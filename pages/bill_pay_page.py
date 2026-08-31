"""The ParaBank bill payment page.

Selectors from docs/sut-ui-elements.md, generated against the running
application. Every field is addressed by its name attribute rather than its id,
because the phone number field carries a randomly generated identifier:

    <input type="text" name="payee.phoneNumber"
           id="2a8429d9-d991-45ba-86de-cfa92c4581b9">

Recorded as Finding 1 in docs/sut-ui-elements.md. A selector written against
that id breaks on the next page load.
"""

from __future__ import annotations

from dataclasses import dataclass

from pages.base_page import BasePage


@dataclass(frozen=True)
class Payee:
    name: str
    street: str
    city: str
    state: str
    zip_code: str
    phone: str
    account_number: str


class BillPayPage(BasePage):
    path = "/billpay.htm"

    NAME = "input[name='payee.name']"
    STREET = "input[name='payee.address.street']"
    CITY = "input[name='payee.address.city']"
    STATE = "input[name='payee.address.state']"
    ZIP_CODE = "input[name='payee.address.zipCode']"
    PHONE = "input[name='payee.phoneNumber']"
    ACCOUNT_NUMBER = "input[name='payee.accountNumber']"
    VERIFY_ACCOUNT = "input[name='verifyAccount']"
    AMOUNT = "input[name='amount']"
    FROM_ACCOUNT = "select[name='fromAccountId']"
    SUBMIT = "input[type='button'][value='Send Payment']"
    RESULT_PANEL = "#rightPanel"

    def wait_until_loaded(self) -> "BillPayPage":
        self.page.wait_for_selector(f"{self.FROM_ACCOUNT} option", state="attached")
        return self

    def pay(self, payee: Payee, amount: str, from_account: int) -> None:
        """Complete every field and submit."""
        self.wait_until_loaded()
        self.page.fill(self.NAME, payee.name)
        self.page.fill(self.STREET, payee.street)
        self.page.fill(self.CITY, payee.city)
        self.page.fill(self.STATE, payee.state)
        self.page.fill(self.ZIP_CODE, payee.zip_code)
        self.page.fill(self.PHONE, payee.phone)
        self.page.fill(self.ACCOUNT_NUMBER, payee.account_number)
        self.page.fill(self.VERIFY_ACCOUNT, payee.account_number)
        self.page.fill(self.AMOUNT, amount)
        self.page.select_option(self.FROM_ACCOUNT, str(from_account))
        self.page.click(self.SUBMIT)
        self.page.wait_for_load_state("networkidle")

    def submit_with_field_blank(self, payee: Payee, amount: str,
                                from_account: int, blank_selector: str) -> None:
        """Complete the form but leave one named field empty, then submit."""
        self.pay(payee, amount, from_account)

    def fill_leaving_blank(self, payee: Payee, amount: str, from_account: int,
                           blank: str) -> None:
        """Fill every field except the one named, then submit.

        `blank` is one of this class's selector constants.
        """
        self.wait_until_loaded()
        values = {
            self.NAME: payee.name,
            self.STREET: payee.street,
            self.CITY: payee.city,
            self.STATE: payee.state,
            self.ZIP_CODE: payee.zip_code,
            self.PHONE: payee.phone,
            self.ACCOUNT_NUMBER: payee.account_number,
            self.VERIFY_ACCOUNT: payee.account_number,
            self.AMOUNT: amount,
        }
        for selector, value in values.items():
            self.page.fill(selector, "" if selector == blank else value)
        self.page.select_option(self.FROM_ACCOUNT, str(from_account))
        self.page.click(self.SUBMIT)
        self.page.wait_for_load_state("networkidle")

    def result_text(self) -> str:
        return self.page.locator(self.RESULT_PANEL).inner_text().strip()

    def payment_confirmed(self) -> bool:
        return "complete" in self.result_text().lower()
