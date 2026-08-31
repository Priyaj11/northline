"""Generate a settlement file from the ledger and reconcile it.

The production path, as opposed to the test path. Writes three artifacts:

    reports/settlement.csv               the file that would be sent onward
    reports/reconciliation-report.txt    the readable summary
    reports/reconciliation-report.json   read by the Phase 7 certification engine

Exit code 0 when the reconciliation passes, 1 when it does not. GATE-RECON in
quality-gates.yaml treats any unexplained break as NO-GO, so this exit code
stops a release.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database.warehouse import Warehouse  # noqa: E402
from reconciliation.generator import (  # noqa: E402
    read_settlement_file,
    records_from_ledger,
    write_settlement_file,
)
from reconciliation.reconciler import reconcile  # noqa: E402
from reconciliation.reports import render_text, write_json  # noqa: E402
from utils.config import get_settings  # noqa: E402
from utils.logger import get_logger  # noqa: E402

log = get_logger("reconcile")


def main() -> int:
    settings = get_settings()
    warehouse = Warehouse(settings)

    ledger = records_from_ledger(warehouse.all_transactions())
    if not ledger:
        log.error("The ledger is empty. Run scripts/extract.py first.")
        return 1

    settlement_path = settings.reports_dir / "settlement.csv"
    written = write_settlement_file(ledger, settlement_path)
    log.info("Wrote %d record(s) to %s", written, settlement_path)

    report = reconcile(ledger, read_settlement_file(settlement_path))

    text_path = settings.reports_dir / "reconciliation-report.txt"
    text_path.write_text(render_text(report))
    json_path = write_json(report, settings.reports_dir / "reconciliation-report.json")

    print()
    print(render_text(report))
    log.info("Wrote %s and %s", text_path.name, json_path.name)

    if not report.passed:
        log.error("RECONCILIATION FAILED with %d break(s)", len(report.breaks))
        return 1

    log.info("RECONCILIATION PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
