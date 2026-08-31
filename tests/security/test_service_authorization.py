"""Authorisation and authentication on the service layer.

Covers TC-SEC-001, TC-SEC-002, TC-SEC-003, TC-SEC-005 and TC-SEC-008.

Every test here makes at most one request per check and asserts on the outcome.
Nothing is exploited and nothing is enumerated. Where a control is missing, the
evidence is a status code and a statement of what was returned, which is what a
defect report needs and is where the testing stops.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
import requests

from utils.api_client import ApiClient
from utils.assertions import json_body
from utils.config import Settings

pytestmark = pytest.mark.security


DEF_005 = (
    "DEF-005: the REST services require no authentication. Confirmed 2026-08-31: "
    "GET /customers/{id}/accounts and GET /accounts/{id}/transactions both "
    "return HTTP 200 with full financial data when no session, cookie, token or "
    "authorisation header is presented. The absence of authentication also means "
    "there is no object level authorisation, so a second customer's account is "
    "readable by anyone. Marked strict so this fails if the behaviour is fixed "
    "without the tests being updated."
)

DEF_006 = (
    "DEF-006: the login endpoint carries the username and password as URL path "
    "segments, so credentials reach access logs, proxy logs, browser history and "
    "Referer headers in plain text."
)

DEF_001 = (
    "DEF-001 as amended: ParaBank does not validate the transfer amount. A "
    "negative amount sent directly to the service moves money in reverse. "
    "Confirmed here 2026-08-31: -250.00 moved account 12345 from -2300.00 to "
    "-2050.00. Recorded from the security angle as well, because it shows that a "
    "rule enforced only in the browser form is not enforced at all."
)


def _unauthenticated_get(url: str) -> requests.Response:
    """A request with no session, no cookie and no credentials of any kind.

    A fresh requests.get rather than the shared client, because the shared
    client's session may hold cookies from an earlier call and the whole point
    of these checks is that nothing is presented.
    """
    return requests.get(url, headers={"Accept": "application/json"}, timeout=30)


@pytest.mark.xfail(strict=True, raises=AssertionError, reason=DEF_005)
def test_account_data_requires_authentication(api: ApiClient, settings: Settings):
    """TC-SEC-001 / REQ-SEC-001.

    Phase 1 observed the service returning full account data with no
    credentials. This is the test that states it as a requirement failure
    rather than an observation.
    """
    customer = json_body(api.login(settings.sut.username, settings.sut.password))
    url = f"{settings.sut.services_url}/customers/{customer['id']}/accounts"

    response = _unauthenticated_get(url)

    returned_data = False
    if response.status_code == 200:
        try:
            body = response.json()
            returned_data = isinstance(body, list) and len(body) > 0
        except ValueError:
            returned_data = False

    assert not returned_data, (
        f"Account data was returned with no credentials of any kind.\n"
        f"  request:  GET {url}\n"
        f"  headers:  Accept only, no cookie, no token, no authorisation\n"
        f"  status:   {response.status_code}\n"
        f"  returned: {len(response.json())} account record(s) including balances"
    )


@pytest.mark.xfail(strict=True, raises=AssertionError, reason=DEF_005)
def test_transaction_data_requires_authentication(api: ApiClient, settings: Settings):
    """TC-SEC-002 / REQ-SEC-001."""
    customer = json_body(api.login(settings.sut.username, settings.sut.password))
    accounts = json_body(api.customer_accounts(customer["id"]))
    account_id = accounts[0]["id"]
    url = f"{settings.sut.services_url}/accounts/{account_id}/transactions"

    response = _unauthenticated_get(url)

    returned_data = False
    if response.status_code == 200:
        try:
            returned_data = isinstance(response.json(), list)
        except ValueError:
            returned_data = False

    assert not returned_data, (
        f"Transaction history was returned with no credentials.\n"
        f"  request: GET {url}\n"
        f"  status:  {response.status_code}"
    )


@pytest.mark.xfail(strict=True, raises=AssertionError, reason=DEF_005)
def test_one_customer_cannot_read_another_customers_account(
    settings: Settings, second_customer: dict
):
    """TC-SEC-003 / REQ-SEC-002, Broken Object Level Authorisation.

    The most consequential authorisation question in a banking application: does
    the system check that a record belongs to the requester, or only that a
    requester exists.

    One request against one account belonging to the second customer. No
    enumeration, no attempt to read more.
    """
    other_account = second_customer["account_ids"][0]
    url = f"{settings.sut.services_url}/accounts/{other_account}"

    response = _unauthenticated_get(url)

    exposed = False
    if response.status_code == 200:
        try:
            body = response.json()
            exposed = isinstance(body, dict) and "balance" in body
        except ValueError:
            exposed = False

    assert not exposed, (
        f"An account belonging to another customer was returned without that "
        f"customer's credentials.\n"
        f"  request: GET {url}\n"
        f"  status:  {response.status_code}\n"
        f"  account {other_account} belongs to the customer registered by this suite"
    )


@pytest.mark.xfail(strict=True, raises=AssertionError, reason=DEF_006)
def test_credentials_are_not_carried_in_the_url_path(settings: Settings):
    """TC-SEC-005 / REQ-SEC-003.

    A Uniform Resource Locator is written to server access logs, browser
    history, proxy logs and referrer headers. None of those are treated as
    secret stores, so a password in the path is a password in plain text in
    several places nobody protects.

    This inspects the endpoint's declared shape rather than sending a password
    anywhere new.
    """
    wadl = requests.get(f"{settings.sut.services_url}?_wadl", timeout=30).text

    assert "login/{username}/{password}" not in wadl, (
        "The service declares a login endpoint that takes the username and "
        "password as URL path segments:\n"
        "    GET /services/bank/login/{username}/{password}\n"
        "Credentials should be carried in a request body or an authorisation "
        "header, neither of which is logged by default."
    )


@pytest.mark.xfail(strict=True, raises=AssertionError, reason=DEF_001)
def test_amount_validation_is_enforced_on_the_server(
    api: ApiClient, settings: Settings
):
    """TC-SEC-008 / REQ-SEC-004.

    The browser form may prevent a negative amount being typed. That is a
    convenience for users, not a control: the service can be called directly,
    so a rule enforced only in the browser is not enforced at all.

    Asserts on the ledger rather than the status code, because whether money
    moved is the question that matters.
    """
    customer = json_body(api.login(settings.sut.username, settings.sut.password))
    accounts = json_body(api.customer_accounts(customer["id"]))
    source, destination = accounts[0]["id"], accounts[1]["id"]

    before = Decimal(str(json_body(api.account(source))["balance"]))
    api.transfer(source, destination, "-250.00")
    after = Decimal(str(json_body(api.account(source))["balance"]))

    assert after == before, (
        f"A negative amount sent directly to the service, bypassing the browser "
        f"form, changed account {source} from {before} to {after}. "
        "Validation present only in the browser is not a control."
    )
