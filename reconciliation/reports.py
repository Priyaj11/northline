"""Rendering of reconciliation results.

Two outputs, for two audiences. A readable summary a person scans, and a JSON
document the certification engine in Phase 7 reads to decide GO or NO-GO.
"""

from __future__ import annotations

import json
from pathlib import Path

from reconciliation.models import BreakKind, ReconciliationReport

KIND_LABELS = {
    BreakKind.MISSING: "Missing from settlement",
    BreakKind.UNEXPECTED: "Unexpected in settlement",
    BreakKind.DUPLICATE: "Duplicated in settlement",
    BreakKind.AMOUNT_MISMATCH: "Amount mismatch",
    BreakKind.ACCOUNT_MISMATCH: "Account mismatch",
}


def render_text(report: ReconciliationReport) -> str:
    lines = [
        "SETTLEMENT RECONCILIATION REPORT",
        "=" * 64,
        "",
        f"  Generated          {report.generated_at.isoformat() if report.generated_at else 'unknown'}",
        f"  Ledger records     {report.ledger_count}",
        f"  Settlement records {report.settlement_count}",
        f"  Matched            {report.matched}",
        "",
        "  Breaks by kind",
    ]
    counts = report.counts()
    for kind in BreakKind:
        lines.append(f"    {KIND_LABELS[kind]:<26} {counts[kind.value]}")

    lines += ["", f"  Total breaks       {len(report.breaks)}",
              f"  STATUS             {report.status.upper()}", ""]

    if report.breaks:
        lines += ["  Detail", ""]
        lines += [f"    {b}" for b in report.breaks]
        lines.append("")

    return "\n".join(lines)


def write_json(report: ReconciliationReport, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report.as_dict(), indent=2))
    return path
