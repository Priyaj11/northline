"""The ParaBank registration page.

Selectors from docs/sut-ui-elements.md, generated against the running
application. The registration form namespaces its fields under "customer.",
which distinguishes them from the login panel that appears on the same page.

    customer.firstName          customer.address.zipCode
    customer.lastName           customer.phoneNumber
    customer.address.street     customer.ssn
    customer.address.city       customer.username
    customer.address.state      customer.password
                                repeatedPassword

Registration exists in the framework for one reason beyond its own coverage:
the authorisation tests need a SECOND customer. Testing whether one customer
can reach another customer's account is impossible with a single seeded user,
and it is the most consequential authorisation check in a banking application.
"""

from __future__ import annotations

from dataclasses import dataclass

from pages.base_page import BasePage


@dataclass(frozen=True)
class NewCustomer:
    """The details used to register, kept so a test can log back in later."""

    first_name: str
    last_name: str
    street: str
    city: str
    state: str
    zip_code: str
    phone: str
    ssn: str
    username: str
    password: str


class RegisterPage(BasePage):
    path = "/register.htm"

    FIRST_NAME = "input[name='customer.firstName']"
    LAST_NAME = "input[name='customer.lastName']"
    STREET = "input[name='customer.address.street']"
    CITY = "input[name='customer.address.city']"
    STATE = "input[name='customer.address.state']"
    ZIP_CODE = "input[name='customer.address.zipCode']"
    PHONE = "input[name='customer.phoneNumber']"
    SSN = "input[name='customer.ssn']"
    USERNAME = "input[name='customer.username']"
    PASSWORD = "input[name='customer.password']"
    CONFIRM = "input[name='repeatedPassword']"
    SUBMIT = "input[type='submit'][value='Register']"

    def register(self, customer: NewCustomer) -> None:
        """Complete every required field and submit."""
        self.page.fill(self.FIRST_NAME, customer.first_name)
        self.page.fill(self.LAST_NAME, customer.last_name)
        self.page.fill(self.STREET, customer.street)
        self.page.fill(self.CITY, customer.city)
        self.page.fill(self.STATE, customer.state)
        self.page.fill(self.ZIP_CODE, customer.zip_code)
        self.page.fill(self.PHONE, customer.phone)
        self.page.fill(self.SSN, customer.ssn)
        self.page.fill(self.USERNAME, customer.username)
        self.page.fill(self.PASSWORD, customer.password)
        self.page.fill(self.CONFIRM, customer.password)
        self.page.click(self.SUBMIT)
        self.page.wait_for_load_state("networkidle")

    def registration_succeeded(self) -> bool:
        """ParaBank logs the new customer straight in on success."""
        return "/parabank/register.htm" not in self.page.url or not self.error_text()
