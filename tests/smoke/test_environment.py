"""Phase 1 smoke tests.

These are deliberately the smallest useful tests in the whole framework.
They answer one question: is the environment fit to test at all?
If these fail, nothing else in Northline is trustworthy.

REQ-ENV-002 exists because of a real Phase 1 finding. ParaBank answers 302 and
redirects to its own database initialisation page when it has not been seeded.
A test that allowed redirects would have passed against a completely broken
application.
"""

from __future__ import annotations

import pytest
import requests

from utils.config import get_settings

settings = get_settings()


@pytest.mark.smoke
def test_sut_home_page_is_served():
    """REQ-ENV-001: the ParaBank home page must be reachable."""
    response = requests.get(settings.sut.home_url, timeout=15)
    assert response.status_code == 200, (
        f"Expected 200 from {settings.sut.home_url}, got {response.status_code}"
    )


@pytest.mark.smoke
def test_sut_home_page_does_not_redirect_to_initialisation():
    """REQ-ENV-002: the home page must return 200 directly, not redirect to setup."""
    response = requests.get(settings.sut.home_url, timeout=15, allow_redirects=False)
    assert response.status_code == 200, (
        f"Expected 200 with no redirect, got {response.status_code} "
        f"(location: {response.headers.get('location', 'none')}). "
        "The SUT database is probably not initialised. "
        "Run: python scripts/initialize_sut.py"
    )


@pytest.mark.smoke
def test_sut_home_page_looks_like_parabank():
    """REQ-ENV-003: the served page must be ParaBank, not a default Tomcat page."""
    response = requests.get(settings.sut.home_url, timeout=15)
    assert "ParaBank" in response.text, "Home page did not contain the text 'ParaBank'"


@pytest.mark.smoke
def test_sut_database_schema_exists():
    """REQ-ENV-004: the admin page reads the Parameter table, so 200 proves the schema."""
    response = requests.get(f"{settings.sut.base_url}/admin.htm", timeout=30)
    assert response.status_code == 200, (
        f"Admin page returned {response.status_code}. The SUT database schema is missing."
    )


@pytest.mark.smoke
def test_certification_data_store_accepts_connections():
    """REQ-ENV-005: the PostgreSQL certification data store must accept a connection."""
    psycopg = pytest.importorskip("psycopg")
    with psycopg.connect(settings.warehouse.dsn, connect_timeout=10) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            assert cur.fetchone()[0] == 1
