"""Assertion helpers for ParaBank's API.

ParaBank's responses are not uniform. Discovery in Phase 3A established that:

  - Success responses on read endpoints are JSON.
  - The transfer endpoint declares application/json but returns plain English
    text, so a client that trusts the declared content type crashes.
  - Error responses return text/plain with a 4xx status.

These helpers make every test check the status before attempting to parse, and
produce a failure message that shows the status, the content type and the start
of the body, so a failing test explains itself without a debugging session.
"""

from __future__ import annotations

from typing import Any

import requests

PREVIEW_CHARS = 200


def _describe(response: requests.Response) -> str:
    body = (response.text or "").strip().replace("\n", " ")
    if len(body) > PREVIEW_CHARS:
        body = body[:PREVIEW_CHARS] + " ...truncated"
    return (
        f"status={response.status_code} "
        f"content-type={response.headers.get('content-type', 'not stated')} "
        f"body={body!r}"
    )


def assert_status(response: requests.Response, expected: int) -> None:
    assert response.status_code == expected, (
        f"Expected HTTP {expected} from {response.request.method} {response.request.url}, "
        f"got {_describe(response)}"
    )


def assert_client_error(response: requests.Response) -> None:
    """A 4xx, not a 5xx. A server error means the application crashed rather
    than rejecting the request, which is itself a defect."""
    assert 400 <= response.status_code < 500, (
        f"Expected a 4xx client error from {response.request.method} {response.request.url}, "
        f"got {_describe(response)}"
    )


def json_body(response: requests.Response, expected_status: int = 200) -> Any:
    """Assert the status, then parse the body as JSON with a useful failure."""
    assert_status(response, expected_status)
    try:
        return response.json()
    except ValueError as exc:
        raise AssertionError(
            f"Expected a JSON body from {response.request.method} {response.request.url} "
            f"but parsing failed ({exc}). {_describe(response)}"
        ) from exc


def assert_fields(record: dict, expected: dict[str, type | tuple[type, ...]], label: str) -> None:
    """Assert a record has each named field with the expected Python type."""
    assert isinstance(record, dict), f"{label}: expected an object, got {type(record).__name__}"
    for name, kind in expected.items():
        assert name in record, f"{label}: missing field '{name}'. Present: {sorted(record)}"
        value = record[name]
        assert isinstance(value, kind), (
            f"{label}: field '{name}' should be {kind}, got {type(value).__name__} ({value!r})"
        )
