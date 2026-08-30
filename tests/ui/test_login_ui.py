"""Browser tests for authentication.

Covers TC-AUTH-001, TC-AUTH-003, TC-AUTH-004, TC-AUTH-005 and
TC-AUTH-006 to TC-AUTH-008.
"""

from __future__ import annotations

import pytest

from pages.login_page import LoginPage
from utils.config import Settings

pytestmark = pytest.mark.ui

OVERVIEW_PATH = "/parabank/overview.htm"


@pytest.fixture
def login_page(page, base_url: str) -> LoginPage:
    return LoginPage(page, base_url).open()


def test_valid_credentials_reach_the_account_overview(
    login_page: LoginPage, settings: Settings
):
    """TC-AUTH-001 / REQ-AUTH-001."""
    login_page.log_in_as(settings.sut.username, settings.sut.password)
    assert login_page.current_path == OVERVIEW_PATH, (
        f"Expected to land on {OVERVIEW_PATH}, ended at {login_page.page.url}. "
        f"Error shown: {login_page.error_text()!r}"
    )


@pytest.mark.parametrize(
    "username, password, case",
    [
        ("john", "wrongpassword", "TC-AUTH-003: valid username, wrong password"),
        ("nosuchuser", "demo", "TC-AUTH-004: unknown username"),
    ],
)
def test_invalid_credentials_are_refused(
    login_page: LoginPage, username: str, password: str, case: str
):
    """TC-AUTH-003 and TC-AUTH-004 / REQ-AUTH-002."""
    login_page.log_in_as(username, password)
    assert login_page.current_path != OVERVIEW_PATH, (
        f"{case}: invalid credentials reached the account overview"
    )
    assert login_page.error_text(), f"{case}: no error message was shown"


def test_the_error_message_does_not_reveal_which_credential_was_wrong(
    login_page: LoginPage, page, base_url: str, settings: Settings
):
    """TC-AUTH-005 / REQ-AUTH-002, username enumeration.

    If a wrong password produces a different message from an unknown username,
    an attacker can confirm which usernames exist by reading the message.
    """
    login_page.log_in_as(settings.sut.username, "wrongpassword")
    wrong_password_message = login_page.error_text()

    fresh = LoginPage(page, base_url).open()
    fresh.log_in_as("nosuchuser", "wrongpassword")
    unknown_user_message = fresh.error_text()

    assert wrong_password_message, "No error shown for a wrong password"
    assert unknown_user_message, "No error shown for an unknown username"
    assert wrong_password_message == unknown_user_message, (
        "The application reveals which credential was wrong.\n"
        f"  wrong password   -> {wrong_password_message!r}\n"
        f"  unknown username -> {unknown_user_message!r}"
    )


@pytest.mark.parametrize(
    "username, password, case",
    [
        ("", "demo", "TC-AUTH-006: empty username"),
        ("john", "", "TC-AUTH-007: empty password"),
        ("", "", "TC-AUTH-008: both fields empty"),
    ],
)
def test_empty_credentials_are_refused(
    login_page: LoginPage, username: str, password: str, case: str
):
    """TC-AUTH-006 to TC-AUTH-008 / REQ-AUTH-003, boundary value analysis.

    The boundary here is zero characters. A blank field must not create a
    session, whatever the message says.
    """
    login_page.submit_empty(username, password)
    assert login_page.current_path != OVERVIEW_PATH, (
        f"{case}: an empty credential reached the account overview"
    )
    assert login_page.error_text(), f"{case}: no validation message was shown"
