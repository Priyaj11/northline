"""Propose automation links between test cases and the tests that run them.

Every automated test in this project names the test case it covers in its
docstring, in the form "TC-XFER-005 / REQ-XFER-003". This script reads those
docstrings and proposes an automated_test entry for each case.

WHY THIS IS DERIVED RATHER THAN GUESSED

The obvious approach is to match test function names against test case titles.
That produces plausible links that are sometimes wrong, and a traceability
matrix nobody can trust is worse than one with an honest gap.

This reads what each test explicitly CLAIMS to cover. A test that does not name
a case identifier produces no link, and a case no test names stays unlinked.
Both of those are real findings rather than gaps in the tooling.

Writes reports/automation-links.yaml for review. It changes nothing on its own:
applying the links is a separate, deliberate step.
"""

from __future__ import annotations

import ast
import re
import sys
from collections import defaultdict
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.logger import get_logger  # noqa: E402

log = get_logger("discover_automation_links")

REPO_ROOT = Path(__file__).resolve().parent.parent
TESTS_DIR = REPO_ROOT / "tests"
CASE_DIR = REPO_ROOT / "test-cases"
OUTPUT = REPO_ROOT / "reports" / "automation-links.yaml"

CASE_PATTERN = re.compile(r"\bTC-[A-Z]+-\d{3}\b")


def load_case_ids() -> dict[str, dict]:
    cases: dict[str, dict] = {}
    for path in sorted(CASE_DIR.glob("*.yaml")):
        suite = yaml.safe_load(path.read_text())
        for case in suite.get("test_cases", []):
            case["_file"] = path.name
            cases[case["id"]] = case
    return cases


def scan_tests() -> dict[str, list[str]]:
    """Map each test case identifier to the node identifiers claiming to cover it."""
    claims: dict[str, list[str]] = defaultdict(list)

    for path in sorted(TESTS_DIR.rglob("test_*.py")):
        try:
            tree = ast.parse(path.read_text())
        except SyntaxError:
            log.error("Could not parse %s", path)
            continue

        relative = path.relative_to(REPO_ROOT)

        # A module-level docstring can name cases covered by the whole file, but
        # those are deliberately NOT used as links: a file-level mention says the
        # suite covers the case, not which function does.
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if not node.name.startswith("test_"):
                continue
            doc = ast.get_docstring(node) or ""
            for case_id in sorted(set(CASE_PATTERN.findall(doc))):
                claims[case_id].append(f"{relative}::{node.name}")

    return claims


def main() -> int:
    cases = load_case_ids()
    claims = scan_tests()

    proposals = []
    unknown_claims = []
    unlinked = []

    for case_id, case in cases.items():
        found = claims.get(case_id, [])
        existing = case.get("automated_test")

        if not found:
            unlinked.append({
                "id": case_id,
                "title": case["title"],
                "file": case["_file"],
                "automation": case["automation"],
                "reason": "no automated test names this case in its docstring",
            })
            continue

        proposals.append({
            "id": case_id,
            "title": case["title"],
            "file": case["_file"],
            "current_automation": case["automation"],
            "current_link": existing,
            "proposed_link": found[0],
            "also_claimed_by": found[1:],
        })

    for case_id in sorted(set(claims) - set(cases)):
        unknown_claims.append({
            "case_id": case_id,
            "claimed_by": claims[case_id],
            "problem": "a test names a case identifier that is not in any register",
        })

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(yaml.safe_dump({
        "summary": {
            "test_cases": len(cases),
            "with_a_proposed_link": len(proposals),
            "without_a_link": len(unlinked),
            "tests_claiming_unknown_cases": len(unknown_claims),
        },
        "proposals": proposals,
        "unlinked": unlinked,
        "unknown_claims": unknown_claims,
    }, sort_keys=False, width=100))

    log.info("%d of %d test cases have a test naming them",
             len(proposals), len(cases))
    log.info("%d have no automated test naming them", len(unlinked))
    if unknown_claims:
        log.warning("%d test(s) name a case identifier not in any register",
                    len(unknown_claims))
        for u in unknown_claims:
            log.warning("  %s claimed by %s", u["case_id"], ", ".join(u["claimed_by"]))
    log.info("Wrote %s for review. Nothing has been changed.", OUTPUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
