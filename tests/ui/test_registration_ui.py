"""Browser tests for registration and opening an account.

Covers TC-AUTH-011, TC-AUTH-012 and TC-ACCT-006.

Registration matters beyond its own coverage. It is what lets a test create its
own customer instead of competing for the shared demo user, which is the
isolation approach described in docs/test-data-strategy.md and the mechanism
the cross-customer authorisation test in Phase 5B depends on.
"""

from __future__ import annotations

import pytest
from faker import Faker

from pages.login_page import LoginPage
from pages.overview_page import OverviewPage
from pages.register_page import NewCustomer, RegisterPage

pytestmark = pytest.mark.ui

fake = Faker("en_CA")

OVERVIEW_PATH = "/parabank/overview.htm"


def new_customer(username: str | None = None) -> NewCustomer:
    """Obviously fabricated details. The identifier field is a placeholder, not
    a number belonging to anybody."""
    return NewCustomer(
        first_name=fake.first_name(),
        last_name=fake.last_name(),
        street="1 Northline Test Street",
        city="Windsor",
        state="ON",
        zip_code="N9A0A0",
        phone="5550100",
        ssn="000-00-0000",
        username=username or f"northline_{fake.uuid4()[:8]}",
        password="NorthlineTest1!",
    )


def test_a_new_customer_can_register_and_is_signed_in(page, base_url: str):
    """TC-AUTH-011 / REQ-AUTH-005."""
    details = new_customer()
    register = RegisterPage(page, base_url).open()
    register.register(details)

    assert register.registration_succeeded(), (
        f"Registration failed for {details.username}. "
        f"Page said: {register.error_text()!r}"
    )

    overview = OverviewPage(page, base_url).open().wait_until_loaded()
    assert overview.account_balances(), (
        "A newly registered customer has no accounts. Registration is supposed "
        "to open one, and the isolated test data approach depends on it."
    )


def test_a_registered_customer_can_log_back_in(page, base_url: str):
    """TC-AUTH-011 / REQ-AUTH-005.

    Registering and being signed in immediately is not the same as having a
    usable account. A customer who cannot log in tomorrow has not really
    registered.
    """
    details = new_customer()
    RegisterPage(page, base_url).open().register(details)

    page.context.clear_cookies()
    login = LoginPage(page, base_url).open()
    login.log_in_as(details.username, details.password)

    assert login.current_path == OVERVIEW_PATH, (
        f"{details.username} registered but could not log in again. "
        f"Ended at {page.url}, error: {login.error_text()!r}"
    )


def test_registering_a_username_that_already_exists_is_refused(
    page, base_url: str, settings
):
    """TC-AUTH-012 / REQ-AUTH-005, negative testing.

    Uses the seeded demo username, which certainly exists. A second customer
    sharing a username would make the login ambiguous, which is a correctness
    problem rather than a validation nicety.
    """
    details = new_customer(username=settings.sut.username)
    register = RegisterPage(page, base_url).open()
    register.register(details)

    error = register.error_text()
    assert error, (
        f"Registering the existing username {settings.sut.username!r} produced "
        f"no error. Ended at {page.url}"
    )


def test_a_customer_can_open_a_new_account(page, base_url: str, settings):
    """TC-ACCT-006 / REQ-ACCT-004.

    Asserted by counting accounts before and after rather than by reading the
    confirmation, because the confirmation says an account was opened and the
    overview is where the customer would look for it.
    """
    LoginPage(page, base_url).open().log_in_as(
        settings.sut.username, settings.sut.password)

    overview = OverviewPage(page, base_url).open().wait_until_loaded()
    before = set(overview.account_ids())
    funding = sorted(before)[0]

    page.goto(f"{base_url}/openaccount.htm")
    page.wait_for_load_state("networkidle")
    page.wait_for_selector("#fromAccountId option", state="attached")
    page.select_option("#type", label="CHECKING")
    page.select_option("#fromAccountId", str(funding))
    page.click("input[type='button'][value='Open New Account']")
    page.wait_for_load_state("networkidle")

    after = set(OverviewPage(page, base_url).open().wait_until_loaded().account_ids())
    created = after - before

    assert len(created) == 1, (
        f"Opening one account should add exactly one to the overview. "
        f"Before: {len(before)}, after: {len(after)}, new: {sorted(created)}"
    )
