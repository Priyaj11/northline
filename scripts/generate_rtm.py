"""Generate the Requirements Traceability Matrix.

The traceability matrix is the table that answers the only question that
matters at release time: is every requirement covered by a test, did that test
run, and what did it find.

It links, in one chain:

    requirement -> test case -> automation -> defect -> result

At this stage of the project no test has been executed and no defect has been
raised, so the result and defect columns read "not executed" and "none". They
are populated from real data in Phase 6 and Phase 7. Nothing is invented here.

Exit code 1 if any requirement has no test case at all, so a coverage gap fails
the pipeline rather than sitting unnoticed in a document.
"""

from __future__ import annotations

import sys
from collections import Counter, defaultdict
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.logger import get_logger  # noqa: E402

log = get_logger("generate_rtm")

REPO_ROOT = Path(__file__).resolve().parent.parent
REGISTER = REPO_ROOT / "requirements.yaml"
CASE_DIR = REPO_ROOT / "test-cases"
DEFECT_REGISTER = REPO_ROOT / "defects" / "register.yaml"
OUTPUT = REPO_ROOT / "docs" / "requirements-traceability-matrix.md"

NOT_EXECUTED = "not executed"
NO_DEFECT = "none"


def load_defects() -> list[dict]:
    """The defect register, if it exists yet."""
    if not DEFECT_REGISTER.exists():
        return []
    return yaml.safe_load(DEFECT_REGISTER.read_text()).get("defects", [])


def load_results() -> dict[str, str]:
    """Map an automated test's node identifier to its outcome, from JUnit XML.

    Only test cases that name a specific automated_test can be given a result.
    Everything else is automated at suite level: the suite covering that area
    runs, but nothing in the data proves which function corresponds to which
    case identifier.

    Matching the rest by name would be guessing, and a traceability matrix built
    on guesses is worse than one with an honest gap, because nobody can tell
    which rows are trustworthy.
    """
    import xml.etree.ElementTree as ET

    results: dict[str, str] = {}
    reports = REPO_ROOT / "reports"
    if not reports.exists():
        return results

    for path in sorted(reports.glob("junit-*.xml")):
        try:
            root = ET.parse(path).getroot()
        except ET.ParseError:
            continue
        suites = [root] if root.tag == "testsuite" else root.findall("testsuite")
        for suite in suites:
            for case in suite.findall("testcase"):
                node = f"{case.get('file', '')}::{case.get('name', '')}"
                if case.find("failure") is not None or case.find("error") is not None:
                    outcome = "FAILED"
                elif case.find("skipped") is not None:
                    outcome = "expected failure or skipped"
                else:
                    outcome = "passed"
                results[node] = outcome
                # Also key on the bare function name, since a case may record its
                # automated_test with or without a parametrised suffix.
                results.setdefault(case.get("name", ""), outcome)
    return results


def load_cases() -> list[dict]:
    cases: list[dict] = []
    for path in sorted(CASE_DIR.glob("*.yaml")):
        suite = yaml.safe_load(path.read_text())
        for case in suite.get("test_cases", []):
            case["_suite"] = suite.get("suite", path.stem)
            cases.append(case)
    return cases


