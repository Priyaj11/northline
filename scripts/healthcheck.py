"""Environment readiness check for Northline.

Liveness versus readiness:

  Liveness  - the process is running and answering on its port.
  Readiness - the application is actually usable.

Docker's healthcheck in docker-compose.yml checks liveness: Tomcat is serving.
This script checks readiness, which is a much stronger claim:

  1. ParaBank's home page returns 200 with NO redirect. A 302 means the
     database has not been initialised and the app is redirecting to its
     own setup page.
  2. ParaBank's admin page returns 200. That page reads the Parameter table,
     so a 200 proves the database schema exists.
  3. The PostgreSQL certification data store accepts a connection.

This distinction matters. During Phase 1 the container reported "healthy" for
nine minutes while every single page was failing with a database error,
because the liveness check accepted a redirect as success.

Exit code 0 means ready. Exit code 1 means not ready.
"""

from __future__ import annotations

import sys
import time
from datetime import datetime, timezone

import requests

import sys
from pathlib import Path

# Scripts are executed as files, not imported as modules, so Python puts the
# scripts/ folder on the import path rather than the repository root. Adding the
# repository root explicitly lets "from utils.config import ..." resolve no
# matter which directory the script is run from.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


from utils.config import get_settings
from utils.logger import get_logger

log = get_logger("healthcheck")

SUT_TIMEOUT_SECONDS = 180
POLL_INTERVAL_SECONDS = 5


def check_sut_ready(base_url: str, home_url: str, timeout: int = SUT_TIMEOUT_SECONDS) -> bool:
    deadline = time.time() + timeout
    attempt = 0
    while time.time() < deadline:
        attempt += 1
        try:
            response = requests.get(home_url, timeout=10, allow_redirects=False)
            if response.status_code == 200:
                log.info("Home page returned 200 after %d attempt(s)", attempt)
                break
            if response.status_code in (301, 302, 303, 307, 308):
                log.error(
                    "Home page returned %d redirecting to %s. "
                    "The SUT database is probably not initialised. "
                    "Run: python scripts/initialize_sut.py",
                    response.status_code,
                    response.headers.get("location", "unknown"),
                )
                return False
            log.info("Attempt %d: home page returned %d", attempt, response.status_code)
        except requests.RequestException as exc:
            log.info("Attempt %d: not reachable yet (%s)", attempt, exc.__class__.__name__)
        time.sleep(POLL_INTERVAL_SECONDS)
    else:
        log.error("SUT did not become ready within %d seconds", timeout)
        return False

    admin_url = f"{base_url}/admin.htm"
    try:
        admin = requests.get(admin_url, timeout=30)
    except requests.RequestException as exc:
        log.error("Could not reach %s: %s", admin_url, exc)
        return False
    if admin.status_code != 200:
        log.error(
            "Admin page returned %d. The database schema is missing. "
            "Run: python scripts/initialize_sut.py",
            admin.status_code,
        )
        return False

    log.info("SUT is ready: home page 200, admin page 200")
    return True


def check_warehouse(dsn: str) -> bool:
    """Open a connection to PostgreSQL and run the cheapest possible query."""
    try:
        import psycopg
    except ImportError:
        log.error("psycopg is not installed. Run: pip install -r requirements.txt")
        return False

    try:
        with psycopg.connect(dsn, connect_timeout=10) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
        log.info("Certification data store is up: SELECT 1 succeeded")
        return True
    except Exception as exc:  # noqa: BLE001 - we want the reason in the log
        log.error("Certification data store is not reachable: %s", exc)
        return False


def main() -> int:
    settings = get_settings()
    log.info("Environment: %s", settings.environment)
    log.info("Checking SUT readiness at %s", settings.sut.base_url)
    sut_ok = check_sut_ready(settings.sut.base_url, settings.sut.home_url)
    log.info("Checking certification data store at %s:%s", settings.warehouse.host, settings.warehouse.port)
    warehouse_ok = check_warehouse(settings.warehouse.dsn)

    ready = sut_ok and warehouse_ok

    # Record the verdict so the certification engine has evidence for GATE-ENV.
    # Without a file, that gate reports "no evidence" and blocks the release,
    # which is the correct behaviour: a release must not be certified when
    # nobody can show the environment was fit to test.
    import json
    record = {
        "ready": ready,
        "sut_ok": sut_ok,
        "warehouse_ok": warehouse_ok,
        "environment": settings.environment,
        "checked_at": datetime.now(tz=timezone.utc).isoformat(),
    }
    (settings.reports_dir / "environment.json").write_text(json.dumps(record, indent=2))

    if ready:
        log.info("ENVIRONMENT READY")
        return 0
    log.error("ENVIRONMENT NOT READY (sut_ok=%s, warehouse_ok=%s)", sut_ok, warehouse_ok)
    return 1


if __name__ == "__main__":
    sys.exit(main())
