"""The ParaBank account overview page.

Structure from docs/sut-ui-tables.md, generated against the running
application:

    table id: accountTable
    headers:  Account | Balance* | Available Amount
    row:      12345 | -$2300.00 | $0.00
    links:    activity.htm?id=12345
    log out:  logout.htm

Two details drive the implementation.

The table has 12 rows for 11 accounts, because the last row is a total rather
than an account. Rows are therefore selected with :has(a), which keeps only the
rows carrying an account link. Selecting by row index or by a count would break
the moment the total row moved or a customer opened another account.

Balances are rendered as text such as "-$2300.00". They are parsed to Decimal,
never float, so that money comparisons are exact.
"""

from __future__ import annotations

from decimal import Decimal

from pages.base_page import BasePage


class OverviewPage(BasePage):
    path = "/overview.htm"

    TABLE = "#accountTable"
    ACCOUNT_ROWS = "#accountTable tbody tr:has(a)"
    LOG_OUT = "a[href='logout.htm']"
    TRANSFER_LINK = "a[href='transfer.htm']"

    @staticmethod
    def parse_money(text: str) -> Decimal:
        """Turn '-$2,300.00' into Decimal('-2300.00').

        Decimal rather than float, because floating point cannot represent 0.01
        exactly and money comparisons must be exact.
        """
        cleaned = text.strip().replace("$", "").replace(",", "").replace("\u00a0", "")
        if cleaned.startswith("(") and cleaned.endswith(")"):
            cleaned = "-" + cleaned[1:-1]
        return Decimal(cleaned)

    def is_displayed(self) -> bool:
        return self.page.locator(self.TABLE).count() > 0

    def wait_until_loaded(self) -> "OverviewPage":
        """The table is rendered by script, so wait for a row rather than the page."""
        self.page.wait_for_selector(self.ACCOUNT_ROWS, state="attached")
        return self

    def account_balances(self) -> dict[int, Decimal]:
        """Every account identifier on the page mapped to its displayed balance."""
        self.wait_until_loaded()
        balances: dict[int, Decimal] = {}
        rows = self.page.locator(self.ACCOUNT_ROWS)
        for i in range(rows.count()):
            cells = rows.nth(i).locator("td")
            account_id = int(cells.nth(0).inner_text().strip())
            balances[account_id] = self.parse_money(cells.nth(1).inner_text())
        return balances

    def account_ids(self) -> list[int]:
        return sorted(self.account_balances())

    def open_account(self, account_id: int) -> None:
        self.page.click(f"a[href='activity.htm?id={account_id}']")
        self.page.wait_for_load_state("networkidle")

    def log_out(self) -> None:
        self.page.click(self.LOG_OUT)
        self.page.wait_for_load_state("networkidle")
