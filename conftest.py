"""Shared pytest fixtures for the whole Northline suite.

pytest discovers this file automatically, so any test can request `settings`,
`api` or `extracted` without importing anything. It sits at the repository root
so it applies to every suite under tests/.

The warehouse fixtures live here rather than under tests/database/ because both
the database suite and the reconciliation suite read the same extracted ledger.
A fixture in a subfolder's conftest is invisible to sibling folders.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from database.warehouse import Warehouse
from utils.api_client import ApiClient
from utils.assertions import json_body
from utils.config import Settings, get_settings
from utils.logger import get_logger

log = get_logger("conftest")


@pytest.fixture(scope="session")
def settings() -> Settings:
    """Configuration, read once per test run."""
    return get_settings()


@pytest.fixture(scope="session")
def api(settings: Settings) -> ApiClient:
    """A logged HTTP client for ParaBank's REST services.

    Session scoped because the client holds no per-test state. Any test that
    needs a clean cookie jar clears it explicitly, which makes that intent
    visible rather than accidental.
    """
    return ApiClient(settings)


@pytest.fixture(scope="session")
def artifacts_dir(settings: Settings) -> Path:
    """Where screenshots, traces and videos from failed tests are written."""
    return settings.artifacts_dir


@pytest.fixture(scope="session")
def warehouse(settings: Settings) -> Warehouse:
    store = Warehouse(settings)
    store.apply_schema()
    return store


@pytest.fixture(scope="session")
def source_customer_id(api: ApiClient, settings: Settings) -> int:
    return json_body(api.login(settings.sut.username, settings.sut.password))["id"]


@pytest.fixture(scope="session")
def source_accounts(api: ApiClient, source_customer_id: int) -> list[dict[str, Any]]:
    return json_body(api.customer_accounts(source_customer_id))


def _extract(warehouse: Warehouse, api: ApiClient, customer_id: int) -> Warehouse:
    warehouse.clear()
    run_id = warehouse.start_run()
    accounts = json_body(api.customer_accounts(customer_id))
    warehouse.upsert_accounts(accounts, run_id)
    total = 0
    for account in accounts:
        total += warehouse.upsert_transactions(
            json_body(api.account_transactions(account["id"])), run_id
        )
    warehouse.finish_run(run_id, len(accounts), total)
    return warehouse


@pytest.fixture(scope="session")
def extracted(warehouse: Warehouse, api: ApiClient, source_customer_id: int) -> Warehouse:
    """Run a full extraction once and return the store.

    Session scoped because extraction is the slow part and most tests read the
    same snapshot. Tests that change money use re_extract instead.
    """
    return _extract(warehouse, api, source_customer_id)


@pytest.fixture
def re_extract(warehouse: Warehouse, api: ApiClient, source_customer_id: int):
    """Re-run the extraction on demand and return the refreshed store.

    Tests that move money need a snapshot taken after the movement. Returning a
    callable rather than a value makes the moment of extraction explicit in the
    test, which matters when the whole point is comparing before and after.
    """
    def _run() -> Warehouse:
        return _extract(warehouse, api, source_customer_id)
    return _run


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Record each test's result on the item itself.

    Fixtures cannot normally see whether the test that used them passed or
    failed. Stashing the report here lets teardown code capture artifacts only
    on failure, instead of writing a screenshot for every passing test and
    filling the disk with pictures of things that worked.
    """
    outcome = yield
    report = outcome.get_result()
    setattr(item, f"report_{report.when}", report)


def pytest_configure(config):
    """Log the environment once at the start of the run."""
    s = get_settings()
    log.info("Northline run | environment=%s | release=%s | SUT=%s",
             s.environment, s.release, s.sut.base_url)
