"""Fixtures for the database suite.

Every test in this suite runs against a freshly extracted store, so that a
result never depends on what a previous test left behind.
"""

from __future__ import annotations

from typing import Any

import pytest

from database.warehouse import Warehouse
from utils.api_client import ApiClient
from utils.assertions import json_body
from utils.config import Settings


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


@pytest.fixture(scope="session")
def extracted(warehouse: Warehouse, api: ApiClient, source_customer_id: int):
    """Run a full extraction once for this suite, and return the store.

    Session scoped because extraction is the slow part and every test in the
    suite reads the same snapshot. Tests that change money re-extract
    explicitly rather than relying on this one.
    """
    warehouse.clear()
    run_id = warehouse.start_run()
    accounts = json_body(api.customer_accounts(source_customer_id))
    warehouse.upsert_accounts(accounts, run_id)
    total = 0
    for account in accounts:
        total += warehouse.upsert_transactions(
            json_body(api.account_transactions(account["id"])), run_id
        )
    warehouse.finish_run(run_id, len(accounts), total)
    return warehouse


@pytest.fixture
def re_extract(warehouse: Warehouse, api: ApiClient, source_customer_id: int):
    """Re-run the extraction on demand and return the refreshed store.

    Tests that move money need a snapshot taken after the movement. Returning a
    callable rather than a value makes the moment of extraction explicit in the
    test, which matters when the whole point is comparing before and after.
    """
    def _run() -> Warehouse:
        warehouse.clear()
        run_id = warehouse.start_run()
        accounts = json_body(api.customer_accounts(source_customer_id))
        warehouse.upsert_accounts(accounts, run_id)
        total = 0
        for account in accounts:
            total += warehouse.upsert_transactions(
                json_body(api.account_transactions(account["id"])), run_id
            )
        warehouse.finish_run(run_id, len(accounts), total)
        return warehouse
    return _run
