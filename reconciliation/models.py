"""Data structures for settlement reconciliation.

A settlement file is what a bank sends onward at the end of a day: one row per
transaction, going to a clearing house, a partner bank, or a regulator.
Reconciliation compares that file against the bank's own ledger and reports
every difference.

Two rules shape these structures.

Money is Decimal, never float. A reconciliation that compares floats reports
breaks that are not real and misses ones that are.

A break carries enough detail to be acted on. "Account 12345 does not
reconcile" sends someone hunting. "Transaction 14032: settlement says 100.00,
ledger says 100.01" tells them what to fix.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum


class BreakKind(str, Enum):
    """The five ways a settlement file can disagree with the ledger."""

    MISSING = "missing"                    # in the ledger, absent from the file
    UNEXPECTED = "unexpected"              # in the file, absent from the ledger
    DUPLICATE = "duplicate"                # appears more than once in the file
    AMOUNT_MISMATCH = "amount_mismatch"    # same transaction, different amount
    ACCOUNT_MISMATCH = "account_mismatch"  # same transaction, different account


@dataclass(frozen=True)
class SettlementRecord:
    """One line of a settlement file, or one row of the ledger."""

    transaction_id: int
    account_id: int
    amount: Decimal
    transaction_type: str
    timestamp: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.amount, Decimal):
            raise TypeError(
                f"Transaction {self.transaction_id}: amount must be Decimal, "
                f"got {type(self.amount).__name__}. Comparing money as a float "
                "produces breaks that are not real and hides ones that are."
            )


@dataclass(frozen=True)
class Break:
    """One difference between the settlement file and the ledger."""

    kind: BreakKind
    transaction_id: int
    detail: str
    account_id: int | None = None

    def __str__(self) -> str:
        where = f" account {self.account_id}" if self.account_id is not None else ""
        return f"[{self.kind.value}] transaction {self.transaction_id}{where}: {self.detail}"


@dataclass
class ReconciliationReport:
    """The outcome of one reconciliation run."""

    ledger_count: int
    settlement_count: int
    matched: int
    breaks: list[Break] = field(default_factory=list)
    generated_at: datetime | None = None

    @property
    def status(self) -> str:
        return "pass" if not self.breaks else "fail"

    @property
    def passed(self) -> bool:
        return not self.breaks

    def of_kind(self, kind: BreakKind) -> list[Break]:
        return [b for b in self.breaks if b.kind is kind]

    def counts(self) -> dict[str, int]:
        return {kind.value: len(self.of_kind(kind)) for kind in BreakKind}

    def as_dict(self) -> dict:
        return {
            "status": self.status,
            "ledger_count": self.ledger_count,
            "settlement_count": self.settlement_count,
            "matched": self.matched,
            "break_count": len(self.breaks),
            "breaks_by_kind": self.counts(),
            "breaks": [
                {
                    "kind": b.kind.value,
                    "transaction_id": b.transaction_id,
                    "account_id": b.account_id,
                    "detail": b.detail,
                }
                for b in self.breaks
            ],
            "generated_at": self.generated_at.isoformat() if self.generated_at else None,
        }