def main() -> int:
    if not REGISTER.exists():
        log.error("Requirements register not found: %s", REGISTER)
        return 1

    register = yaml.safe_load(REGISTER.read_text())
    requirements = register["requirements"]
    areas = register["areas"]
    cases = load_cases()

    by_requirement: dict[str, list[dict]] = defaultdict(list)
    for case in cases:
        by_requirement[case["requirement"]].append(case)

    # Defects are linked in two directions. A defect names the requirements it
    # violates and the test cases that found it, so the matrix can show, for any
    # row, whether that specific test case raised something.
    defects = load_defects()
    results = load_results()
    defects_by_case: dict[str, list[dict]] = defaultdict(list)
    defects_by_requirement: dict[str, list[dict]] = defaultdict(list)
    for defect in defects:
        for cid in defect.get("test_cases", []):
            defects_by_case[cid].append(defect)
        for rid in defect.get("requirements", []):
            defects_by_requirement[rid].append(defect)

    req_ids = {r["id"] for r in requirements}
    orphans = sorted({c["requirement"] for c in cases} - req_ids)
    uncovered = sorted(r["id"] for r in requirements if not by_requirement.get(r["id"]))

    covered = len(requirements) - len(uncovered)
    coverage_pct = round(100 * covered / len(requirements), 1) if requirements else 0.0

    automation_counts = Counter(c["automation"] for c in cases)
    technique_counts = Counter(c["technique"] for c in cases)

    lines = [
        "# Requirements Traceability Matrix",
        "",
        "Generated by scripts/generate_rtm.py from requirements.yaml and test-cases/*.yaml.",
        "Do not edit by hand.",
        "",
        f"Release: {register.get('release', 'unspecified')}  ",
        f"System Under Test: {register.get('system_under_test', 'unspecified')}",
        "",
        "## What this table is for",
        "",
        "It links each requirement to the test cases that cover it, the automation",
        "that runs them, any defect they found, and the result. A requirement with no",
        "test case is a coverage gap. A test case with no requirement is a test nobody",
        "asked for.",
        "",
        "## Honesty note",
        "",
        "The defect column is populated from defects/register.yaml and reflects defects",
        "actually raised against the named test case.",
        "",
        "The result column is populated from the JUnit XML files in reports/, but ONLY",
        "for test cases that name a specific automated test. Those read passed, failed,",
        "or expected failure.",
        "",
        "Every other row reads 'no explicit link'. Those cases are automated at suite",
        "level: the suite covering that area runs, but nothing in the data proves which",
        "function corresponds to which case identifier. Matching them by name would be",
        "guessing, and a matrix built on guesses is worse than one with an honest gap,",
        "because nobody can tell which rows are trustworthy.",
        "",
        "Coverage here means a requirement has at least one test case. It does not mean",
        "the requirement is fully verified.",
        "",
        "## Summary",
        "",
        f"| Measure | Value |",
        f"| --- | --- |",
        f"| Requirements | {len(requirements)} |",
        f"| Test cases | {len(cases)} |",
        f"| Requirements with at least one test case | {covered} |",
        f"| Requirements with no test case | {len(uncovered)} |",
        f"| Coverage | {coverage_pct} percent |",
        "",
        "### Test cases by automation status",
        "",
        "| Status | Count |",
        "| --- | --- |",
    ]
    for status in ("automated", "planned", "manual", "deferred"):
        lines.append(f"| {status} | {automation_counts.get(status, 0)} |")

    lines += ["", "### Test cases by design technique", "", "| Technique | Count |", "| --- | --- |"]
    for technique, count in sorted(technique_counts.items(), key=lambda kv: -kv[1]):
        lines.append(f"| {technique} | {count} |")

    if defects:
        lines += [
            "",
            "## Requirements with defects raised against them",
            "",
            "| Requirement | Area | Defect | Severity | Priority | Status |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
        for req in requirements:
            for defect in defects_by_requirement.get(req["id"], []):
                lines.append(
                    f"| {req['id']} | {req['area']} | "
                    f"[{defect['id']}](../defects/{defect['document']}) | "
                    f"{defect['severity']} | {defect['priority']} | {defect['status']} |"
                )
        covered_with_defects = len({
            r["id"] for r in requirements if defects_by_requirement.get(r["id"])
        })
        lines += [
            "",
            f"{covered_with_defects} of {len(requirements)} requirements have at least one",
            "defect raised against them.",
            "",
        ]

    lines += ["", "## Matrix", ""]

    for code, area_name in areas.items():
        area_reqs = [r for r in requirements if r["area"] == code]
        if not area_reqs:
            continue
        lines += [
            f"### {code} - {area_name}",
            "",
            "| Requirement | Priority | Source | Test case | Technique | Automation | Defect | Result |",
            "| --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
        for req in area_reqs:
            matched = by_requirement.get(req["id"], [])
            if not matched:
                lines.append(
                    f"| {req['id']} | {req['priority']} | {req['source']} | "
                    f"**NO TEST CASE** | - | - | - | - |"
                )
                continue
            for case in matched:
                automation = case["automation"]
                if case.get("automated_test"):
                    automation = f"{automation}: `{case['automated_test']}`"
                raised = defects_by_case.get(case["id"], [])
                defect_cell = ", ".join(
                    f"**{d['id']}** ({d['severity']})" for d in raised
                ) or NO_DEFECT

                node = case.get("automated_test")
                if node:
                    result_cell = results.get(node) or results.get(
                        node.split("::")[-1], "no result recorded")
                else:
                    result_cell = "no explicit link"

                lines.append(
                    f"| {req['id']} | {req['priority']} | {req['source']} | "
                    f"{case['id']} {case['title']} | {case['technique']} | "
                    f"{automation} | {defect_cell} | {result_cell} |"
                )
        lines.append("")

    if uncovered:
        lines += ["## Coverage gaps", "",
                  "These requirements have no test case and must be addressed:", ""]
        lines += [f"- {rid}" for rid in uncovered]
        lines.append("")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text("\n".join(lines))

    # A machine-readable summary for the certification engine, which needs the
    # coverage figure for GATE-COVERAGE.
    import json
    reports_dir = REPO_ROOT / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    (reports_dir / "traceability.json").write_text(json.dumps({
        "requirements": len(requirements),
        "test_cases": len(cases),
        "covered": covered,
        "uncovered": uncovered,
        "coverage_percent": coverage_pct,
        "requirements_with_defects": sorted(
            r["id"] for r in requirements if defects_by_requirement.get(r["id"])
        ),
    }, indent=2))

    log.info("Requirements: %d, test cases: %d", len(requirements), len(cases))
    log.info("Coverage: %s percent (%d covered, %d uncovered)", coverage_pct, covered, len(uncovered))
    log.info("Wrote %s", OUTPUT)

    if orphans:
        log.error("Test cases reference unknown requirements: %s", ", ".join(orphans))
        return 1
    if uncovered:
        log.error("Requirements with no test case: %s", ", ".join(uncovered))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
