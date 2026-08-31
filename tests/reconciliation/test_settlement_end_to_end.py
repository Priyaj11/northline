"""End to end settlement reconciliation against the real ledger.

Covers TC-DATA-002 and TC-DATA-004.

The engine tests in test_reconciler.py prove the comparison logic with
synthetic data. These prove the whole path: extract from the source, generate a
settlement file, read it back, and reconcile.

The round trip through a file matters. A reconciler can be correct in memory and
still be wrong once amounts have been written to text and parsed back, because
that is where a Decimal quietly becomes a float.
"""

from __future__ import annotations

import csv
from decimal import Decimal
from pathlib import Path

import pytest

from reconciliation.generator import (
    read_settlement_file,
    records_from_ledger,
    write_settlement_file,
)
from reconciliation.models import BreakKind
from reconciliation.reconciler import reconcile
from reconciliation.reports import render_text

pytestmark = pytest.mark.reconciliation


@pytest.fixture
def ledger_records(extracted):
    records = records_from_ledger(extracted.all_transactions())
    assert records, "The ledger is empty, so there is nothing to reconcile"
    return records


@pytest.fixture
def settlement_path(tmp_path: Path) -> Path:
    return tmp_path / "settlement.csv"


def test_a_settlement_file_is_generated_from_the_ledger(ledger_records, settlement_path):
    """TC-DATA-002 / REQ-DATA-002."""
    written = write_settlement_file(ledger_records, settlement_path)

    assert settlement_path.exists()
    assert written == len(ledger_records)

    with settlement_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    assert len(rows) == len(ledger_records)
    for field in ("transaction_id", "account_id", "amount", "transaction_type", "timestamp"):
        assert field in rows[0], f"Settlement file is missing the {field} column"


def test_amounts_survive_the_round_trip_exactly(ledger_records, settlement_path):
    """REQ-DATA-002.

    Writing to text and parsing back is where a Decimal becomes a float and a
    reconciliation starts reporting one cent breaks that do not exist.
    """
    write_settlement_file(ledger_records, settlement_path)
    read_back = read_settlement_file(settlement_path)

    original = {r.transaction_id: r.amount for r in ledger_records}
    returned = {r.transaction_id: r.amount for r in read_back}

    assert set(original) == set(returned)
    for transaction_id, amount in original.items():
        assert isinstance(returned[transaction_id], Decimal)
        assert returned[transaction_id] == amount, (
            f"Transaction {transaction_id}: wrote {amount}, read back "
            f"{returned[transaction_id]}"
        )


def test_an_untouched_settlement_file_reconciles_cleanly(ledger_records, settlement_path):
    """TC-DATA-004 / REQ-DATA-004. The baseline for the injected faults below."""
    write_settlement_file(ledger_records, settlement_path)
    report = reconcile(ledger_records, read_settlement_file(settlement_path))

    assert report.passed, (
        "A settlement file generated from the ledger did not reconcile:\n"
        + render_text(report)
    )
    assert report.matched == len(ledger_records)


def _rewrite(path: Path, transform) -> None:
    """Read a settlement file, transform its rows, write it back."""
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        header = reader.fieldnames
        rows = list(reader)
    rows = transform(rows)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=header)
        writer.writeheader()
        writer.writerows(rows)


def test_a_record_removed_from_the_file_is_detected(ledger_records, settlement_path):
    """TC-DATA-003 / REQ-DATA-003, injected into a real file rather than a list."""
    write_settlement_file(ledger_records, settlement_path)
    victim = str(ledger_records[0].transaction_id)
    _rewrite(settlement_path, lambda rows: [r for r in rows if r["transaction_id"] != victim])

    report = reconcile(ledger_records, read_settlement_file(settlement_path))

    missing = report.of_kind(BreakKind.MISSING)
    assert len(missing) == 1, render_text(report)
    assert str(missing[0].transaction_id) == victim
    assert len(report.breaks) == 1, render_text(report)


def test_a_record_duplicated_in_the_file_is_detected(ledger_records, settlement_path):
    """TC-DATA-003 / REQ-DATA-003."""
    write_settlement_file(ledger_records, settlement_path)
    victim = str(ledger_records[1].transaction_id)
    _rewrite(settlement_path,
             lambda rows: rows + [r for r in rows if r["transaction_id"] == victim])

    report = reconcile(ledger_records, read_settlement_file(settlement_path))

    duplicates = report.of_kind(BreakKind.DUPLICATE)
    assert len(duplicates) == 1, render_text(report)
    assert str(duplicates[0].transaction_id) == victim
    assert len(report.breaks) == 1, render_text(report)


def test_an_amount_altered_by_one_cent_is_detected(ledger_records, settlement_path):
    """TC-DATA-003 / REQ-DATA-003.

    One cent, deliberately. A reconciler that only notices large differences
    would miss every rounding and conversion error, which is most of them.
    """
    write_settlement_file(ledger_records, settlement_path)
    victim = str(ledger_records[2].transaction_id)

    def bump(rows):
        for row in rows:
            if row["transaction_id"] == victim:
                row["amount"] = f"{Decimal(row['amount']) + Decimal('0.01'):.2f}"
        return rows

    _rewrite(settlement_path, bump)
    report = reconcile(ledger_records, read_settlement_file(settlement_path))

    mismatches = report.of_kind(BreakKind.AMOUNT_MISMATCH)
    assert len(mismatches) == 1, render_text(report)
    assert str(mismatches[0].transaction_id) == victim
    assert "0.01" in mismatches[0].detail
    assert len(report.breaks) == 1, render_text(report)


def test_an_account_changed_to_another_real_account_is_detected(
    ledger_records, settlement_path
):
    """TC-DATA-003 / REQ-DATA-003.

    Another account that genuinely exists, because the realistic failure is
    money landing on somebody else's account rather than on one that does not
    exist. A reconciler that only catches obviously invalid identifiers would
    miss the case that actually costs a customer money.
    """
    write_settlement_file(ledger_records, settlement_path)
    victim = ledger_records[3]
    other = next(r.account_id for r in ledger_records if r.account_id != victim.account_id)

    def repoint(rows):
        for row in rows:
            if row["transaction_id"] == str(victim.transaction_id):
                row["account_id"] = str(other)
        return rows

    _rewrite(settlement_path, repoint)
    report = reconcile(ledger_records, read_settlement_file(settlement_path))

    mismatches = report.of_kind(BreakKind.ACCOUNT_MISMATCH)
    assert len(mismatches) == 1, render_text(report)
    assert mismatches[0].transaction_id == victim.transaction_id
    assert str(other) in mismatches[0].detail
    assert len(report.breaks) == 1, render_text(report)


def test_the_report_states_totals_and_an_overall_status(ledger_records, settlement_path):
    """TC-DATA-007 / REQ-DATA-004."""
    write_settlement_file(ledger_records, settlement_path)

    clean = reconcile(ledger_records, read_settlement_file(settlement_path))
    assert clean.status == "pass"
    assert clean.as_dict()["break_count"] == 0

    _rewrite(settlement_path, lambda rows: rows[:-1])
    broken = reconcile(ledger_records, read_settlement_file(settlement_path))

    assert broken.status == "fail"
    summary = broken.as_dict()
    assert summary["ledger_count"] == len(ledger_records)
    assert summary["settlement_count"] == len(ledger_records) - 1
    assert summary["break_count"] == 1
    assert set(summary["breaks_by_kind"]) == {
        "missing", "unexpected", "duplicate", "amount_mismatch", "account_mismatch"
    }

    text = render_text(broken)
    assert "STATUS" in text and "FAIL" in text
