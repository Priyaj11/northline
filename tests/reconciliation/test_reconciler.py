"""Fault injection tests for the reconciliation engine.

Covers TC-DATA-003 and TC-DATA-004.

These are the most important tests in the project, and they are the ones people
usually forget to write. A reconciler that has only ever been run against
matching data proves nothing at all: an engine that always returns "pass" would
pass that test too.

So every break type is injected deliberately and the engine must find exactly
that break and nothing else. The "and nothing else" half matters as much as the
first: a reconciler that reports six breaks when one exists is as useless as one
that reports none, because nobody can act on it.

These tests are pure functions over lists, with no database and no network, so
they run in milliseconds and can be exhaustive.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from reconciliation.models import BreakKind, SettlementRecord
from reconciliation.reconciler import reconcile

pytestmark = pytest.mark.reconciliation

WHEN = datetime(2026, 8, 30, 12, 0, tzinfo=timezone.utc)


def record(transaction_id: int, account_id: int, amount: str,
           kind: str = "Debit") -> SettlementRecord:
    return SettlementRecord(
        transaction_id=transaction_id,
        account_id=account_id,
        amount=Decimal(amount),
        transaction_type=kind,
        timestamp=WHEN,
    )


@pytest.fixture
def ledger() -> list[SettlementRecord]:
    return [
        record(1001, 12345, "100.00", "Debit"),
        record(1002, 12456, "100.00", "Credit"),
        record(1003, 12567, "42.00", "Debit"),
        record(1004, 12789, "42.00", "Credit"),
        record(1005, 13011, "1000.00", "Debit"),
    ]


def test_identical_data_reconciles_cleanly(ledger):
    """TC-DATA-004. The baseline. If this fails nothing else means anything."""
    report = reconcile(ledger, list(ledger))
    assert report.passed, f"Identical data produced breaks: {[str(b) for b in report.breaks]}"
    assert report.status == "pass"
    assert report.matched == 5
    assert report.ledger_count == 5
    assert report.settlement_count == 5


def test_a_missing_record_is_detected(ledger):
    """TC-DATA-003. A transaction the bank recorded but never sent onward."""
    settlement = [r for r in ledger if r.transaction_id != 1003]

    report = reconcile(ledger, settlement)

    assert not report.passed
    missing = report.of_kind(BreakKind.MISSING)
    assert len(missing) == 1, f"Expected exactly one missing break, got {report.counts()}"
    assert missing[0].transaction_id == 1003
    assert missing[0].account_id == 12567
    assert len(report.breaks) == 1, (
        f"Expected only the missing break, also got: "
        f"{[str(b) for b in report.breaks if b.kind is not BreakKind.MISSING]}"
    )
    assert report.matched == 4


def test_a_duplicate_record_is_detected(ledger):
    """TC-DATA-003. The same transaction sent twice, which double counts money."""
    settlement = list(ledger) + [record(1002, 12456, "100.00", "Credit")]

    report = reconcile(ledger, settlement)

    assert not report.passed
    duplicates = report.of_kind(BreakKind.DUPLICATE)
    assert len(duplicates) == 1, f"Expected exactly one duplicate break, got {report.counts()}"
    assert duplicates[0].transaction_id == 1002
    assert "2 times" in duplicates[0].detail
    assert len(report.breaks) == 1
    assert report.matched == 4, "The duplicated record must not count as matched"


def test_an_amount_mismatch_is_detected(ledger):
    """TC-DATA-003. One cent, deliberately.

    A reconciler that only catches large differences is worthless. The realistic
    failure is a rounding error or a currency conversion, and those are small.
    """
    settlement = [r for r in ledger if r.transaction_id != 1004]
    settlement.append(record(1004, 12789, "42.01", "Credit"))

    report = reconcile(ledger, settlement)

    assert not report.passed
    mismatches = report.of_kind(BreakKind.AMOUNT_MISMATCH)
    assert len(mismatches) == 1, f"Expected exactly one amount break, got {report.counts()}"
    assert mismatches[0].transaction_id == 1004
    assert "42.01" in mismatches[0].detail and "42.00" in mismatches[0].detail
    assert len(report.breaks) == 1
    assert report.matched == 4


def test_an_account_mismatch_is_detected(ledger):
    """TC-DATA-003. Money posted to the wrong real account.

    Another valid account identifier is used rather than a nonsense value,
    because the realistic failure is a transaction landing on somebody else's
    account, not on an account that does not exist.
    """
    settlement = [r for r in ledger if r.transaction_id != 1005]
    settlement.append(record(1005, 13122, "1000.00", "Debit"))

    report = reconcile(ledger, settlement)

    assert not report.passed
    mismatches = report.of_kind(BreakKind.ACCOUNT_MISMATCH)
    assert len(mismatches) == 1, f"Expected exactly one account break, got {report.counts()}"
    assert mismatches[0].transaction_id == 1005
    assert "13122" in mismatches[0].detail and "13011" in mismatches[0].detail
    assert len(report.breaks) == 1
    assert report.matched == 4


def test_an_unexpected_record_is_detected(ledger):
    """TC-DATA-003. Money reported that the bank has no record of."""
    settlement = list(ledger) + [record(9999, 12345, "500.00", "Credit")]

    report = reconcile(ledger, settlement)

    assert not report.passed
    unexpected = report.of_kind(BreakKind.UNEXPECTED)
    assert len(unexpected) == 1, f"Expected exactly one unexpected break, got {report.counts()}"
    assert unexpected[0].transaction_id == 9999
    assert len(report.breaks) == 1
    assert report.matched == 5, "Every genuine record still matched"


def test_several_break_types_are_reported_together(ledger):
    """TC-DATA-004. A real reconciliation break is rarely alone.

    All four injected at once. Each must be reported once and correctly, because
    a report that stops at the first problem hides the rest.
    """
    settlement = [r for r in ledger if r.transaction_id not in (1003, 1004, 1005)]
    settlement.append(record(1004, 12789, "42.01", "Credit"))   # amount
    settlement.append(record(1005, 13122, "1000.00", "Debit"))  # account
    settlement.append(record(1002, 12456, "100.00", "Credit"))  # duplicate
    # 1003 simply absent                                         # missing

    report = reconcile(ledger, settlement)

    counts = report.counts()
    assert counts["missing"] == 1, counts
    assert counts["duplicate"] == 1, counts
    assert counts["amount_mismatch"] == 1, counts
    assert counts["account_mismatch"] == 1, counts
    assert counts["unexpected"] == 0, counts
    assert len(report.breaks) == 4
    assert report.status == "fail"


def test_amount_and_account_can_both_be_wrong_on_one_record(ledger):
    """TC-DATA-004. One record, two problems. Both must be reported, because a
    person fixing only the amount would still leave money on the wrong account."""
    settlement = [r for r in ledger if r.transaction_id != 1001]
    settlement.append(record(1001, 13122, "99.99", "Debit"))

    report = reconcile(ledger, settlement)

    assert len(report.of_kind(BreakKind.AMOUNT_MISMATCH)) == 1
    assert len(report.of_kind(BreakKind.ACCOUNT_MISMATCH)) == 1
    assert len(report.breaks) == 2
    assert report.matched == 4


def test_an_empty_settlement_file_reports_every_record_as_missing(ledger):
    """TC-DATA-003. The catastrophic case: the file never arrived, or arrived
    empty. Every record must be reported, not a single summary line."""
    report = reconcile(ledger, [])
    assert len(report.of_kind(BreakKind.MISSING)) == len(ledger)
    assert report.matched == 0
    assert report.status == "fail"


def test_the_engine_refuses_amounts_that_are_not_decimal():
    """A float amount is rejected at construction rather than silently compared.

    0.1 + 0.2 does not equal 0.3 in floating point. A reconciler that accepts
    floats reports breaks that do not exist and misses ones that do.
    """
    with pytest.raises(TypeError, match="must be Decimal"):
        SettlementRecord(
            transaction_id=1,
            account_id=2,
            amount=42.00,  # a float, deliberately
            transaction_type="Debit",
            timestamp=WHEN,
        )
