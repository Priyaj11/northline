"""Extraction and data integrity tests.

Covers TC-DATA-001 and TC-ACCT-005.

The question this suite answers is whether the certification data store is a
faithful copy of what the source system reports. Everything downstream, the
transaction correctness checks and the whole reconciliation engine, is built on
that assumption, so it is checked directly rather than assumed.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import pytest

from database.warehouse import Warehouse
from utils.api_client import ApiClient
from utils.assertions import json_body

pytestmark = pytest.mark.database

EARLIEST_PLAUSIBLE = datetime(1990, 1, 1, tzinfo=timezone.utc)
LATEST_PLAUSIBLE = datetime(2100, 1, 1, tzinfo=timezone.utc)


def test_the_schema_creates_the_expected_tables(warehouse: Warehouse):
    """TC-DATA-001 / REQ-DATA-001, the precondition for everything else."""
    tables = warehouse.table_names()
    for expected in ("accounts", "transactions", "extraction_runs"):
        assert expected in tables, f"Table '{expected}' missing. Found: {tables}"


def test_every_account_from_the_source_is_in_the_store(
    extracted: Warehouse, source_accounts: list[dict[str, Any]]
):
    """TC-DATA-001 / REQ-DATA-001."""
    in_store = set(extracted.balances())
    at_source = {a["id"] for a in source_accounts}
    assert in_store == at_source, (
        "The store and the source disagree about which accounts exist.\n"
        f"  only in store:  {sorted(in_store - at_source)}\n"
        f"  only at source: {sorted(at_source - in_store)}"
    )


def test_every_stored_balance_matches_the_source(
    extracted: Warehouse, source_accounts: list[dict[str, Any]]
):
    """TC-ACCT-005 / REQ-ACCT-003.

    Compared as Decimal on both sides. The store column is NUMERIC(15,2), which
    psycopg returns as a Decimal, so a one cent difference is caught rather than
    absorbed by floating point.
    """
    stored = extracted.balances()
    mismatches = {
        a["id"]: (stored.get(a["id"]), Decimal(str(a["balance"])))
        for a in source_accounts
        if stored.get(a["id"]) != Decimal(str(a["balance"]))
    }
    assert not mismatches, (
        "Stored balances differ from the source:\n"
        + "\n".join(
            f"  account {aid}: store {got}, source {want}"
            for aid, (got, want) in mismatches.items()
        )
    )


def test_every_transaction_from_the_source_is_in_the_store(
    extracted: Warehouse, api: ApiClient, source_accounts: list[dict[str, Any]]
):
    """TC-DATA-001 / REQ-DATA-001. A missing transaction would make every
    reconciliation result wrong in a way that looks like a source system fault."""
    at_source: set[int] = set()
    for account in source_accounts:
        at_source.update(t["id"] for t in json_body(api.account_transactions(account["id"])))

    in_store = {t["transaction_id"] for t in extracted.all_transactions()}
    assert in_store == at_source, (
        "The store and the source disagree about which transactions exist.\n"
        f"  only in store:  {sorted(in_store - at_source)}\n"
        f"  only at source: {sorted(at_source - in_store)}"
    )


def test_no_transaction_refers_to_a_missing_account(extracted: Warehouse):
    """REQ-DATA-001, referential integrity.

    The foreign key should make this impossible. The test asserts the constraint
    is actually doing its job rather than assuming the schema was applied as
    written.
    """
    orphans = extracted.orphan_transactions()
    assert not orphans, f"Transactions referring to accounts that do not exist: {orphans}"


def test_no_amount_carries_more_than_two_decimal_places(extracted: Warehouse):
    """REQ-DATA-001. NUMERIC(15,2) should guarantee this. Money stored with
    hidden extra precision is how a reconciliation ends up one cent out with no
    visible cause."""
    bad = extracted.amounts_with_excess_precision()
    assert not bad, f"Amounts with more than two decimal places: {bad}"


def test_stored_dates_are_plausible(extracted: Warehouse):
    """REQ-TXN-003. The source returns epoch milliseconds, which are converted
    on the way in. A conversion in the wrong unit still stores a valid timestamp,
    just one in 1970 or far in the future."""
    for txn in extracted.all_transactions():
        assert EARLIEST_PLAUSIBLE <= txn["date"] <= LATEST_PLAUSIBLE, (
            f"Transaction {txn['transaction_id']} has date {txn['date'].isoformat()}, "
            "which is outside any plausible range. The epoch conversion is probably wrong."
        )


def test_the_extraction_run_was_recorded(extracted: Warehouse):
    """REQ-DATA-001. Every row must be traceable to when it was pulled and from
    which environment, otherwise a result cannot be tied to a release."""
    with extracted.connect() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT status, account_count, transaction_count, environment, finished_at "
            "FROM extraction_runs ORDER BY run_id DESC LIMIT 1"
        )
        row = cur.fetchone()

    assert row is not None, "No extraction run was recorded"
    status, accounts, transactions, environment, finished_at = row
    assert status == "complete", f"Last extraction run status was {status!r}"
    assert accounts == extracted.account_count()
    assert transactions == extracted.transaction_count()
    assert environment, "The run did not record which environment it ran against"
    assert finished_at is not None, "The run was never marked finished"
