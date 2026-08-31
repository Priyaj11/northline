"""Transfer amount validation and boundary behaviour.

Covers TC-XFER-008 to TC-XFER-011 and TC-XFER-015.

Separated from test_transfer_api.py because these are about what the service
accepts rather than about whether an accepted transfer moves money correctly.

Two of these establish behaviour rather than assert an expectation.

TC-XFER-010 asks whether an amount carrying more precision than a currency has
is rounded consistently on both sides. Inconsistent rounding is how money leaks
from a real ledger: a fraction of a cent debited and not credited, repeated
across millions of transactions.

TC-XFER-015 answers the question REQ-XFER-007 has carried as an assumption
since it was written: what does the application do when a transfer exceeds the
available balance? The seeded data contains negative balances, which suggests
overdrafts are permitted, but that was never confirmed.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from utils.api_client import ApiClient
from utils.assertions import json_body

pytestmark = pytest.mark.api

DEF_001_SCIENTIFIC = (
    "DEF-001 as amended: ParaBank does not validate the transfer amount. "
    "Scientific notation is parsed as a number and moves money. Confirmed "
    "2026-08-31: an amount of '1e3' returned 200 with the message "
    "\"Successfully transferred $1E+3\", debited 1000.00 from the source and "
    "credited 1000.00 to the destination. Money is conserved, so this is "
    "additional evidence for DEF-001 rather than a separate defect."
)

MALFORMED_AMOUNTS = [
    ("abc", "TC-XFER-008: letters"),
    ("", "TC-XFER-009: empty"),
    ("$100", "TC-XFER-011: a currency symbol"),
    ("1,000.00", "TC-XFER-011: a thousands separator"),
    pytest.param(
        "1e3", "TC-XFER-011: scientific notation",
        marks=pytest.mark.xfail(strict=True, raises=AssertionError,
                                reason=DEF_001_SCIENTIFIC),
    ),
]


def balance(api: ApiClient, account_id: int) -> Decimal:
    return Decimal(str(json_body(api.account(account_id))["balance"]))


@pytest.mark.parametrize("amount, case", MALFORMED_AMOUNTS)
def test_a_malformed_amount_does_not_move_money(
    api: ApiClient, account_pair: tuple[int, int], amount: str, case: str
):
    """TC-XFER-008, TC-XFER-009 and TC-XFER-011 / REQ-XFER-004.

    The browser form may prevent these being typed. That is irrelevant: the
    service can be called directly, so a rule enforced only in the browser is
    not enforced. Asserted on the money rather than the status code, because
    whatever the application answers, it must not move funds on an amount it
    cannot parse.
    """
    source, destination = account_pair
    before_source = balance(api, source)
    before_destination = balance(api, destination)

    response = api.transfer(source, destination, amount)

    after_source = balance(api, source)
    after_destination = balance(api, destination)

    assert after_source == before_source and after_destination == before_destination, (
        f"{case}: a malformed amount {amount!r} moved money.\n"
        f"  response: {response.status_code} {response.text.strip()[:120]!r}\n"
        f"  source {source}: {before_source} became {after_source}\n"
        f"  destination {destination}: {before_destination} became {after_destination}"
    )


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason=(
        "DEF-007: a transfer of 10.005 is accepted, stores a balance with three "
        "decimal places, and the application is then unable to read the affected "
        "accounts. Every subsequent read returns HTTP 500 with "
        "ArithmeticException: Rounding necessary. Confirmed 2026-08-31. This test "
        "CORRUPTS the environment, so it resets the data afterwards; without that "
        "every test running later fails on unrelated account reads."
    ),
)
def test_an_amount_with_excess_precision_debits_and_credits_the_same(
    api: ApiClient, account_pair: tuple[int, int], reset_sut_after
):
    """TC-XFER-010 / REQ-XFER-004.

    Establishes behaviour rather than asserting an expectation. Either outcome
    is defensible on its own:

        refused           the application will not accept sub-cent precision
        rounded           it accepts and rounds to two places

    What is NOT defensible is rounding the two sides differently. A debit of
    10.01 against a credit of 10.00 leaves a cent unaccounted for on every
    transaction, and that is how a real ledger drifts.
    """
    source, destination = account_pair
    amount = Decimal("10.005")

    before_source = balance(api, source)
    before_destination = balance(api, destination)

    response = api.transfer(source, destination, str(amount))

    debited = before_source - balance(api, source)
    credited = balance(api, destination) - before_destination

    print(f"amount 10.005 -> status {response.status_code}, "
          f"debited {debited}, credited {credited}")

    if debited == 0 and credited == 0:
        return  # refused, which is a valid outcome

    assert debited == credited, (
        f"An amount of {amount} debited {debited} and credited {credited}. "
        "The two sides were rounded differently, so money was created or lost."
    )


def test_a_transfer_of_exactly_the_available_balance_is_accepted(
    api: ApiClient, accounts, settings
):
    """TC-XFER-015 / REQ-XFER-007, boundary value analysis at the balance.

    Uses an account with a positive balance, chosen at runtime. Several seeded
    accounts are negative, and "the whole balance" is not a meaningful amount
    on one of those.
    """
    positive = [a for a in accounts if Decimal(str(a["balance"])) > 0]
    if len(positive) < 2:
        pytest.skip("Fewer than two accounts hold a positive balance")

    source = positive[0]["id"]
    destination = positive[1]["id"]
    available = balance(api, source)

    response = api.transfer(source, destination, str(available))
    after = balance(api, source)

    print(f"transferred the whole balance {available} -> status {response.status_code}, "
          f"source now {after}")

    assert after == available - available, (
        f"Transferring the entire balance of {available} should leave 0.00. "
        f"Account {source} holds {after}."
    )


def test_what_happens_when_a_transfer_exceeds_the_available_balance(
    api: ApiClient, accounts
):
    """TC-XFER-015 / REQ-XFER-007.

    REQ-XFER-007 is marked 'assumed' because the application's overdraft rule
    was never established. This test establishes it.

    Whatever the rule turns out to be, one property must hold: the amount
    debited must equal the amount credited. A bank may permit an overdraft or
    refuse one; it may not lose track of the money either way.

    The observed behaviour is printed so the requirement register can be
    corrected to match reality rather than a defect being invented against an
    assumption that was never confirmed.
    """
    positive = [a for a in accounts if Decimal(str(a["balance"])) > 0]
    if len(positive) < 2:
        pytest.skip("Fewer than two accounts hold a positive balance")

    source = positive[0]["id"]
    destination = positive[1]["id"]

    before_source = balance(api, source)
    before_destination = balance(api, destination)
    amount = before_source + Decimal("500.00")

    response = api.transfer(source, destination, str(amount))

    after_source = balance(api, source)
    after_destination = balance(api, destination)
    debited = before_source - after_source
    credited = after_destination - before_destination

    print(
        f"OVERDRAFT BEHAVIOUR: balance {before_source}, attempted {amount}\n"
        f"  status    {response.status_code}\n"
        f"  body      {response.text.strip()[:120]!r}\n"
        f"  debited   {debited}\n"
        f"  credited  {credited}\n"
        f"  source now {after_source}"
    )

    assert debited == credited, (
        f"A transfer of {amount} against a balance of {before_source} debited "
        f"{debited} and credited {credited}. Whether or not the overdraft is "
        "permitted, the two sides must match."
    )
