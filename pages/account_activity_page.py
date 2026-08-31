"""The ParaBank account activity page.

Reached from the account overview at activity.htm?id=<account>. Structure
captured against the running application:

    account details    #accountId #accountType #balance #availableBalance
    filters            #month #transactionType
    transactions       #transactionTable, headers Date | Transaction |
                       Debit (-) | Credit (+)
    empty state        #noTransactions

Amounts are rendered as text such as "$300.00" in one of two columns depending
on direction, so a row's signed amount has to be derived from WHICH column holds
the value rather than from the value itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from pages.base_page import BasePage
from pages.overview_page import OverviewPage


@dataclass(frozen=True)
class ActivityRow:
    date: str
    description: str
    debit: Decimal | None
    credit: Decimal | None

    @property
    def signed_amount(self) -> Decimal:
        """Negative for a debit, positive for a credit.

        Derived from which column the value sits in, because the displayed text
        carries no sign. A row showing $100.00 in the debit column and one
        showing $100.00 in the credit column are opposite transactions that
        render identically apart from their position.
        """
        if self.debit is not None:
            return -self.debit
        return self.credit or Decimal("0.00")


class AccountActivityPage(BasePage):
    TABLE = "#transactionTable"
    ROWS = "#transactionTable tbody tr"
    NO_TRANSACTIONS = "#noTransactions"
    ACCOUNT_ID = "#accountId"
    ACCOUNT_TYPE = "#accountType"
    BALANCE = "#balance"
    AVAILABLE = "#availableBalance"
    MONTH = "#month"
    TYPE_FILTER = "#transactionType"

    def open_for(self, account_id: int) -> "AccountActivityPage":
        self.page.goto(f"{self.base_url}/activity.htm?id={account_id}")
        self.page.wait_for_load_state("networkidle")
        return self

    def account_id(self) -> int:
        return int(self.page.locator(self.ACCOUNT_ID).inner_text().strip())

    def account_type(self) -> str:
        return self.page.locator(self.ACCOUNT_TYPE).inner_text().strip()

    def balance(self) -> Decimal:
        return OverviewPage.parse_money(self.page.locator(self.BALANCE).inner_text())

    def has_transactions(self) -> bool:
        return self.page.locator(self.ROWS).count() > 0

    def rows(self) -> list[ActivityRow]:
        found: list[ActivityRow] = []
        rows = self.page.locator(self.ROWS)
        for i in range(rows.count()):
            cells = rows.nth(i).locator("td")
            if cells.count() < 4:
                continue
            debit_text = cells.nth(2).inner_text().strip()
            credit_text = cells.nth(3).inner_text().strip()
            found.append(ActivityRow(
                date=cells.nth(0).inner_text().strip(),
                description=cells.nth(1).inner_text().strip(),
                debit=OverviewPage.parse_money(debit_text) if debit_text else None,
                credit=OverviewPage.parse_money(credit_text) if credit_text else None,
            ))
        return found
