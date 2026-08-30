"""The ParaBank transfer funds page.

Structure from docs/sut-ui-elements.md, generated against the running
application:

    amount field:  <input type="text" name="input" id="amount">
    from account:  <select id="fromAccountId">   (no name attribute)
    to account:    <select id="toAccountId">     (no name attribute)
    submit:        <input type="submit" value="Transfer">

The amount field's name attribute is the literal string "input", which carries
no meaning, and the two dropdowns have no name at all. Both are recorded as
findings in docs/sut-ui-elements.md. Selection is therefore by identifier.

The confirmation is read from #rightPanel, an authored container identifier
confirmed by scripts/discover_ui_tables.py, rather than from a guessed result
element.
"""

from __future__ import annotations

from pages.base_page import BasePage


class TransferPage(BasePage):
    path = "/transfer.htm"

    AMOUNT = "#amount"
    FROM_ACCOUNT = "#fromAccountId"
    TO_ACCOUNT = "#toAccountId"
    SUBMIT = "input[type='submit'][value='Transfer']"
    RESULT_PANEL = "#rightPanel"

    def wait_until_loaded(self) -> "TransferPage":
        """The dropdowns are populated by script, so wait for their options.

        state="attached", not the default "visible". An <option> inside a
        <select> is never visible in the layout sense, because the browser
        draws the dropdown control rather than the options themselves. Waiting
        for visibility here times out even though the elements are present,
        which is exactly what happened on the first run of this suite.
        """
        self.page.wait_for_selector(f"{self.FROM_ACCOUNT} option", state="attached")
        self.page.wait_for_selector(f"{self.TO_ACCOUNT} option", state="attached")
        return self

    def available_account_ids(self) -> list[int]:
        """Read the option values directly from the document.

        evaluate_all rather than all_inner_texts, because inner_text depends on
        layout and returns nothing for elements the browser never renders. The
        value attribute is present regardless.
        """
        self.wait_until_loaded()
        values = self.page.locator(f"{self.FROM_ACCOUNT} option").evaluate_all(
            "options => options.map(o => o.value)"
        )
        return [int(v.strip()) for v in values if v.strip().isdigit()]

    def transfer(self, amount: str, from_account: int, to_account: int) -> None:
        """Fill the form and submit. Says nothing about whether it worked."""
        self.wait_until_loaded()
        self.page.fill(self.AMOUNT, amount)
        self.page.select_option(self.FROM_ACCOUNT, str(from_account))
        self.page.select_option(self.TO_ACCOUNT, str(to_account))
        self.page.click(self.SUBMIT)
        self.page.wait_for_load_state("networkidle")

    def result_text(self) -> str:
        """Everything shown in the main content area after submission."""
        return self.page.locator(self.RESULT_PANEL).inner_text().strip()
