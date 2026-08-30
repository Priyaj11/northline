"""Browser tests for the account overview.

Covers TC-ACCT-001, TC-ACCT-003 and TC-AUTH-009.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from pages.login_page import LoginPage
from pages.overview_page import OverviewPage
from utils.api_client import ApiClient
from utils.assertions import json_body
from utils.config import Settings

pytestmark = pytest.mark.ui


def test_the_overview_lists_the_customers_accounts(overview: OverviewPage):
    """TC-ACCT-001 / REQ-ACCT-001."""
    balances = overview.account_balances()
    assert balances, "The account overview showed no accounts"
    for account_id in balances:
        assert account_id > 0, f"Unexpected account identifier {account_id}"


def test_the_overview_shows_every_account_the_service_reports(
    overview: OverviewPage, api: ApiClient, settings: Settings
):
    """TC-ACCT-001 / REQ-ACCT-001.

    Two independent routes to the same fact must agree. A screen missing an
    account is as serious as a screen showing a wrong balance.
    """
    customer = json_body(api.login(settings.sut.username, settings.sut.password))
    from_service = {a["id"] for a in json_body(api.customer_accounts(customer["id"]))}
    on_screen = set(overview.account_balances())

    assert on_screen == from_service, (
        "The overview and the service disagree about which accounts exist.\n"
        f"  only on screen:  {sorted(on_screen - from_service)}\n"
        f"  only in service: {sorted(from_service - on_screen)}"
    )


def test_every_displayed_balance_matches_the_service(
    overview: OverviewPage, api: ApiClient, settings: Settings
):
    """TC-ACCT-003 / REQ-ACCT-003.

    This catches the most dangerous class of banking defect: an interface that
    displays a wrong number confidently. Compared as Decimal so that a one cent
    difference is caught rather than lost to floating point.
    """
    customer = json_body(api.login(settings.sut.username, settings.sut.password))
    service_balances = {
        a["id"]: Decimal(str(a["balance"]))
        for a in json_body(api.customer_accounts(customer["id"]))
    }
    displayed = overview.account_balances()

    mismatches = {
        account_id: (shown, service_balances.get(account_id))
        for account_id, shown in displayed.items()
        if service_balances.get(account_id) != shown
    }
    assert not mismatches, (
        "Displayed balances differ from the service:\n"
        + "\n".join(
            f"  account {aid}: screen {shown}, service {expected}"
            for aid, (shown, expected) in mismatches.items()
        )
    )


def test_logging_out_returns_to_the_login_page(overview: OverviewPage, page, base_url: str):
    """TC-AUTH-009 / REQ-AUTH-004, a state transition from logged in to logged out."""
    overview.log_out()
    assert LoginPage(page, base_url).is_displayed(), (
        f"After logging out the login form was not shown. Ended at {page.url}"
    )
