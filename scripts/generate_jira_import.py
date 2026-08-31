"""Generate Jira-importable CSV files from the project's own registers.

Northline's source of truth is its YAML registers, not Jira. This script
exports them into the shape Jira's CSV importer expects, so the project can be
loaded into a Jira instance without ever depending on one.

That direction matters. A project that keeps its requirements inside a Jira
free tier stops working the day the tier changes, and cannot be reviewed by
anyone without an account. Keeping the registers in the repository and treating
Jira as an export target keeps the project self contained and reviewable.

Writes into reports/jira/:

    epics.csv         one epic per requirement area
    requirements.csv  one story per requirement
    tests.csv         one test issue per test case
    defects.csv       one bug per defect

Jira's importer matches issues by the Issue ID and Parent ID columns during a
single import, so importing all four files in one pass preserves the hierarchy.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.logger import get_logger  # noqa: E402

log = get_logger("generate_jira_import")

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "reports" / "jira"

SEVERITY_TO_JIRA_PRIORITY = {
    "Critical": "Highest",
    "High": "High",
    "Medium": "Medium",
    "Low": "Low",
}


def write_csv(path: Path, header: list[str], rows: list[list]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)
    return len(rows)


def main() -> int:
    requirements_file = yaml.safe_load((REPO_ROOT / "requirements.yaml").read_text())
    requirements = requirements_file["requirements"]
    areas = requirements_file["areas"]

    cases = []
    for path in sorted((REPO_ROOT / "test-cases").glob("*.yaml")):
        suite = yaml.safe_load(path.read_text())
        for case in suite.get("test_cases", []):
            case["_suite"] = suite.get("suite", path.stem)
            cases.append(case)

    defect_register = REPO_ROOT / "defects" / "register.yaml"
    defects = yaml.safe_load(defect_register.read_text())["defects"] if defect_register.exists() else []

    release = requirements_file.get("release", "R1.0")

    # Epics, one per requirement area.
    epic_rows = [
        [f"EPIC-{code}", "Epic", f"{code} - {name}",
         f"Requirements and testing for the {name.lower()} area.", release]
        for code, name in areas.items()
        if any(r["area"] == code for r in requirements)
    ]
    n_epics = write_csv(
        OUT_DIR / "epics.csv",
        ["Issue ID", "Issue Type", "Summary", "Description", "Fix Version"],
        epic_rows,
    )

    # Requirements as stories, parented to their area epic.
    requirement_rows = [
        [r["id"], "Story", r["title"], " ".join(str(r["detail"]).split()),
         r["priority"], f"EPIC-{r['area']}", release,
         f"source:{r['source']}", ", ".join(r["verification"])]
        for r in requirements
    ]
    n_requirements = write_csv(
        OUT_DIR / "requirements.csv",
        ["Issue ID", "Issue Type", "Summary", "Description", "Priority",
         "Parent ID", "Fix Version", "Labels", "Verified By"],
        requirement_rows,
    )

    # Test cases as Test issues, linked to the requirement they cover.
    test_rows = []
    for case in cases:
        steps = " ".join(
            f"{i}. {' '.join(str(s).split())}" for i, s in enumerate(case["steps"], 1)
        )
        description = (
            f"Technique: {case['technique']}\n"
            f"Layer: {case['layer']}\n"
            f"Preconditions: {' '.join(str(case['preconditions']).split())}\n"
            f"Test data: {' '.join(str(case['test_data']).split())}\n"
            f"Steps: {steps}\n"
            f"Expected: {' '.join(str(case['expected']).split())}"
        )
        test_rows.append([
            case["id"], "Test", case["title"], description, case["priority"],
            case["requirement"], release,
            f"technique:{case['technique'].replace(' ', '-')} automation:{case['automation']}",
            case.get("automated_test", ""),
        ])
    n_tests = write_csv(
        OUT_DIR / "tests.csv",
        ["Issue ID", "Issue Type", "Summary", "Description", "Priority",
         "Linked Issue (tests)", "Fix Version", "Labels", "Automation Reference"],
        test_rows,
    )

    # Defects as bugs, linked to the requirement they violate and the tests that found them.
    defect_rows = []
    for defect in defects:
        document = REPO_ROOT / "defects" / defect["document"]
        summary_line = (
            f"See {defect['document']} in the repository for the full writeup with "
            f"evidence and reproduction steps."
        )
        defect_rows.append([
            defect["id"], "Bug", defect["title"], summary_line,
            SEVERITY_TO_JIRA_PRIORITY[defect["severity"]],
            defect["status"], ", ".join(defect["requirements"]),
            ", ".join(defect["test_cases"]) or "none (found by exploratory testing)",
            release,
            f"severity:{defect['severity']} layer:{defect['detection_layer']} "
            f"found:{defect['detection_method'].replace(' ', '-')}",
            str(defect["detected_on"]),
            "yes" if document.exists() else "MISSING",
        ])
    n_defects = write_csv(
        OUT_DIR / "defects.csv",
        ["Issue ID", "Issue Type", "Summary", "Description", "Priority", "Status",
         "Linked Issue (blocks)", "Linked Issue (found by)", "Fix Version",
         "Labels", "Detected On", "Writeup Present"],
        defect_rows,
    )

    log.info("Wrote %d epic(s), %d requirement(s), %d test(s), %d defect(s) to %s",
             n_epics, n_requirements, n_tests, n_defects, OUT_DIR)
    return 0


if __name__ == "__main__":
    sys.exit(main())
