"""Collect the evidence each quality gate needs from the reports on disk.

Kept separate from the evaluator on purpose. The evaluator decides; this reads
files. That split is what lets the decision logic be tested exhaustively with
constructed evidence and no environment at all.

Every gate's evidence names its source file, and that source appears in the
report. A number in a release decision that cannot be traced to the file it came
from is not evidence, it is an assertion.

A MISSING FILE IS NOT A PASS. When a report is absent, this collector returns
nothing for that gate and the evaluator records "no evidence", which does not
satisfy the gate. Deleting a report must never be a way to certify a release.
"""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
REPORTS = REPO_ROOT / "reports"


def _load_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except (ValueError, OSError):
        return None


def read_junit(path: Path) -> dict | None:
    """Summarise a JUnit XML file.

    Note on expected failures: pytest records an xfail as a SKIPPED case, not a
    failure, so a known defect marked xfail does not count against a pass rate.
    That is deliberate and it is why GATE-CRITICAL-DEFECT reads the defect
    register instead: a known defect stays visible to the release decision no
    matter how its test is marked.
    """
    if not path.exists():
        return None
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError:
        return None

    suites = [root] if root.tag == "testsuite" else root.findall("testsuite")
    total = failures = errors = skipped = 0
    for suite in suites:
        total += int(suite.get("tests", 0))
        failures += int(suite.get("failures", 0))
        errors += int(suite.get("errors", 0))
        skipped += int(suite.get("skipped", 0))

    executed = total - skipped
    not_passed = failures + errors
    pass_rate = round(100 * (executed - not_passed) / executed, 2) if executed else 0.0

    return {
        "total": total,
        "failures": failures,
        "errors": errors,
        "skipped": skipped,
        "executed": executed,
        "not_passed": not_passed,
        "pass_rate_percent": pass_rate,
    }


def collect() -> tuple[dict[str, Any], list[str]]:
    """Return (evidence, notes). Notes record what could not be found."""
    evidence: dict[str, Any] = {}
    notes: list[str] = []

    def record(gate_id: str, observed, source: str) -> None:
        evidence[gate_id] = {"observed": observed, "source": source}

    def missing(gate_id: str, what: str) -> None:
        notes.append(f"{gate_id}: {what} not found")

    # GATE-ENV, from the readiness check.
    env = _load_json(REPORTS / "environment.json")
    if env is None:
        missing("GATE-ENV", "reports/environment.json")
    else:
        record("GATE-ENV", bool(env.get("ready")), "reports/environment.json")

    # GATE-SMOKE, zero failures allowed.
    smoke = read_junit(REPORTS / "junit-smoke.xml")
    if smoke is None:
        missing("GATE-SMOKE", "reports/junit-smoke.xml")
    else:
        record("GATE-SMOKE", smoke["not_passed"], "reports/junit-smoke.xml")

    # GATE-API-PASS, a pass rate.
    api = read_junit(REPORTS / "junit-api.xml")
    if api is None:
        missing("GATE-API-PASS", "reports/junit-api.xml")
    else:
        record("GATE-API-PASS", api["pass_rate_percent"], "reports/junit-api.xml")

    # GATE-UI-PASS, a pass rate.
    ui = read_junit(REPORTS / "junit-ui.xml")
    if ui is None:
        missing("GATE-UI-PASS", "reports/junit-ui.xml")
    else:
        record("GATE-UI-PASS", ui["pass_rate_percent"], "reports/junit-ui.xml")

    # GATE-CRITICAL-DEFECT, from the register rather than from any test result.
    defects = _load_json(REPORTS / "defects.json")
    if defects is None:
        missing("GATE-CRITICAL-DEFECT", "reports/defects.json")
    else:
        record("GATE-CRITICAL-DEFECT", defects.get("release_blocking_open"),
               "reports/defects.json")

    # GATE-RECON, unexplained breaks.
    recon = _load_json(REPORTS / "reconciliation-report.json")
    if recon is None:
        missing("GATE-RECON", "reports/reconciliation-report.json")
    else:
        record("GATE-RECON", recon.get("break_count"),
               "reports/reconciliation-report.json")

    # GATE-ACCESSIBILITY, critical and serious violations across every page.
    scan = _load_json(REPORTS / "accessibility-scan.json")
    if scan is None:
        missing("GATE-ACCESSIBILITY", "reports/accessibility-scan.json")
    else:
        serious = 0
        for page in scan.values():
            for violation in page.get("violations", []):
                if violation.get("impact") in ("critical", "serious"):
                    serious += 1
        record("GATE-ACCESSIBILITY", serious, "reports/accessibility-scan.json")

    # GATE-PERF-P95 and GATE-PERF-ERROR, the worst profile in the run.
    perf = _load_json(REPORTS / "performance-report.json")
    if perf is None:
        missing("GATE-PERF-P95", "reports/performance-report.json")
        missing("GATE-PERF-ERROR", "reports/performance-report.json")
    else:
        profiles = perf.get("profiles", [])
        if not profiles:
            missing("GATE-PERF-P95", "any profile in reports/performance-report.json")
            missing("GATE-PERF-ERROR", "any profile in reports/performance-report.json")
        else:
            # The worst figure across profiles, not the average and not the
            # lightest load. A gate that passes because one quiet profile
            # dragged the number down is not a gate.
            worst_p95 = max(p["overall"]["p95_ms"] for p in profiles)
            worst_errors = max(p["overall"]["error_rate_percent"] for p in profiles)
            record("GATE-PERF-P95", worst_p95,
                   "reports/performance-report.json (worst profile)")
            record("GATE-PERF-ERROR", worst_errors,
                   "reports/performance-report.json (worst profile)")

    # GATE-COVERAGE, from the traceability matrix.
    trace = _load_json(REPORTS / "traceability.json")
    if trace is None:
        missing("GATE-COVERAGE", "reports/traceability.json")
    else:
        record("GATE-COVERAGE", trace.get("coverage_percent"),
               "reports/traceability.json")

    return evidence, notes
