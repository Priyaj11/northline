"""API transaction history tests.

Covers TC-TXN-002 and TC-TXN-004.

Phase 3A discovery established that the date field is an integer, not a string.
That is almost certainly epoch milliseconds, the standard Java timestamp
representation, so these tests assert on that rather than on a parseable date
string.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import pytest

from utils.api_client import ApiClient
from utils.assertions import assert_fields, json_body

pytestmark = pytest.mark.api

# Any transaction in a banking system should fall between these two dates.
# Wide enough never to fail on legitimate data, narrow enough to catch a value
# in the wrong unit, which is the actual failure mode: seconds interpreted as
# milliseconds lands in 1970, and milliseconds read as seconds lands far future.
EARLIEST_PLAUSIBLE = datetime(1990, 1, 1, tzinfo=timezone.utc)
LATEST_PLAUSIBLE = datetime(2100, 1, 1, tzinfo=timezone.utc)


@pytest.fixture(scope="module")
def transactions(api: ApiClient, accounts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Transactions from the first account that has any."""
    for account in accounts:
        body = json_body(api.account_transactions(account["id"]))
        if isinstance(body, list) and body:
            return body
    pytest.skip("No account in the seeded data has any transactions")


def test_transaction_records_have_the_expected_fields_and_types(
    transactions: list[dict[str, Any]]
):
    """TC-TXN-004 / REQ-TXN-003."""
    for txn in transactions:
        assert_fields(
            txn,
            {
                "id": int,
                "accountId": int,
                "type": str,
                "date": int,
                "amount": (int, float),
                "description": str,
            },
            f"transaction {txn.get('id')}",
        )


def test_transaction_dates_are_plausible_epoch_milliseconds(
    transactions: list[dict[str, Any]]
):
    """TC-TXN-004 / REQ-TXN-003.

    The field is numeric, so the only meaningful check is whether the number
    converts to a sensible date. A timestamp in the wrong unit still passes a
    type check and still produces a statement dated 1970.
    """
    for txn in transactions:
        when = datetime.fromtimestamp(txn["date"] / 1000, tz=timezone.utc)
        assert EARLIEST_PLAUSIBLE <= when <= LATEST_PLAUSIBLE, (
            f"Transaction {txn['id']} has date {txn['date']}, which reads as {when.isoformat()}. "
            "That is outside any plausible range, so the value is probably in the wrong unit."
        )


def test_every_transaction_belongs_to_the_requested_account(
    api: ApiClient, accounts: list[dict[str, Any]]
):
    """REQ-TXN-001. A history containing another account's transactions would
    be both a correctness and a confidentiality problem."""
    for account in accounts:
        body = json_body(api.account_transactions(account["id"]))
        for txn in body:
            assert txn["accountId"] == account["id"], (
                f"History for account {account['id']} contains transaction "
                f"{txn['id']} belonging to account {txn['accountId']}"
            )


def test_filtering_transactions_by_amount_returns_only_that_amount(
    api: ApiClient, transactions: list[dict[str, Any]]
):
    """TC-TXN-002 / REQ-TXN-002."""
    sample = transactions[0]
    amount = Decimal(str(sample["amount"]))
    response = api.get(f"/accounts/{sample['accountId']}/transactions/amount/{amount}")
    body = json_body(response)
    assert isinstance(body, list), f"Expected a list, got {type(body).__name__}"
    assert body, f"Filtering by an amount known to exist ({amount}) returned nothing"
    for txn in body:
        assert Decimal(str(txn["amount"])) == amount, (
            f"Filter for {amount} returned transaction {txn['id']} of {txn['amount']}"
        )
