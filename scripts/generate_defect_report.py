"""Validate the defect register and generate the defect report.

defects/register.yaml is the machine-readable index of the narrative writeups
in defects/DEF-NNN.md. This script checks the two stay consistent with each
other and with the requirements and test cases, then produces:

    docs/defect-report.md      the readable report with metrics
    reports/defects.json       read by the Phase 7 certification engine

Every figure is counted from the register. Nothing is estimated, and no metric
is reported that the data cannot support: there is no fix history here, so no
reopen rate, no time to fix, and no fix effectiveness.

Exit code 1 on any inconsistency, so a register that has drifted from the
requirements, the test cases or the writeups fails the pipeline.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.logger import get_logger  # noqa: E402

log = get_logger("generate_defect_report")

REPO_ROOT = Path(__file__).resolve().parent.parent
REGISTER = REPO_ROOT / "defects" / "register.yaml"
REQUIREMENTS = REPO_ROOT / "requirements.yaml"
CASE_DIR = REPO_ROOT / "test-cases"
DEFECT_DIR = REPO_ROOT / "defects"
OUTPUT = REPO_ROOT / "docs" / "defect-report.md"

SEVERITIES = ("Critical", "High", "Medium", "Low")
PRIORITIES = ("P1", "P2", "P3", "P4")
STATUSES = ("Open", "In progress", "Fixed", "Closed", "Deferred", "Rejected")
METHODS = ("designed test case", "exploratory", "reported")

#: Severities that fail GATE-CRITICAL-DEFECT when open.
RELEASE_BLOCKING = ("Critical", "High")

REQUIRED = ("id", "title", "severity", "priority", "status", "requirements",
            "test_cases", "detected_in_phase", "detected_on",
            "detection_method", "detection_layer", "reproducibility", "document")


def load_known_ids() -> tuple[set[str], set[str], dict[str, str]]:
    register = yaml.safe_load(REQUIREMENTS.read_text())
    requirement_ids = {r["id"] for r in register["requirements"]}
    area_of = {r["id"]: r["area"] for r in register["requirements"]}

    case_ids: set[str] = set()
    for path in sorted(CASE_DIR.glob("*.yaml")):
        suite = yaml.safe_load(path.read_text())
        case_ids.update(c["id"] for c in suite.get("test_cases", []))

    return requirement_ids, case_ids, area_of


def validate(defects: list[dict], requirement_ids: set[str], case_ids: set[str]) -> list[str]:
    problems: list[str] = []
    seen: set[str] = set()

    for defect in defects:
        did = defect.get("id", "<missing id>")
        for field in REQUIRED:
            if field not in defect:
                problems.append(f"{did}: missing field '{field}'")
        if did in seen:
            problems.append(f"{did}: duplicate identifier")
        seen.add(did)

        if defect.get("severity") not in SEVERITIES:
            problems.append(f"{did}: severity must be one of {SEVERITIES}")
        if defect.get("priority") not in PRIORITIES:
            problems.append(f"{did}: priority must be one of {PRIORITIES}")
        if defect.get("status") not in STATUSES:
            problems.append(f"{did}: status must be one of {STATUSES}")
        if defect.get("detection_method") not in METHODS:
            problems.append(f"{did}: detection_method must be one of {METHODS}")

        for rid in defect.get("requirements", []):
            if rid not in requirement_ids:
                problems.append(f"{did}: unknown requirement '{rid}'")
        for cid in defect.get("test_cases", []):
            if cid not in case_ids:
                problems.append(f"{did}: unknown test case '{cid}'")

        document = DEFECT_DIR / str(defect.get("document", ""))
        if not document.exists():
            problems.append(f"{did}: writeup {document.name} does not exist")

        if defect.get("detection_method") == "designed test case" and not defect.get("test_cases"):
            problems.append(
                f"{did}: recorded as found by a designed test case but names none"
            )

    return problems


def main() -> int:
    register = yaml.safe_load(REGISTER.read_text())
    defects = register["defects"]
    requirement_ids, case_ids, area_of = load_known_ids()

    problems = validate(defects, requirement_ids, case_ids)
    if problems:
        log.error("Register is invalid, %d problem(s):", len(problems))
        for problem in problems:
            log.error("  %s", problem)
        return 1

    open_defects = [d for d in defects if d["status"] in ("Open", "In progress")]
    blocking = [d for d in open_defects if d["severity"] in RELEASE_BLOCKING]

    by_severity = Counter(d["severity"] for d in defects)
    by_priority = Counter(d["priority"] for d in defects)
    by_status = Counter(d["status"] for d in defects)
    by_phase = Counter(d["detected_in_phase"] for d in defects)
    by_method = Counter(d["detection_method"] for d in defects)
    by_layer = Counter(d["detection_layer"] for d in defects)

    by_area: Counter = Counter()
    for defect in defects:
        for rid in defect["requirements"]:
            by_area[area_of[rid]] += 1

    summary = {
        "release": register.get("release"),
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        "total": len(defects),
        "open": len(open_defects),
        "release_blocking_open": len(blocking),
        "release_blocking_ids": [d["id"] for d in blocking],
        "by_severity": dict(by_severity),
        "by_priority": dict(by_priority),
        "by_status": dict(by_status),
        "by_detection_phase": {str(k): v for k, v in sorted(by_phase.items())},
        "by_detection_method": dict(by_method),
        "by_detection_layer": dict(by_layer),
        "by_requirement_area": dict(by_area),
        "defects": defects,
    }

    reports_dir = REPO_ROOT / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    (reports_dir / "defects.json").write_text(json.dumps(summary, indent=2, default=str))
    OUTPUT.write_text(render(summary, area_of))

    log.info("Validated %d defect(s), %d open, %d release blocking",
             len(defects), len(open_defects), len(blocking))
    log.info("Wrote %s and reports/defects.json", OUTPUT.name)
    return 0


def render(summary: dict, area_of: dict[str, str]) -> str:
    defects = summary["defects"]
    lines = [
        "# Defect report",
        "",
        "Generated by scripts/generate_defect_report.py from defects/register.yaml.",
        "Do not edit by hand.",
        "",
        f"Release: {summary['release']}",
        "",
        "This document is deterministic: the same register always produces the same",
        "bytes. It carries no generation timestamp on purpose. A committed generated",
        "file that changes on every regeneration cannot be checked for drift, and the",
        "check that compares them becomes permanent noise that people learn to bypass.",
        "",
        "The generation time is recorded in reports/defects.json, which the",
        "certification engine reads and which is not committed.",
        "",
        "Every figure below is counted from the register. No metric appears here",
        "that the data cannot support: there is no fix history yet, so there is no",
        "reopen rate, no time to fix and no fix effectiveness.",
        "",
        "## Release impact",
        "",
        f"    total defects                {summary['total']}",
        f"    open                         {summary['open']}",
        f"    open and release blocking    {summary['release_blocking_open']}",
        "",
        "GATE-CRITICAL-DEFECT fails a release on any open defect of severity",
        "Critical or High. Currently blocking: "
        + (", ".join(summary["release_blocking_ids"]) or "none"),
        "",
        "The gate reads THIS register, not the test results. Several of these defects",
        "have their tests marked as expected failures so the suite stays green for new",
        "regressions, and marking a test does not remove its defect from the gate.",
        "",
        "## The register",
        "",
        "| ID | Title | Severity | Priority | Status | Requirements | Found in |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for d in defects:
        lines.append(
            f"| [{d['id']}](../defects/{d['document']}) | {d['title']} | {d['severity']} | "
            f"{d['priority']} | {d['status']} | {', '.join(d['requirements'])} | "
            f"Phase {d['detected_in_phase']} |"
        )

    def table(title: str, counts: dict, order=None) -> list[str]:
        keys = order if order else sorted(counts)
        rows = [f"| {k} | {counts.get(k, 0)} |" for k in keys if counts.get(k, 0) or order]
        return ["", f"### {title}", "", "| | Count |", "| --- | --- |"] + rows

    lines += table("By severity", summary["by_severity"], SEVERITIES)
    lines += table("By priority", summary["by_priority"], PRIORITIES)
    lines += table("By status", summary["by_status"])
    lines += table("By detection layer", summary["by_detection_layer"])
    lines += table("By requirement area", summary["by_requirement_area"])

    lines += ["", "### By phase in which it was detected", "", "| Phase | Count |", "| --- | --- |"]
    for phase, count in summary["by_detection_phase"].items():
        lines.append(f"| Phase {phase} | {count} |")

    lines += ["", "### By detection method", "", "| Method | Count |", "| --- | --- |"]
    for method, count in sorted(summary["by_detection_method"].items()):
        lines.append(f"| {method} | {count} |")

    lines += [
        "",
        "Detection method is recorded because a register that credits every defect to",
        "a planned test case overstates how much the test design found. Exploratory",
        "work found one of these, and saying so is more useful than a tidier number.",
        "",
        "## Severity and priority are different things",
        "",
        "    Severity   technical impact: how badly is the system broken",
        "    Priority   business urgency: how soon must it be fixed",
        "",
        "They vary independently, which is the point of having both:",
        "",
        "    High severity, low priority   data corruption in a feature nobody uses yet",
        "    Low severity, high priority   the bank's name misspelt on the login page",
        "",
        "In this register DEF-002 and DEF-004 are the clearest example of the split in",
        "action. Both are real and neither blocks a customer from completing a task, so",
        "both are Medium and P3, while DEF-001 and DEF-005 put money and customer data",
        "at risk and are Critical and P1.",
        "",
        "## Why some findings are NOT in this register",
        "",
        "Two things were investigated and deliberately not raised as defects.",
        "",
        "The self-contradictory transaction records in ParaBank's seeded data, where a",
        "record described as received is typed as a debit. An experiment established",
        "that the application writes correct records today and the inconsistency comes",
        "from the demo dataset. Recorded as Observation 10 in docs/sut-parabank.md.",
        "",
        "The three cross-customer access failures. They share one root cause with",
        "DEF-005: with no authentication there is no requester, so there can be no",
        "check that a record belongs to one. Three entries for one problem would give",
        "a team no way to prioritise.",
        "",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())
