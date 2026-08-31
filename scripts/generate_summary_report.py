"""Generate the test summary report.

The document a release board reads: what ran, what passed, what was found, and
what the decision was.

Every figure is counted from a file a run produced. Where a number cannot be
derived from the evidence, this says so rather than estimating it.

Writes:
    docs/test-summary-report.md
    reports/summary.json
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from certification.evidence import read_junit  # noqa: E402
from utils.config import get_settings  # noqa: E402
from utils.logger import get_logger  # noqa: E402

log = get_logger("generate_summary_report")

REPO_ROOT = Path(__file__).resolve().parent.parent
REPORTS = REPO_ROOT / "reports"
OUTPUT = REPO_ROOT / "docs" / "test-summary-report.md"

SUITES = [
    ("Smoke", "junit-smoke.xml"),
    ("API", "junit-api.xml"),
    ("User interface", "junit-ui.xml"),
    ("Database and ledger", "junit-database.xml"),
    ("Reconciliation", "junit-reconciliation.xml"),
    ("Accessibility", "junit-accessibility.xml"),
    ("Security-adjacent", "junit-security.xml"),
]


def load_json(name: str) -> dict | None:
    path = REPORTS / name
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except ValueError:
        return None


def main() -> int:
    settings = get_settings()

    suites = []
    for label, filename in SUITES:
        summary = read_junit(REPORTS / filename)
        suites.append({"suite": label, "file": filename, "summary": summary})

    executed = sum(s["summary"]["executed"] for s in suites if s["summary"])
    not_passed = sum(s["summary"]["not_passed"] for s in suites if s["summary"])
    skipped = sum(s["summary"]["skipped"] for s in suites if s["summary"])
    total = sum(s["summary"]["total"] for s in suites if s["summary"])
    overall_rate = round(100 * (executed - not_passed) / executed, 2) if executed else 0.0

    defects = load_json("defects.json")
    certification = load_json("certification.json")
    trace = load_json("traceability.json")
    recon = load_json("reconciliation-report.json")
    perf = load_json("performance-report.json")

    cases = []
    for path in sorted((REPO_ROOT / "test-cases").glob("*.yaml")):
        cases.extend(yaml.safe_load(path.read_text()).get("test_cases", []))
    automated = [c for c in cases if c.get("automated_test")]

    payload = {
        "release": settings.release,
        "environment": settings.environment,
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        "execution": {
            "recorded": total,
            "executed": executed,
            "not_passed": not_passed,
            "skipped_or_expected_failure": skipped,
            "pass_rate_percent": overall_rate,
        },
        "suites": suites,
        "decision": certification.get("decision") if certification else None,
    }
    (REPORTS / "summary.json").write_text(json.dumps(payload, indent=2, default=str))
    OUTPUT.write_text(render(payload, suites, defects, certification, trace, recon,
                             perf, cases, automated, settings))

    log.info("Executed %d, not passed %d, pass rate %s percent",
             executed, not_passed, overall_rate)
    log.info("Decision: %s", payload["decision"] or "not evaluated")
    log.info("Wrote %s", OUTPUT.name)
    return 0


def render(payload, suites, defects, certification, trace, recon, perf,
           cases, automated, settings) -> str:
    e = payload["execution"]
    decision = payload["decision"] or "not evaluated"

    lines = [
        "# Test summary report",
        "",
        f"    release      {payload['release']}",
        f"    environment  {payload['environment']}",
        f"    generated    {payload['generated_at']}",
        "",
        "```",
        f"    RELEASE DECISION: {decision}",
        "```",
        "",
        "Every figure below is counted from a file produced by a run that happened.",
        "Where a number cannot be derived from the evidence, this report says so",
        "rather than estimating it.",
        "",
        "## Execution",
        "",
        "| Measure | Value |",
        "| --- | --- |",
        f"| Test cases recorded in the run | {e['recorded']} |",
        f"| Executed | {e['executed']} |",
        f"| Not passed | {e['not_passed']} |",
        f"| Skipped or expected failure | {e['skipped_or_expected_failure']} |",
        f"| Pass rate | {e['pass_rate_percent']} percent |",
        "",
        "Expected failures are counted as skipped, which is how pytest records them",
        "in JUnit XML. Each one is a known defect whose test is marked so the suite",
        "stays green for NEW regressions. They are not hidden: every one appears in",
        "the defect register below, and the release gate reads that register rather",
        "than these results.",
        "",
        "## By suite",
        "",
        "| Suite | Recorded | Executed | Not passed | Expected failures | Pass rate | Source |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for s in suites:
        if not s["summary"]:
            lines.append(f"| {s['suite']} | - | - | - | - | not run | `{s['file']}` missing |")
            continue
        d = s["summary"]
        lines.append(
            f"| {s['suite']} | {d['total']} | {d['executed']} | {d['not_passed']} | "
            f"{d['skipped']} | {d['pass_rate_percent']}% | `reports/{s['file']}` |"
        )
    lines.append("")

    if defects:
        lines += [
            "## Defects",
            "",
            f"    total                        {defects['total']}",
            f"    open                         {defects['open']}",
            f"    open and release blocking    {defects['release_blocking_open']}",
            "",
            "### By severity",
            "",
            "| Severity | Count |",
            "| --- | --- |",
        ]
        for severity in ("Critical", "High", "Medium", "Low"):
            lines.append(f"| {severity} | {defects['by_severity'].get(severity, 0)} |")

        lines += ["", "### By detection stage", "", "| Phase | Count |", "| --- | --- |"]
        for phase, count in defects["by_detection_phase"].items():
            lines.append(f"| Phase {phase} | {count} |")

        lines += ["", "### By detection method", "", "| Method | Count |", "| --- | --- |"]
        for method, count in sorted(defects["by_detection_method"].items()):
            lines.append(f"| {method} | {count} |")

        lines += [
            "",
            "Detection stage answers a question a release board asks: was this found",
            "early or late. Detection method answers another: did the test design find",
            "it, or did somebody find it by looking around. Both matter, and a report",
            "that credits everything to the test design overstates it.",
            "",
        ]

    if trace:
        lines += [
            "## Requirement coverage",
            "",
            f"    requirements                 {trace['requirements']}",
            f"    test cases                   {trace['test_cases']}",
            f"    requirements with a test     {trace['covered']}",
            f"    coverage                     {trace['coverage_percent']} percent",
            f"    requirements with a defect   {len(trace['requirements_with_defects'])}",
            "",
            "Coverage here means every requirement has at least one test case. It does",
            "NOT mean every requirement is fully verified: a requirement with one",
            "shallow case counts the same as one with fifteen thorough ones. Reported",
            "this way because that is what the number actually measures.",
            "",
            "### Automation linkage, stated honestly",
            "",
            f"    test cases in the registers          {len(cases)}",
            f"    naming a specific automated test     {len(automated)}",
            "",
            "Only those cases carry a verifiable link between a test case identifier",
            "and the function that runs it. The rest are automated at suite level: the",
            "suite covering that area runs, but nothing in the data proves which",
            "function corresponds to which case identifier.",
            "",
            "The result column of the traceability matrix is populated only for cases",
            "with that explicit link. Matching the others by name would be guessing,",
            "and a traceability matrix built on guesses is worse than one with an",
            "honest gap, because nobody can tell which rows are trustworthy.",
            "",
        ]

    if recon:
        lines += [
            "## Settlement reconciliation",
            "",
            f"    ledger records      {recon['ledger_count']}",
            f"    settlement records  {recon['settlement_count']}",
            f"    matched             {recon['matched']}",
            f"    breaks              {recon['break_count']}",
            f"    status              {recon['status'].upper()}",
            "",
        ]

    if perf:
        lines += [
            "## Performance",
            "",
            "| Threads requested | Peak concurrency | Samples | Errors | p95 | Status |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
        for profile in perf["profiles"]:
            o = profile["overall"]
            lines.append(
                f"| {profile.get('users_requested', profile.get('users'))} | "
                f"{o.get('peak_concurrency', '-')} | {o['samples']} | {o['errors']} | "
                f"{o['p95_ms']} ms | {profile['status'].upper()} |"
            )
        lines += [
            "",
            "Run locally, not in continuous integration. A shared runner's timing is",
            "not comparable between runs. See docs/performance-notes.md, which records",
            "the first run being green and invalid.",
            "",
        ]

    if certification:
        lines += [
            "## Release decision",
            "",
            f"    decision   {certification['decision']}",
            f"    gates      {certification['gates_passed']} of "
            f"{certification['gates_total']} passed",
            "",
        ]
        if certification["gates_blocking"]:
            lines += ["Blocking:", ""]
            lines += [f"    {g}" for g in certification["gates_blocking"]]
            lines.append("")
        if certification["gates_of_concern"]:
            lines += ["Recorded concerns:", ""]
            lines += [f"    {g}" for g in certification["gates_of_concern"]]
            lines.append("")
        lines += [
            "Produced mechanically by scripts/certify.py from the thresholds in",
            "quality-gates.yaml. The full breakdown, with the evidence file behind",
            "every figure, is in docs/release-certification.md.",
            "",
        ]

    lines += [
        "## What this report does not contain",
        "",
        "    time to fix, reopen rate, fix effectiveness",
        "        No defect has been fixed, so there is no fix history to measure.",
        "",
        "    defect density per thousand lines",
        "        The application under test is third-party code whose size is not",
        "        measured here, and dividing by a number nobody counted is not a",
        "        metric.",
        "",
        "    manual accessibility results",
        "        docs/accessibility-manual-checklist.md has a blank result column",
        "        because those checks have not been performed. A checklist filled in",
        "        without performing the checks looks like evidence and is not.",
        "",
        "    User Acceptance Testing results",
        "        Scenarios are designed and recorded as designed, not executed. There",
        "        is no business user to execute them, and claiming otherwise would be",
        "        fiction.",
        "",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())
