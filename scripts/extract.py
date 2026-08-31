"""Extract ParaBank accounts and transactions into the certification data store.

This is the ETL step: read from the source system through its interface, write
into the store where validation and reconciliation happen.

Deliberately simple. It reads the customer, then their accounts, then every
account's transactions, and writes all of it inside one recorded extraction run
so that every row can be traced back to when it was pulled and from which
environment.

Exit code 0 on success, 1 on failure. Continuous integration gates on it.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database.warehouse import Warehouse  # noqa: E402
from utils.api_client import ApiClient  # noqa: E402
from utils.assertions import json_body  # noqa: E402
from utils.config import get_settings  # noqa: E402
from utils.logger import get_logger  # noqa: E402

log = get_logger("extract")


def main() -> int:
    settings = get_settings()
    api = ApiClient(settings)
    warehouse = Warehouse(settings)

    warehouse.apply_schema()
    warehouse.clear()

    try:
        customer = json_body(api.login(settings.sut.username, settings.sut.password))
    except AssertionError as exc:
        log.error("Could not log in to the source system: %s", exc)
        return 1

    customer_id = customer["id"]
    log.info("Extracting for customer %s", customer_id)

    run_id = warehouse.start_run()

    try:
        accounts = json_body(api.customer_accounts(customer_id))
        written_accounts = warehouse.upsert_accounts(accounts, run_id)
        log.info("Wrote %d account(s)", written_accounts)

        written_transactions = 0
        for account in accounts:
            transactions = json_body(api.account_transactions(account["id"]))
            written_transactions += warehouse.upsert_transactions(transactions, run_id)
        log.info("Wrote %d transaction(s)", written_transactions)

    except Exception as exc:  # noqa: BLE001 - record the failure before re-raising
        warehouse.finish_run(run_id, 0, 0, status="failed")
        log.error("Extraction failed: %s", exc)
        return 1

    warehouse.finish_run(run_id, written_accounts, written_transactions)
    log.info("EXTRACTION COMPLETE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
