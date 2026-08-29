"""Provision the System Under Test.

ParaBank ships with an empty database. Its schema and demo data are created by
visiting /parabank/initializeDB.htm once. Until that happens, every page fails
with an HSQLDB error saying the PARAMETER table does not exist, and
/parabank/index.htm answers 302 (a redirect to the initialisation page) rather
than 200.

The database lives inside the container with no mounted volume, so it is wiped
every time the container is recreated. Provisioning therefore has to be a
repeatable scripted step, not a manual one.

Exit code 0 means the SUT is provisioned. Exit code 1 means it is not.
"""

from __future__ import annotations

import sys
import time

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

log = get_logger("initialize_sut")

TOMCAT_TIMEOUT_SECONDS = 240
POLL_INTERVAL_SECONDS = 5


def wait_for_tomcat(home_url: str, timeout: int = TOMCAT_TIMEOUT_SECONDS) -> bool:
    """Wait until Tomcat answers at all. Any HTTP status counts as alive."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            response = requests.get(home_url, timeout=10, allow_redirects=False)
            log.info("Tomcat is serving (%s returned %d)", home_url, response.status_code)
            return True
        except requests.RequestException:
            log.info("Waiting for Tomcat to accept connections...")
            time.sleep(POLL_INTERVAL_SECONDS)
    log.error("Tomcat did not start within %d seconds", timeout)
    return False


def is_provisioned(home_url: str) -> bool:
    """Provisioned means index.htm returns 200 directly, with no redirect."""
    try:
        response = requests.get(home_url, timeout=15, allow_redirects=False)
    except requests.RequestException as exc:
        log.error("Could not reach %s: %s", home_url, exc)
        return False
    if response.status_code == 200:
        return True
    log.info("Not provisioned yet: %s returned %d", home_url, response.status_code)
    if "location" in response.headers:
        log.info("It redirects to: %s", response.headers["location"])
    return False


def provision(base_url: str) -> bool:
    """Visit the initialisation page in a single session and follow redirects."""
    init_url = f"{base_url}/initializeDB.htm"
    log.info("Provisioning via %s", init_url)
    with requests.Session() as session:
        try:
            response = session.get(init_url, timeout=180, allow_redirects=True)
        except requests.RequestException as exc:
            log.error("Provisioning request failed: %s", exc)
            return False
    log.info("Provisioning request finished with status %d", response.status_code)
    return response.status_code == 200


def admin_page_works(base_url: str) -> bool:
    """The admin page reads the Parameter table, so a 200 proves the schema exists."""
    admin_url = f"{base_url}/admin.htm"
    try:
        response = requests.get(admin_url, timeout=30)
    except requests.RequestException as exc:
        log.error("Could not reach %s: %s", admin_url, exc)
        return False
    if response.status_code == 200:
        log.info("Admin page returned 200, so the database schema exists")
        return True
    log.error("Admin page returned %d, so the schema is still missing", response.status_code)
    return False


def main() -> int:
    settings = get_settings()
    base_url = settings.sut.base_url
    home_url = settings.sut.home_url

    if not wait_for_tomcat(home_url):
        return 1

    if is_provisioned(home_url):
        log.info("SUT already provisioned, nothing to do")
    else:
        if not provision(base_url):
            log.error("Provisioning failed")
            return 1
        if not is_provisioned(home_url):
            log.error("Provisioning ran but %s still does not return 200", home_url)
            return 1
        log.info("SUT provisioned")

    if not admin_page_works(base_url):
        return 1

    log.info("SUT READY")
    return 0


if __name__ == "__main__":
    sys.exit(main())
