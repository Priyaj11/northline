"""Access layer for the Northline certification data store.

One place that owns the connection, the schema, and every query. Tests and
scripts call methods here rather than writing SQL inline, so a schema change is
a single edit.

Money is read and written as Decimal throughout. psycopg maps a PostgreSQL
NUMERIC column to a Python Decimal automatically, so exactness survives the
round trip in both directions.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable

import psycopg

from utils.config import Settings
from utils.logger import get_logger

log = get_logger("warehouse")

SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


def epoch_millis_to_datetime(value: int) -> datetime:
    """ParaBank returns transaction dates as epoch milliseconds, not strings.

    Recorded as Observation 5 in docs/sut-parabank.md. Converting here keeps the
    quirk in one place instead of spreading it through every query.
    """
    return datetime.fromtimestamp(value / 1000, tz=timezone.utc)


class Warehouse:
    """A thin, explicit wrapper around the certification data store."""

    def __init__(self, settings: Settings) -> None:
        self._dsn = settings.warehouse.dsn
        self._environment = settings.environment
        self._release = settings.release

    def connect(self) -> psycopg.Connection:
        return psycopg.connect(self._dsn, connect_timeout=10)

    # --- schema ---------------------------------------------------------

    def apply_schema(self) -> None:
        """Create the tables if they do not already exist."""
        sql = SCHEMA_PATH.read_text()
        with self.connect() as conn, conn.cursor() as cur:
            cur.execute(sql)
            conn.commit()
        log.info("Schema applied from %s", SCHEMA_PATH.name)

    def table_names(self) -> list[str]:
        with self.connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public' ORDER BY table_name"
            )
            return [row[0] for row in cur.fetchall()]

    def clear(self) -> None:
        """Empty the data tables, keeping the schema. Used before an extraction."""
        with self.connect() as conn, conn.cursor() as cur:
            cur.execute("TRUNCATE transactions, accounts, extraction_runs RESTART IDENTITY CASCADE")
            conn.commit()
        log.info("Certification data store cleared")

    # --- extraction runs -------------------------------------------------

    def start_run(self) -> int:
        with self.connect() as conn, conn.cursor() as cur:
            cur.execute(
                "INSERT INTO extraction_runs (environment, release) VALUES (%s, %s) "
                "RETURNING run_id",
                (self._environment, self._release),
            )
            run_id = cur.fetchone()[0]
            conn.commit()
        log.info("Extraction run %s started", run_id)
        return run_id

    def finish_run(self, run_id: int, accounts: int, transactions: int,
                   status: str = "complete") -> None:
        with self.connect() as conn, conn.cursor() as cur:
            cur.execute(
                "UPDATE extraction_runs SET finished_at = now(), account_count = %s, "
                "transaction_count = %s, status = %s WHERE run_id = %s",
                (accounts, transactions, status, run_id),
            )
            conn.commit()
        log.info("Extraction run %s %s: %d accounts, %d transactions",
                 run_id, status, accounts, transactions)

    # --- writes -----------------------------------------------------------

    def upsert_accounts(self, accounts: Iterable[dict[str, Any]], run_id: int) -> int:
        rows = [
            (a["id"], a["customerId"], a["type"], Decimal(str(a["balance"])), run_id)
            for a in accounts
        ]
        with self.connect() as conn, conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO accounts (account_id, customer_id, account_type, balance, run_id) "
                "VALUES (%s, %s, %s, %s, %s) "
                "ON CONFLICT (account_id) DO UPDATE SET "
                "customer_id = EXCLUDED.customer_id, account_type = EXCLUDED.account_type, "
                "balance = EXCLUDED.balance, run_id = EXCLUDED.run_id, extracted_at = now()",
                rows,
            )
            conn.commit()
        return len(rows)

    def upsert_transactions(self, transactions: Iterable[dict[str, Any]], run_id: int) -> int:
        rows = [
            (
                t["id"],
                t["accountId"],
                t["type"],
                epoch_millis_to_datetime(t["date"]),
                Decimal(str(t["amount"])),
                t.get("description"),
                run_id,
            )
            for t in transactions
        ]
        if not rows:
            return 0
        with self.connect() as conn, conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO transactions (transaction_id, account_id, transaction_type, "
                "transaction_date, amount, description, run_id) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s) "
                "ON CONFLICT (transaction_id) DO UPDATE SET "
                "account_id = EXCLUDED.account_id, transaction_type = EXCLUDED.transaction_type, "
                "transaction_date = EXCLUDED.transaction_date, amount = EXCLUDED.amount, "
                "description = EXCLUDED.description, run_id = EXCLUDED.run_id, "
                "extracted_at = now()",
                rows,
            )
            conn.commit()
        return len(rows)

    # --- reads ------------------------------------------------------------

    def account_count(self) -> int:
        with self.connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM accounts")
            return cur.fetchone()[0]

    def transaction_count(self) -> int:
        with self.connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM transactions")
            return cur.fetchone()[0]

    def balances(self) -> dict[int, Decimal]:
        with self.connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT account_id, balance FROM accounts ORDER BY account_id")
            return {row[0]: row[1] for row in cur.fetchall()}

    def balance_of(self, account_id: int) -> Decimal | None:
        with self.connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT balance FROM accounts WHERE account_id = %s", (account_id,))
            row = cur.fetchone()
            return row[0] if row else None

    def transactions_for(self, account_id: int) -> list[dict[str, Any]]:
        with self.connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT transaction_id, account_id, transaction_type, transaction_date, "
                "amount, description FROM transactions WHERE account_id = %s "
                "ORDER BY transaction_date, transaction_id",
                (account_id,),
            )
            return [
                {
                    "transaction_id": r[0],
                    "account_id": r[1],
                    "type": r[2],
                    "date": r[3],
                    "amount": r[4],
                    "description": r[5],
                }
                for r in cur.fetchall()
            ]

    def all_transactions(self) -> list[dict[str, Any]]:
        with self.connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT transaction_id, account_id, transaction_type, transaction_date, "
                "amount, description FROM transactions ORDER BY transaction_id"
            )
            return [
                {
                    "transaction_id": r[0],
                    "account_id": r[1],
                    "type": r[2],
                    "date": r[3],
                    "amount": r[4],
                    "description": r[5],
                }
                for r in cur.fetchall()
            ]

    def orphan_transactions(self) -> list[int]:
        """Transactions whose account is not present. The foreign key should
        make this impossible, so a non-empty result means the constraint is
        missing rather than that the data is odd."""
        with self.connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT t.transaction_id FROM transactions t "
                "LEFT JOIN accounts a ON a.account_id = t.account_id "
                "WHERE a.account_id IS NULL"
            )
            return [row[0] for row in cur.fetchall()]

    def amounts_with_excess_precision(self) -> list[tuple[int, Decimal]]:
        """Amounts carrying more than two decimal places.

        NUMERIC(15,2) should make this impossible, so this asserts the column
        definition is doing its job rather than that the source data is clean.
        """
        with self.connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT transaction_id, amount FROM transactions "
                "WHERE amount <> round(amount, 2)"
            )
            return [(row[0], row[1]) for row in cur.fetchall()]

    def type_description_inconsistencies(self) -> list[dict[str, Any]]:
        """Transactions whose type contradicts their own description.

        A record described as "Funds Transfer Received" but typed Debit is
        self-contradictory. Any downstream system that sums by type rather than
        by description gets a wrong total for that account.

        ParaBank's seeded demo data contains four such records (confirmed
        2026-08-30, see Observation 10 in docs/sut-parabank.md). The application
        writes correct records today, so this is a property of the seed rather
        than a defect. Tests use this to assert that no NEW inconsistency
        appears, which is the part that would be a real regression.
        """
        with self.connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT transaction_id, account_id, transaction_type, amount, description "
                "FROM transactions "
                "WHERE (description ILIKE '%%Received%%' AND transaction_type <> 'Credit') "
                "   OR (description ILIKE '%%Sent%%'     AND transaction_type <> 'Debit') "
                "ORDER BY transaction_id"
            )
            return [
                {
                    "transaction_id": r[0],
                    "account_id": r[1],
                    "type": r[2],
                    "amount": r[3],
                    "description": r[4],
                }
                for r in cur.fetchall()
            ]

    def zero_amount_transactions(self) -> list[dict[str, Any]]:
        """Transactions recorded with an amount of zero.

        The application rejects a transfer of 0.00, confirmed by TC-XFER-004, so
        a zero-amount transfer record should not be creatable. Two exist in the
        seeded data.
        """
        with self.connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT transaction_id, account_id, transaction_type, amount, description "
                "FROM transactions WHERE amount = 0 ORDER BY transaction_id"
            )
            return [
                {
                    "transaction_id": r[0],
                    "account_id": r[1],
                    "type": r[2],
                    "amount": r[3],
                    "description": r[4],
                }
                for r in cur.fetchall()
            ]
