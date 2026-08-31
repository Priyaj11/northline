"""Data quality checks on the ledger.

These do not assert that ParaBank's seeded demo data is clean. It is not, and
that was established by experiment rather than assumed: see Observation 10 in
docs/sut-parabank.md.

They assert that testing does not INTRODUCE inconsistency. That is the part
which would be a real regression, and it is checked by taking a baseline,
performing a movement, and comparing.

This is a general pattern worth knowing. When a system under test starts from a
known-imperfect state, asserting perfection produces a permanently red suite
that everyone ignores. Asserting "no worse than the baseline" keeps the check
meaningful.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from utils.api_client import ApiClient
from utils.assertions import assert_status

pytestmark = pytest.mark.database


def test_no_new_type_description_contradiction_is_introduced(
    api: ApiClient, re_extract
):
    """REQ-TXN-003.

    A record described as received but typed as a debit contradicts itself.
    Four such records exist in the seed. This asserts that a transfer performed
    now does not add a fifth.
    """
    store = re_extract()
    baseline = {t["transaction_id"] for t in store.type_description_inconsistencies()}

    accounts = sorted(store.balances())
    source, destination = accounts[2], accounts[4]
    assert_status(api.transfer(source, destination, "42.00"), 200)

    store = re_extract()
    after = {t["transaction_id"] for t in store.type_description_inconsistencies()}

    introduced = after - baseline
    assert not introduced, (
        "A transfer introduced transactions whose type contradicts their description: "
        f"{sorted(introduced)}\n"
        + "\n".join(
            f"  {t}" for t in store.type_description_inconsistencies()
            if t["transaction_id"] in introduced
        )
    )


def test_a_transfer_writes_a_matched_debit_and_credit_pair(api: ApiClient, re_extract):
    """REQ-XFER-006. The positive form of the same check.

    Rather than only asserting that nothing got worse, this asserts what a
    correct pair looks like: a Debit described as sent on the source, and a
    Credit described as received on the destination, for the same amount.
    """
    store = re_extract()
    accounts = sorted(store.balances())
    source, destination = accounts[6], accounts[8]
    amount = Decimal("13.13")

    before_source = {t["transaction_id"] for t in store.transactions_for(source)}
    before_destination = {t["transaction_id"] for t in store.transactions_for(destination)}

    assert_status(api.transfer(source, destination, str(amount)), 200)

    store = re_extract()
    new_source = [t for t in store.transactions_for(source)
                  if t["transaction_id"] not in before_source]
    new_destination = [t for t in store.transactions_for(destination)
                       if t["transaction_id"] not in before_destination]

    assert len(new_source) == 1 and len(new_destination) == 1, (
        f"Expected one new record on each side, got {len(new_source)} and "
        f"{len(new_destination)}"
    )

    debit, credit = new_source[0], new_destination[0]
    assert debit["type"] == "Debit", f"Source record typed {debit['type']!r}, expected Debit"
    assert credit["type"] == "Credit", f"Destination record typed {credit['type']!r}, expected Credit"
    assert debit["amount"] == credit["amount"] == amount, (
        f"Debit {debit['amount']} and credit {credit['amount']} should both be {amount}"
    )


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason=(
        "DEF-001 as amended: ParaBank does not validate the transfer amount at "
        "all. A transfer of 0.00 returns 200 and writes a record on both "
        "accounts. Confirmed 2026-08-30, transactions 14920 and 15031. This "
        "test found the error in the original DEF-001 writeup, which claimed "
        "zero was rejected on the strength of an API test that asserted only "
        "that balances did not change."
    ),
)
def test_no_new_zero_amount_transaction_is_introduced(api: ApiClient, re_extract):
    """REQ-XFER-003.

    A rejected request must leave no trace. This is the assertion the API layer
    structurally cannot make: at that layer, "refused" and "accepted with no
    monetary effect" look identical, because both leave the balances unchanged.
    Only the ledger distinguishes them.
    """
    store = re_extract()
    baseline = {t["transaction_id"] for t in store.zero_amount_transactions()}

    accounts = sorted(store.balances())
    api.transfer(accounts[0], accounts[1], "0.00")

    store = re_extract()
    after = {t["transaction_id"] for t in store.zero_amount_transactions()}

    introduced = after - baseline
    assert not introduced, (
        f"A rejected zero-amount transfer still wrote transaction(s) {sorted(introduced)}"
    )
