"""API authentication tests.

Covers TC-AUTH-002 and the service-side half of TC-AUTH-003 and TC-AUTH-004.
"""

from __future__ import annotations

import pytest

from utils.api_client import ApiClient
from utils.assertions import assert_fields, json_body
from utils.config import Settings

pytestmark = pytest.mark.api


def test_login_with_valid_credentials_returns_a_customer(api: ApiClient, settings: Settings):
    """TC-AUTH-002 / REQ-AUTH-001."""
    body = json_body(api.login(settings.sut.username, settings.sut.password))
    assert_fields(
        body,
        {"id": int, "firstName": str, "lastName": str, "phoneNumber": str},
        "login response",
    )


def test_login_response_includes_a_structured_address(api: ApiClient, settings: Settings):
    """TC-AUTH-002 / REQ-AUTH-001, checking the nested object shape."""
    body = json_body(api.login(settings.sut.username, settings.sut.password))
    assert "address" in body, f"No address in login response. Present: {sorted(body)}"
    assert_fields(
        body["address"],
        {"street": str, "city": str, "state": str, "zipCode": str},
        "login response address",
    )


@pytest.mark.parametrize(
    "username, password, case",
    [
        ("john", "wrongpassword", "valid username, wrong password"),
        ("nosuchuser", "demo", "unknown username"),
        ("nosuchuser", "wrongpassword", "unknown username and wrong password"),
    ],
)
def test_login_with_invalid_credentials_returns_no_customer(
    api: ApiClient, username: str, password: str, case: str
):
    """TC-AUTH-003 and TC-AUTH-004 / REQ-AUTH-002.

    The assertion is deliberately about the outcome that matters rather than a
    specific status code: an invalid login must not hand back a customer
    record. That holds whether the application answers 400, 401 or 200 with an
    error body, and it is the property a bank actually cares about.
    """
    response = api.login(username, password)
    if response.status_code != 200:
        return
    try:
        body = response.json()
    except ValueError:
        return
    assert not (isinstance(body, dict) and "id" in body), (
        f"Invalid login ({case}) returned a customer record: {body!r}"
    )
