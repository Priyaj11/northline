"""Settlement file generation and reading.

The settlement file is what a bank sends onward at the end of a day. Northline
generates it from the certification data store, then the reconciler compares
the two.

That sounds circular, and it would be if nothing ever went wrong between them.
The point of the exercise is the fault injection: records are deliberately
removed, duplicated and altered, and the reconciler must find every one. A
reconciler that has only ever seen matching data proves nothing.

The file is comma separated values, which is what banks actually exchange for
this. Amounts are written as plain decimal strings with two places, never in
scientific notation and never as floats.
"""

from __future__ import annotations

import csv
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable

from reconciliation.models import SettlementRecord

HEADER = ["transaction_id", "account_id", "amount", "transaction_type", "timestamp"]


def records_from_ledger(rows: Iterable[dict[str, Any]]) -> list[SettlementRecord]:
    """Turn warehouse rows into settlement records."""
    return [
        SettlementRecord(
            transaction_id=row["transaction_id"],
            account_id=row["account_id"],
            amount=row["amount"] if isinstance(row["amount"], Decimal)
            else Decimal(str(row["amount"])),
            transaction_type=row["type"],
            timestamp=row["date"],
        )
        for row in rows
    ]


def write_settlement_file(records: Iterable[SettlementRecord], path: Path) -> int:
    """Write a settlement file. Returns the number of rows written."""
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = list(records)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(HEADER)
        for record in rows:
            writer.writerow([
                record.transaction_id,
                record.account_id,
                f"{record.amount:.2f}",
                record.transaction_type,
                record.timestamp.isoformat(),
            ])
    return len(rows)


def read_settlement_file(path: Path) -> list[SettlementRecord]:
    """Read a settlement file back.

    Amounts are parsed with Decimal(str), never float(). Parsing "0.01" as a
    float and comparing it to a Decimal is how a reconciler reports a break
    that does not exist.
    """
    records: list[SettlementRecord] = []
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            records.append(SettlementRecord(
                transaction_id=int(row["transaction_id"]),
                account_id=int(row["account_id"]),
                amount=Decimal(row["amount"]),
                transaction_type=row["transaction_type"],
                timestamp=_parse_timestamp(row["timestamp"]),
            ))
    return records


def _parse_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
