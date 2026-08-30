"""API account tests.

Covers TC-ACCT-002 and TC-ACCT-004.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from utils.api_client import ApiClient
from utils.assertions import assert_client_error, assert_fields, json_body

pytestmark = pytest.mark.api

NON_EXISTENT_ACCOUNT = 99999999


def test_customer_accounts_returns_a_list(accounts: list[dict[str, Any]]):
    """TC-ACCT-002 / REQ-ACCT-001."""
    assert len(accounts) >= 1, "The demo customer should own at least one account"


def test_every_account_has_the_expected_fields_and_types(accounts: list[dict[str, Any]]):
    """TC-ACCT-002 / REQ-ACCT-001.

    Types matter as much as presence. A balance returned as a string would pass
    a 'field exists' check and break every arithmetic assertion downstream.
    """
    for account in accounts:
        assert_fields(
            account,
            {"id": int, "customerId": int, "type": str, "balance": (int, float)},
            f"account {account.get('id')}",
        )


def test_every_account_belongs_to_the_requested_customer(
    accounts: list[dict[str, Any]], customer_id: int
):
    """REQ-ACCT-001. A list containing another customer's account would be a
    serious authorisation defect, not merely a wrong result."""
    for account in accounts:
        assert account["customerId"] == customer_id, (
            f"Account {account['id']} belongs to customer {account['customerId']}, "
            f"not the requested customer {customer_id}"
        )


def test_account_detail_matches_the_account_list(
    api: ApiClient, accounts: list[dict[str, Any]]
):
    """TC-ACCT-002 / REQ-ACCT-002. Two routes to the same fact must agree."""
    listed = accounts[0]
    detail = json_body(api.account(listed["id"]))
    assert_fields(
        detail,
        {"id": int, "customerId": int, "type": str, "balance": (int, float)},
        f"account detail {listed['id']}",
    )
    assert detail["id"] == listed["id"]
    assert detail["customerId"] == listed["customerId"]
    assert detail["type"] == listed["type"]
    assert Decimal(str(detail["balance"])) == Decimal(str(listed["balance"])), (
        f"Account {listed['id']} balance differs between the list "
        f"({listed['balance']}) and the detail ({detail['balance']})"
    )


def test_a_non_existent_account_returns_a_client_error(api: ApiClient):
    """TC-ACCT-004 / REQ-ACCT-002.

    A 4xx means the application rejected the request. A 5xx would mean it
    crashed, which is a defect in error handling rather than correct refusal.
    """
    assert_client_error(api.account(NON_EXISTENT_ACCOUNT))
