"""Reset ParaBank's data to its seeded state.

Discovered in Phase 1, ParaBank exposes two service endpoints:

    POST /services/bank/cleanDB        wipes application data
    POST /services/bank/initializeDB   recreates schema and demo data

Together they give a deterministic reset, which docs/test-data-strategy.md
relies on. Suites that assert absolute values rather than deltas run after this.

Exit code 0 on success, 1 on failure.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.api_client import ApiClient  # noqa: E402
from utils.assertions import json_body  # noqa: E402
from utils.config import get_settings  # noqa: E402
from utils.logger import get_logger  # noqa: E402

log = get_logger("reset_sut_data")


def main() -> int:
    settings = get_settings()
    api = ApiClient(settings)

    log.info("Cleaning application data")
    clean = api.clean_db()
    log.info("cleanDB returned %d", clean.status_code)

    log.info("Reseeding demo data")
    init = api.initialize_db()
    log.info("initializeDB returned %d", init.status_code)

    if clean.status_code >= 400 or init.status_code >= 400:
        log.error("Reset failed. cleanDB=%d initializeDB=%d",
                  clean.status_code, init.status_code)
        return 1

    login = api.login(settings.sut.username, settings.sut.password)
    if login.status_code != 200:
        log.error("Demo customer is not usable after reset: login returned %d",
                  login.status_code)
        return 1

    customer = json_body(login)
    accounts = json_body(api.customer_accounts(customer["id"]))
    log.info("Reset complete: customer %s has %d account(s)", customer["id"], len(accounts))
    return 0


if __name__ == "__main__":
    sys.exit(main())
