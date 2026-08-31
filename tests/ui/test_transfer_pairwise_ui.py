"""Pairwise transfer coverage across browsers, account types and amount classes.

Covers TC-XFER-016.

WHY NINE COMBINATIONS RATHER THAN EIGHTEEN

Three factors: browser (Chromium, Firefox, WebKit), account type (CHECKING,
SAVINGS) and amount class (minimum valid, typical, maximum valid). That is 18
full combinations and 21 distinct pairs of values.

Most defects arise from an interaction between two factors rather than five, so
covering every PAIR is nearly as effective as covering every combination at half
the cost. The nine combinations below were computed by greedy pair coverage and
verified to cover all 21 pairs; they are listed in docs/test-design-techniques.md.

The browser dimension comes from pytest-playwright's --browser flag rather than
from this table, so running the suite in one browser executes the three rows for
that browser and running it in all three executes all nine.

The honest limitation: pairwise finds defects caused by two factors
interacting. A defect appearing only when all three specific values occur
together can be missed. That is an accepted trade, not an oversight.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from pages.overview_page import OverviewPage
from pages.transfer_page import TransferPage
from utils.api_client import ApiClient
from utils.assertions import json_body

pytestmark = pytest.mark.ui

#: (browser, account type, amount class). Computed by greedy pair coverage over
#: 3 x 2 x 3 factors: nine rows covering all 21 pairs, down from 18 combinations.
PAIRWISE = [
    ("chromium", "CHECKING", "minimum"),
    ("chromium", "SAVINGS", "typical"),
    ("chromium", "SAVINGS", "maximum"),
    ("firefox", "CHECKING", "typical"),
    ("firefox", "SAVINGS", "minimum"),
    ("firefox", "CHECKING", "maximum"),
    ("webkit", "CHECKING", "maximum"),
    ("webkit", "SAVINGS", "minimum"),
    ("webkit", "CHECKING", "typical"),
]

AMOUNTS = {
    "minimum": Decimal("0.01"),
    "typical": Decimal("100.00"),
    "maximum": Decimal("1000.00"),
}


def balance(api: ApiClient, account_id: int) -> Decimal:
    return Decimal(str(json_body(api.account(account_id))["balance"]))


@pytest.mark.parametrize(
    "target_browser, account_type, amount_class",
    [pytest.param(*row, id=f"{row[0]}-{row[1]}-{row[2]}") for row in PAIRWISE],
)
def test_a_transfer_from_each_pairwise_combination(
    overview: OverviewPage, page, base_url: str, api: ApiClient,
    browser_name: str, target_browser: str, account_type: str, amount_class: str,
    settings,
):
    """TC-XFER-016 / REQ-XFER-001.

    Skips the rows for browsers other than the one currently running, so the
    same table produces three executions under --browser chromium and all nine
    under all three browsers.
    """
    if browser_name != target_browser:
        pytest.skip(f"row is for {target_browser}, this run is {browser_name}")

    customer = json_body(api.login(settings.sut.username, settings.sut.password))
    accounts = json_body(api.customer_accounts(customer["id"]))

    matching = [a["id"] for a in accounts if a["type"] == account_type]
    if not matching:
        pytest.skip(f"the demo customer owns no {account_type} account")

    source = matching[0]
    destination = next(a["id"] for a in accounts if a["id"] != source)
    amount = AMOUNTS[amount_class]

    before_source = balance(api, source)
    before_destination = balance(api, destination)

    TransferPage(page, base_url).open().transfer(str(amount), source, destination)

    assert before_source - balance(api, source) == amount, (
        f"{browser_name}/{account_type}/{amount_class}: source {source} did not "
        f"fall by {amount}"
    )
    assert balance(api, destination) - before_destination == amount, (
        f"{browser_name}/{account_type}/{amount_class}: destination {destination} "
        f"did not rise by {amount}"
    )
