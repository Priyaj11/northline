"""API funds transfer tests.

Covers TC-XFER-002 and the boundary and negative cases TC-XFER-004 to
TC-XFER-007, TC-XFER-012 and TC-XFER-013.

Two design decisions run through this file.

Money is compared as Decimal, never float. Floating point cannot represent 0.01
exactly, so float comparisons produce failures that look like defects and are
not, while hiding the real one-cent errors that are.

Rejection tests assert that no money moved, rather than asserting a particular
status code. Whether the application answers 400 or 200 with an error body is a
contract question. Whether money moved is the banking question, and it is the
one that matters.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from utils.api_client import ApiClient
from utils.assertions import assert_status

pytestmark = pytest.mark.api

NON_EXISTENT_ACCOUNT = 99999999
ZERO = Decimal("0.00")


def test_a_valid_transfer_is_accepted(api: ApiClient, account_pair: tuple[int, int]):
    """TC-XFER-002 / REQ-XFER-001."""
    source, destination = account_pair
    assert_status(api.transfer(source, destination, "1.00"), 200)


def test_a_valid_transfer_moves_exactly_the_amount(
    api: ApiClient, account_pair: tuple[int, int], balance_of
):
    """TC-XFER-002 supporting REQ-XFER-002.

    Asserted on the difference rather than the absolute balance, so the test
    survives any starting state and can run repeatedly. The stronger
    verification against the certification data store arrives in Phase 4.
    """
    source, destination = account_pair
    amount = Decimal("100.00")

    before_source = balance_of(source)
    before_destination = balance_of(destination)

    assert_status(api.transfer(source, destination, str(amount)), 200)

    after_source = balance_of(source)
    after_destination = balance_of(destination)

    assert before_source - after_source == amount, (
        f"Source {source} should have fallen by {amount}, "
        f"went from {before_source} to {after_source}"
    )
    assert after_destination - before_destination == amount, (
        f"Destination {destination} should have risen by {amount}, "
        f"went from {before_destination} to {after_destination}"
    )


def test_the_smallest_valid_amount_is_accepted(
    api: ApiClient, account_pair: tuple[int, int], balance_of
):
    """TC-XFER-006 / REQ-XFER-003, boundary value analysis.

    One step above the boundary. This is the case that catches a comparison
    written as greater than or equal to zero where greater than zero was meant.
    """
    source, destination = account_pair
    amount = Decimal("0.01")

    before_source = balance_of(source)
    before_destination = balance_of(destination)

    assert_status(api.transfer(source, destination, str(amount)), 200)

    assert before_source - balance_of(source) == amount
    assert balance_of(destination) - before_destination == amount


DEF_001 = (
    "DEF-001 as amended: ParaBank does not validate the transfer amount at all. "
    "Negative amounts are accepted and move money in reverse, confirmed "
    "2026-08-30 when -500.00 returned 200 and credited the source by 500.00. "
    "Zero amounts are also accepted and write records, which this layer cannot "
    "detect because no money moves either way; that is covered by "
    "tests/database/test_data_quality.py. Marked strict so the suite fails if "
    "the behaviour is fixed without these tests being updated. The release gate "
    "reads the defect register, not this mark, so the open Critical defect "
    "still forces a NO-GO."
)


@pytest.mark.parametrize(
    "amount, case",
    [
        ("0.00", "TC-XFER-004: the boundary itself"),
        pytest.param(
            "-0.01",
            "TC-XFER-005: one step below the boundary",
            marks=pytest.mark.xfail(strict=True, raises=AssertionError,
                                    reason=DEF_001),
        ),
        pytest.param(
            "-500.00",
            "TC-XFER-007: a representative negative amount",
            marks=pytest.mark.xfail(strict=True, reason=DEF_001),
        ),
    ],
)
def test_invalid_amounts_do_not_move_money(
    api: ApiClient, account_pair: tuple[int, int], balance_of, amount: str, case: str
):
    """TC-XFER-004, TC-XFER-005 and TC-XFER-007 / REQ-XFER-003.

    A negative transfer that succeeds moves money in the opposite direction,
    which is a Critical severity defect. The status code is recorded in the log
    either way; the assertion is about the money.

    Known limitation of this assertion, recorded rather than hidden. The 0.00
    case passes here even though the application ACCEPTS the request, because a
    zero-amount transfer leaves the balances unchanged either way. At this layer
    "refused" and "accepted with no monetary effect" are indistinguishable.

    That gap is closed in tests/database/test_data_quality.py, which asserts
    that no record was written. See the amendment to DEF-001.
    """
    source, destination = account_pair
    before_source = balance_of(source)
    before_destination = balance_of(destination)

    api.transfer(source, destination, amount)

    assert balance_of(source) == before_source, (
        f"{case}: source balance changed after a transfer of {amount}"
    )
    assert balance_of(destination) == before_destination, (
        f"{case}: destination balance changed after a transfer of {amount}"
    )


def test_a_transfer_to_a_non_existent_account_does_not_debit_the_source(
    api: ApiClient, account_pair: tuple[int, int], balance_of
):
    """TC-XFER-012 / REQ-XFER-005.

    A debit with no matching credit is money disappearing. Whatever status the
    application returns, the source balance must be untouched.
    """
    source, _ = account_pair
    before = balance_of(source)
    api.transfer(source, NON_EXISTENT_ACCOUNT, "50.00")
    after = balance_of(source)
    assert after == before, (
        f"Source {source} was debited by a transfer to a non-existent account: "
        f"{before} became {after}"
    )


def test_a_transfer_to_the_same_account_nets_to_zero(
    api: ApiClient, account_pair: tuple[int, int], balance_of
):
    """TC-XFER-013 / REQ-XFER-005, derived from the decision table rule R4.

    Either the transfer is refused, or it completes with a net change of exactly
    zero. Any other outcome means money was created or destroyed.
    """
    source, _ = account_pair
    before = balance_of(source)
    api.transfer(source, source, "25.00")
    after = balance_of(source)
    assert after - before == ZERO, (
        f"A transfer from account {source} to itself changed the balance by "
        f"{after - before}. Money was created or destroyed."
    )


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason=(
        "Known contract defect found in Phase 3A discovery: the transfer endpoint "
        "declares Content-Type: application/json but returns plain English text. "
        "Marked xfail rather than deleted so the defect stays visible and the "
        "suite fails if it is ever fixed without the test being updated. "
        "Written up with evidence in Phase 6."
    ),
)
def test_the_transfer_response_body_matches_its_declared_content_type(
    api: ApiClient, account_pair: tuple[int, int]
):
    """Contract check adjacent to REQ-TXN-003.

    A client that trusts the declared content type and calls a JSON parser
    crashes on this endpoint.
    """
    source, destination = account_pair
    response = api.transfer(source, destination, "0.01")

    declared = response.headers.get("content-type", "").lower()
    if "json" not in declared:
        pytest.skip(f"The endpoint no longer declares JSON, it declares {declared!r}")

    try:
        response.json()
        parses = True
    except ValueError:
        parses = False

    assert parses, (
        f"The endpoint declares Content-Type {declared!r} but the body does not "
        f"parse as JSON. Body: {response.text.strip()[:120]!r}"
    )
