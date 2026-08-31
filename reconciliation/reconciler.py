"""The reconciliation engine.

Compares a settlement file against the ledger and reports every difference.

Deliberately a pure function over two lists rather than something that talks to
a database. That means the engine can be tested exhaustively without an
environment, which matters: a reconciler nobody can test thoroughly is a
reconciler nobody should trust with money.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone

from reconciliation.models import Break, BreakKind, ReconciliationReport, SettlementRecord


def reconcile(ledger: list[SettlementRecord],
              settlement: list[SettlementRecord]) -> ReconciliationReport:
    """Compare the ledger against a settlement file.

    Detection order matters for readability of the report, not for correctness:
    duplicates first because they change how the rest is interpreted, then
    records present on only one side, then field-level differences on records
    present in both.
    """
    breaks: list[Break] = []

    ledger_by_id = {r.transaction_id: r for r in ledger}
    settlement_counts = Counter(r.transaction_id for r in settlement)
    settlement_by_id: dict[int, SettlementRecord] = {}
    for record in settlement:
        settlement_by_id.setdefault(record.transaction_id, record)

    # 1. Duplicates: the same transaction appearing more than once in the file.
    for transaction_id, count in sorted(settlement_counts.items()):
        if count > 1:
            record = settlement_by_id[transaction_id]
            breaks.append(Break(
                kind=BreakKind.DUPLICATE,
                transaction_id=transaction_id,
                account_id=record.account_id,
                detail=f"appears {count} times in the settlement file, expected once",
            ))

    # 2. Missing: in the ledger, absent from the file. Money the bank recorded
    #    that was never sent onward.
    for transaction_id in sorted(set(ledger_by_id) - set(settlement_by_id)):
        record = ledger_by_id[transaction_id]
        breaks.append(Break(
            kind=BreakKind.MISSING,
            transaction_id=transaction_id,
            account_id=record.account_id,
            detail=f"in the ledger for {record.amount} but absent from the settlement file",
        ))

    # 3. Unexpected: in the file, absent from the ledger. Money reported that
    #    the bank has no record of.
    for transaction_id in sorted(set(settlement_by_id) - set(ledger_by_id)):
        record = settlement_by_id[transaction_id]
        breaks.append(Break(
            kind=BreakKind.UNEXPECTED,
            transaction_id=transaction_id,
            account_id=record.account_id,
            detail=f"in the settlement file for {record.amount} but absent from the ledger",
        ))

    # 4. Field differences on records present in both.
    matched = 0
    for transaction_id in sorted(set(ledger_by_id) & set(settlement_by_id)):
        expected = ledger_by_id[transaction_id]
        actual = settlement_by_id[transaction_id]
        record_ok = True

        if actual.amount != expected.amount:
            record_ok = False
            breaks.append(Break(
                kind=BreakKind.AMOUNT_MISMATCH,
                transaction_id=transaction_id,
                account_id=expected.account_id,
                detail=(f"settlement says {actual.amount}, ledger says {expected.amount} "
                        f"(difference {actual.amount - expected.amount})"),
            ))

        if actual.account_id != expected.account_id:
            record_ok = False
            breaks.append(Break(
                kind=BreakKind.ACCOUNT_MISMATCH,
                transaction_id=transaction_id,
                account_id=expected.account_id,
                detail=(f"settlement posts to account {actual.account_id}, "
                        f"ledger says account {expected.account_id}"),
            ))

        if record_ok and settlement_counts[transaction_id] == 1:
            matched += 1

    return ReconciliationReport(
        ledger_count=len(ledger),
        settlement_count=len(settlement),
        matched=matched,
        breaks=breaks,
        generated_at=datetime.now(tz=timezone.utc),
    )
