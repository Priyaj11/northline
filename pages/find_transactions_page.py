"""The ParaBank find transactions page.

Structure captured against the running application:

    account          #accountId
    by identifier    #transactionId       #findById       #transactionIdError
    by date          #transactionDate     #findByDate     #transactionDateError
    by date range    #fromDate #toDate    #findByDateRange #dateRangeError
    by amount        #amount              #findByAmount   #amountError
    results          #resultContainer, #transactionTable
                     headers Date | Transaction | Debit (-) | Credit (+)

DATE FORMAT

Established by experiment, not assumed. The page accepts MM-DD-YYYY and rejects
slash-separated and ISO formats with "Invalid date format" in the matching
error element.

It also ACCEPTS DD-MM-YYYY without complaint, which is recorded as a finding
rather than worked around: a customer entering 31-12-2026 gets results rather
than an error, and a customer entering a correct range with no matching
transactions gets the same silent empty table.
"""

from __future__ import annotations

from pages.base_page import BasePage
from pages.account_activity_page import ActivityRow
from pages.overview_page import OverviewPage


class FindTransactionsPage(BasePage):
    path = "/findtrans.htm"

    ACCOUNT = "#accountId"
    TRANSACTION_ID = "#transactionId"
    FIND_BY_ID = "#findById"
    ID_ERROR = "#transactionIdError"
    DATE = "#transactionDate"
    FIND_BY_DATE = "#findByDate"
    DATE_ERROR = "#transactionDateError"
    FROM_DATE = "#fromDate"
    TO_DATE = "#toDate"
    FIND_BY_RANGE = "#findByDateRange"
    RANGE_ERROR = "#dateRangeError"
    AMOUNT = "#amount"
    FIND_BY_AMOUNT = "#findByAmount"
    AMOUNT_ERROR = "#amountError"
    ROWS = "#transactionTable tbody tr"

    def wait_until_loaded(self) -> "FindTransactionsPage":
        """Wait for the account select to have a non-zero SIZE.

        That is the condition that actually matters, and it was established by
        measurement rather than reasoning.

        On the second search within a test, the element reported display
        inline-block and visibility visible while its bounding rectangle was
        0 by 0, and document.elementFromPoint at its centre returned BODY rather
        than the select. A zero-sized element is not actionable, which is what
        Playwright means by "not visible", and it is why every check of computed
        style reported the element as fine.

        The cause is reopening the page inside a search: the element exists and
        has styles before the layout has resolved. Waiting for networkidle does
        not help, because layout is not network activity.

        Three earlier diagnoses were wrong, all reasoned from the error message:
        that the select needed a visibility wait, that it was permanently hidden
        and needed force, and that the page needed to settle. Printing the
        bounding rectangle at the moment of the failing call settled it in one
        attempt.
        """
        self.page.wait_for_load_state("networkidle")
        self.page.wait_for_selector(f"{self.ACCOUNT} option", state="attached")
        self.page.wait_for_function(
            """() => {
                const e = document.querySelector('#accountId');
                if (!e) return false;
                const r = e.getBoundingClientRect();
                return r.width > 0 && r.height > 0;
            }"""
        )
        return self

    def available_account_ids(self) -> list[int]:
        self.wait_until_loaded()
        values = self.page.locator(f"{self.ACCOUNT} option").evaluate_all(
            "options => options.map(o => o.value)")
        return [int(v) for v in values if v.strip().isdigit()]

    def search_by_date_range(self, account_id: int, from_date: str,
                             to_date: str) -> None:
        """Dates in MM-DD-YYYY, the only format the page documents by accepting."""
        self.wait_until_loaded()
        self.page.select_option(self.ACCOUNT, str(account_id))
        self.page.fill(self.FROM_DATE, from_date)
        self.page.fill(self.TO_DATE, to_date)
        self.page.click(self.FIND_BY_RANGE)
        self.page.wait_for_load_state("networkidle")

    def search_by_amount(self, account_id: int, amount: str) -> None:
        self.open()
        self.wait_until_loaded()
        self.page.select_option(self.ACCOUNT, str(account_id))
        self.page.fill(self.AMOUNT, amount)
        self.page.click(self.FIND_BY_AMOUNT)
        self.page.wait_for_load_state("networkidle")

    def error_for(self, selector: str) -> str:
        locator = self.page.locator(selector)
        return locator.inner_text().strip() if locator.count() else ""

    def result_rows(self) -> list[ActivityRow]:
        found: list[ActivityRow] = []
        rows = self.page.locator(self.ROWS)
        for i in range(rows.count()):
            cells = rows.nth(i).locator("td")
            if cells.count() < 4:
                continue
            debit = cells.nth(2).inner_text().strip()
            credit = cells.nth(3).inner_text().strip()
            found.append(ActivityRow(
                date=cells.nth(0).inner_text().strip(),
                description=cells.nth(1).inner_text().strip(),
                debit=OverviewPage.parse_money(debit) if debit else None,
                credit=OverviewPage.parse_money(credit) if credit else None,
            ))
        return found
