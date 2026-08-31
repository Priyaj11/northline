"""Fixtures shared by the API suite.

Account identifiers are read at runtime rather than hard coded, following
docs/test-data-strategy.md. Hard-coded identifiers break the moment the seeded
data changes, and ParaBank's data is recreated on every container restart.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from utils.api_client import ApiClient
from utils.assertions import json_body
from utils.config import Settings


@pytest.fixture(scope="session")
def customer_id(api: ApiClient, settings: Settings) -> int:
    """The demo customer's identifier, read from the login response."""
    body = json_body(api.login(settings.sut.username, settings.sut.password))
    assert isinstance(body, dict) and "id" in body, (
        f"Login did not return a customer record with an id. Got: {body!r}"
    )
    return body["id"]


@pytest.fixture(scope="session")
def accounts(api: ApiClient, customer_id: int) -> list[dict[str, Any]]:
    """Every account belonging to the demo customer."""
    body = json_body(api.customer_accounts(customer_id))
    assert isinstance(body, list) and body, "Expected a non-empty list of accounts"
    return body


@pytest.fixture(scope="session")
def account_pair(accounts: list[dict[str, Any]]) -> tuple[int, int]:
    """Two distinct account identifiers to move money between."""
    ids = [a["id"] for a in accounts]
    assert len(ids) >= 2, f"Need at least two accounts, found {len(ids)}"
    return ids[0], ids[1]


@pytest.fixture
def balance_of(api: ApiClient):
    """Read one account's balance as a Decimal.

    Decimal rather than float, because floating point cannot represent 0.01
    exactly. Asserting money with floats produces failures that look like
    defects and are not, and hides real one-cent errors that are.
    """
    def _read(account_id: int) -> Decimal:
        body = json_body(api.account(account_id))
        return Decimal(str(body["balance"]))
    return _read


@pytest.fixture
def reset_sut_after(api: ApiClient):
    """Reset the application's data after the test, whatever happens.

    Needed by TC-XFER-010, which triggers DEF-007: the transfer it performs
    leaves accounts the application cannot read, so every test running
    afterwards fails on unrelated account reads.

    A test that corrupts the environment must clean up after itself. Without
    this, one deliberate boundary case makes the rest of the suite report
    failures that have nothing to do with what they were testing, which is
    exactly the confusion this defect caused when it was first hit.
    """
    yield
    api.clean_db()
    api.initialize_db()
