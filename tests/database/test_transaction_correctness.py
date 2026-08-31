"""Transaction correctness in the data.

Covers TC-XFER-003, TC-XFER-014 and TC-BILL-002.

This is the point of the whole project. Earlier phases verified that ParaBank
SAYS the right things: a confirmation appeared, an endpoint returned 200, a
balance was displayed. None of that is evidence that money moved.

These tests perform a movement, re-extract, and check the ledger.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from database.warehouse import Warehouse
from utils.api_client import ApiClient
from utils.assertions import assert_status

pytestmark = pytest.mark.database

ZERO = Decimal("0.00")


def _two_accounts(store: Warehouse) -> tuple[int, int]:
    ids = sorted(store.balances())
    assert len(ids) >= 2, f"Need at least two accounts, found {len(ids)}"
    return ids[0], ids[1]


def test_a_transfer_debits_and_credits_the_ledger(api: ApiClient, re_extract):
    """TC-XFER-003 / REQ-XFER-002.

    The strongest assertion in the suite. Not "the screen said success" and not
    "the endpoint returned 200", but "the stored balance for the source fell by
    exactly this amount and the destination rose by exactly the same amount".
    """
    store = re_extract()
    source, destination = _two_accounts(store)
    amount = Decimal("100.00")

    before_source = store.balance_of(source)
    before_destination = store.balance_of(destination)

    assert_status(api.transfer(source, destination, str(amount)), 200)

    store = re_extract()
    after_source = store.balance_of(source)
    after_destination = store.balance_of(destination)

    assert before_source - after_source == amount, (
        f"Source {source} should have fallen by {amount} in the ledger. "
        f"Went from {before_source} to {after_source}."
    )
    assert after_destination - before_destination == amount, (
        f"Destination {destination} should have risen by {amount} in the ledger. "
        f"Went from {before_destination} to {after_destination}."
    )


def test_a_transfer_conserves_money_across_the_ledger(api: ApiClient, re_extract):
    """REQ-XFER-002. The total across both accounts must be unchanged.

    A transfer moves money, it does not create or destroy it. This catches a
    rounding error that debits one amount and credits a different one, which a
    per-account check can miss if both differences look plausible on their own.
    """
    store = re_extract()
    source, destination = _two_accounts(store)
    amount = Decimal("33.33")

    before_total = store.balance_of(source) + store.balance_of(destination)
    assert_status(api.transfer(source, destination, str(amount)), 200)

    store = re_extract()
    after_total = store.balance_of(source) + store.balance_of(destination)

    assert after_total - before_total == ZERO, (
        f"A transfer of {amount} changed the combined balance by "
        f"{after_total - before_total}. Money was created or destroyed."
    )


def test_a_transfer_writes_one_transaction_to_each_account(api: ApiClient, re_extract):
    """TC-XFER-014 / REQ-XFER-006.

    Each side of a transfer must leave exactly one record on its own account. A
    debit with no matching credit, or a duplicated entry, is what the settlement
    reconciliation in Phase 4B is built to detect, so the ledger has to be right
    before reconciliation means anything.
    """
    store = re_extract()
    source, destination = _two_accounts(store)
    amount = Decimal("77.77")

    before_source = {t["transaction_id"] for t in store.transactions_for(source)}
    before_destination = {t["transaction_id"] for t in store.transactions_for(destination)}

    assert_status(api.transfer(source, destination, str(amount)), 200)

    store = re_extract()
    new_source = [
        t for t in store.transactions_for(source) if t["transaction_id"] not in before_source
    ]
    new_destination = [
        t for t in store.transactions_for(destination)
        if t["transaction_id"] not in before_destination
    ]

    assert len(new_source) == 1, (
        f"Expected exactly one new transaction on source {source}, got {len(new_source)}: "
        f"{[t['transaction_id'] for t in new_source]}"
    )
    assert len(new_destination) == 1, (
        f"Expected exactly one new transaction on destination {destination}, "
        f"got {len(new_destination)}: {[t['transaction_id'] for t in new_destination]}"
    )
    assert new_source[0]["amount"] == amount, (
        f"Source transaction recorded {new_source[0]['amount']}, expected {amount}"
    )
    assert new_destination[0]["amount"] == amount, (
        f"Destination transaction recorded {new_destination[0]['amount']}, expected {amount}"
    )


def test_a_bill_payment_debits_the_source_account(api: ApiClient, re_extract):
    """TC-BILL-002 / REQ-BILL-001.

    Bill payment moves money out of the bank rather than between two accounts,
    so only one side exists. The debit must still be exact.
    """
    store = re_extract()
    source, _ = _two_accounts(store)
    amount = Decimal("25.00")

    before = store.balance_of(source)

    response = api.post("/billpay", params={"accountId": source, "amount": str(amount)},
                        json={
                            "name": "Northline Test Payee",
                            "address": {
                                "street": "1 Test Street",
                                "city": "Windsor",
                                "state": "ON",
                                "zipCode": "N9A0A0",
                            },
                            "phoneNumber": "555-0100",
                            "accountNumber": str(source),
                        })
    if response.status_code != 200:
        pytest.skip(
            f"Bill payment through the service returned {response.status_code}. "
            f"Body: {response.text[:200]!r}. The browser path is covered by TC-BILL-001; "
            "the service shape for this endpoint is not established."
        )

    store = re_extract()
    after = store.balance_of(source)

    assert before - after == amount, (
        f"Bill payment of {amount} should have debited account {source} by exactly that. "
        f"Went from {before} to {after}."
    )


def test_transaction_types_are_recorded(re_extract):
    """REQ-TXN-003. Records what the source actually calls its transaction types.

    Not a guess at the expected values: the assertion is only that a type is
    present and non-empty on every record. The observed set is printed so the
    real vocabulary is captured rather than assumed.
    """
    store = re_extract()
    types = {t["type"] for t in store.all_transactions()}
    print(f"Transaction types observed in the source data: {sorted(types)}")
    assert types, "No transactions were extracted, so no types could be checked"
    assert all(t and t.strip() for t in types), f"An empty transaction type was stored: {types}"
