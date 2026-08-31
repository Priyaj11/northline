"""Session handling in the browser.

Covers TC-SEC-004, TC-SEC-006 and TC-SEC-007.

The service layer has no sessions at all, which is itself the finding in
TC-SEC-001. The browser layer does, so these are the tests that can ask whether
a session is required, whether it ends, and what protections its cookie carries.
"""

from __future__ import annotations

import pytest

from pages.login_page import LoginPage
from pages.overview_page import OverviewPage
from utils.config import Settings

pytestmark = pytest.mark.security

PROTECTED_PAGES = ["/overview.htm", "/transfer.htm", "/billpay.htm"]


@pytest.mark.parametrize("path", PROTECTED_PAGES)
def test_a_protected_page_returns_no_customer_data_without_a_session(
    page, base_url: str, path: str
):
    """TC-SEC-006 / REQ-SEC-004.

    Requesting an authenticated page directly with no session must not return
    customer data. Either a refusal or a redirect to login is acceptable; what
    is not acceptable is account information appearing.
    """
    page.context.clear_cookies()
    page.goto(f"{base_url}{path}")
    page.wait_for_load_state("networkidle")

    account_rows = page.locator("#accountTable tbody tr:has(a)")
    assert account_rows.count() == 0, (
        f"{path} showed {account_rows.count()} account row(s) with no session established. "
        f"Ended at {page.url}"
    )


def test_the_session_ends_when_the_customer_logs_out(
    page, base_url: str, settings: Settings
):
    """TC-SEC-004 / REQ-SEC-004, the logged-out to logged-in transition reversed.

    A page address noted while logged in must stop working after logging out.
    Browsers keep history, and a shared or stolen machine makes this a real
    exposure rather than a theoretical one.
    """
    LoginPage(page, base_url).open().log_in_as(settings.sut.username, settings.sut.password)
    overview = OverviewPage(page, base_url).wait_until_loaded()
    assert overview.account_balances(), "Setup failed: no accounts visible while logged in"

    overview.log_out()

    page.goto(f"{base_url}/overview.htm")
    page.wait_for_load_state("networkidle")
    rows = page.locator("#accountTable tbody tr:has(a)")
    assert rows.count() == 0, (
        f"After logging out, the account overview still showed {rows.count()} "
        f"account row(s). Ended at {page.url}"
    )


def test_the_session_cookie_carries_its_protections(
    page, base_url: str, settings: Settings
):
    """TC-SEC-007 / REQ-SEC-004.

    Records what protections the session cookie declares.

    HttpOnly stops page scripts reading the cookie, which is the difference
    between a scripting flaw exposing a session and merely defacing a page.
    Secure stops it travelling over plain HTTP. Secure cannot be expected here,
    because the local environment is served over HTTP, so it is recorded rather
    than asserted.
    """
    LoginPage(page, base_url).open().log_in_as(settings.sut.username, settings.sut.password)

    cookies = [c for c in page.context.cookies() if c["name"].upper() == "JSESSIONID"]
    assert cookies, f"No session cookie was set. Cookies present: {[c['name'] for c in page.context.cookies()]}"

    cookie = cookies[0]
    print(
        f"session cookie: name={cookie['name']} httpOnly={cookie.get('httpOnly')} "
        f"secure={cookie.get('secure')} sameSite={cookie.get('sameSite')} "
        f"path={cookie.get('path')}"
    )

    assert cookie.get("httpOnly") is True, (
        "The session cookie is not marked HttpOnly, so any script running on the "
        "page can read it. Attributes observed: "
        f"httpOnly={cookie.get('httpOnly')} secure={cookie.get('secure')} "
        f"sameSite={cookie.get('sameSite')}"
    )


def test_discarding_the_session_cookie_ends_access(
    page, base_url: str, settings: Settings
):
    """TC-SEC-007 / REQ-SEC-004.

    ParaBank has no server-side session timeout endpoint, so a timeout cannot be
    triggered on demand and is not tested. What can be tested is that the cookie
    is what grants access: discard it and access must stop.

    Stated as a limitation rather than worked around.
    """
    LoginPage(page, base_url).open().log_in_as(settings.sut.username, settings.sut.password)
    OverviewPage(page, base_url).wait_until_loaded()

    page.context.clear_cookies()

    page.goto(f"{base_url}/overview.htm")
    page.wait_for_load_state("networkidle")
    rows = page.locator("#accountTable tbody tr:has(a)")
    assert rows.count() == 0, (
        f"Account data was still shown after the session cookie was discarded: "
        f"{rows.count()} row(s) at {page.url}"
    )
