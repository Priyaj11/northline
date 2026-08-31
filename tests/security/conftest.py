"""Fixtures for the security-adjacent suite.

SCOPE, stated plainly because it matters.

This is not penetration testing. Northline verifies that the application
enforces the access rules it claims to enforce. It does not attempt to exploit
anything, does not enumerate beyond what a single request reveals, and does not
extract data beyond what is needed to demonstrate whether a control exists.

Where a control is found missing, the evidence is one request and its status
code, and the finding goes into the defect register. That is the difference
between testing a control and attacking a system.
"""

from __future__ import annotations

import pytest
from faker import Faker

from pages.register_page import NewCustomer, RegisterPage
from utils.config import Settings

fake = Faker("en_CA")


@pytest.fixture(scope="session")
def second_customer(browser, settings: Settings) -> dict:
    """Register a second customer and return their details and account.

    The authorisation tests need two customers. With only the seeded user there
    is no way to ask the question that matters: can one customer reach another
    customer's account.

    Registration runs through the browser because ParaBank has no service
    endpoint for it. Session scoped so it happens once for the whole suite.

    All values are obviously fabricated. The social security number field is
    filled with a formatted placeholder, not a real number.
    """
    details = NewCustomer(
        first_name=fake.first_name(),
        last_name=fake.last_name(),
        street="1 Northline Test Street",
        city="Windsor",
        state="ON",
        zip_code="N9A0A0",
        phone="5550100",
        ssn="000-00-0000",
        username=f"northline_{fake.uuid4()[:8]}",
        password="NorthlineTest1!",
    )

    context = browser.new_context(viewport={"width": 1280, "height": 900})
    page = context.new_page()
    page.set_default_timeout(settings.framework.default_timeout_ms)

    register = RegisterPage(page, settings.sut.base_url).open()
    register.register(details)

    if not register.registration_succeeded():
        message = register.error_text()
        context.close()
        pytest.skip(f"Could not register a second customer. Page said: {message!r}")

    page.goto(f"{settings.sut.base_url}/overview.htm")
    page.wait_for_load_state("networkidle")

    account_ids: list[int] = []
    rows = page.locator("#accountTable tbody tr:has(a)")
    for i in range(rows.count()):
        text = rows.nth(i).locator("td").nth(0).inner_text().strip()
        if text.isdigit():
            account_ids.append(int(text))

    context.close()

    if not account_ids:
        pytest.skip("The second customer was registered but has no accounts")

    return {"details": details, "account_ids": account_ids}
