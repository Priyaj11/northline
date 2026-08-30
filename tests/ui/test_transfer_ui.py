"""Browser tests for funds transfer.

Covers TC-XFER-001 and, when the suite is run across browsers, the browser
dimension of the pairwise selection in TC-XFER-016.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from pages.overview_page import OverviewPage
from pages.transfer_page import TransferPage
from utils.api_client import ApiClient
from utils.assertions import json_body

pytestmark = pytest.mark.ui


def _balance(api: ApiClient, account_id: int) -> Decimal:
    return Decimal(str(json_body(api.account(account_id))["balance"]))


def test_a_valid_transfer_shows_a_confirmation(
    overview: OverviewPage, page, base_url: str
):
    """TC-XFER-001 / REQ-XFER-001."""
    accounts = overview.account_ids()
    assert len(accounts) >= 2, f"Need at least two accounts, found {len(accounts)}"
    source, destination = accounts[0], accounts[1]

    transfer = TransferPage(page, base_url).open()
    transfer.transfer("100.00", source, destination)

    result = transfer.result_text()
    assert str(source) in result and str(destination) in result, (
        f"The confirmation did not name both accounts.\n{result}"
    )
    assert "100" in result, f"The confirmation did not name the amount.\n{result}"


def test_a_transfer_through_the_browser_moves_exactly_the_amount(
    overview: OverviewPage, page, base_url: str, api: ApiClient
):
    """TC-XFER-001 supporting REQ-XFER-002.

    The confirmation message is not evidence that money moved. The balances are.
    Asserted as a difference so the test survives any starting state, and read
    through the service so the check is independent of the screen that
    performed the transfer.
    """
    accounts = overview.account_ids()
    source, destination = accounts[0], accounts[1]
    amount = Decimal("50.00")

    before_source = _balance(api, source)
    before_destination = _balance(api, destination)

    TransferPage(page, base_url).open().transfer(str(amount), source, destination)

    assert before_source - _balance(api, source) == amount, (
        f"Source {source} did not fall by {amount}"
    )
    assert _balance(api, destination) - before_destination == amount, (
        f"Destination {destination} did not rise by {amount}"
    )


def test_the_transfer_page_offers_the_customers_accounts(
    overview: OverviewPage, page, base_url: str
):
    """REQ-XFER-001. The dropdowns must offer exactly the accounts the customer
    owns. An account belonging to someone else appearing here would be an
    authorisation defect, not a display bug."""
    expected = set(overview.account_ids())
    offered = set(TransferPage(page, base_url).open().available_account_ids())
    assert offered == expected, (
        "The transfer dropdown does not match the customer's accounts.\n"
        f"  only offered: {sorted(offered - expected)}\n"
        f"  only owned:   {sorted(expected - offered)}"
    )
