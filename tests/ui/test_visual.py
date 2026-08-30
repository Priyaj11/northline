"""Visual regression on the pages that carry no data.

Deliberately small. Two pages, not twenty.

Visual regression compares a screenshot against a stored baseline and fails on
any pixel difference. That makes it powerful for catching layout breakage and
useless on anything data-driven: the account overview shows balances, and every
transfer test moves money, so a snapshot of it would fail whenever the data
changed rather than whenever the layout broke. A suite that cries wolf is a
suite people stop reading.

Only the login and registration pages are snapshotted. Both are static markup.

The comparison lives in utils/visual.py, because the Python binding of
Playwright has no screenshot assertion. That exists only in the JavaScript
binding.

Baselines are per browser and live in tests/ui/baselines/<browser>/.
To accept a change after reviewing it:

    NORTHLINE_UPDATE_BASELINES=1 .venv/bin/python -m pytest tests/ui/test_visual.py
"""

from __future__ import annotations

import pytest

from utils.visual import assert_matches_baseline

pytestmark = pytest.mark.ui

#: A small allowance for font anti-aliasing between runs on the same machine.
#: Zero would be ideal, but text edges move by a pixel or two and a suite that
#: fails on that gets ignored, which is worse than a small tolerance.
TOLERANCE = 0.001  # 0.1 percent of pixels


#: The Latest News panel renders today's date as <li class="captionthree">.
#: Without masking it, this baseline would fail every day at midnight for a
#: reason that has nothing to do with layout. Masking covers the smallest
#: region that actually changes and still compares everything around it.
DATE_MASK = ["ul.events li.captionthree"]


def test_the_login_page_looks_unchanged(page, base_url: str, browser_name: str):
    """Catches layout breakage on the application's entry point."""
    page.goto(f"{base_url}/index.htm")
    page.wait_for_load_state("networkidle")
    assert_matches_baseline(page, "login-page.png", browser_name, TOLERANCE,
                            mask=DATE_MASK)


def test_the_registration_page_looks_unchanged(page, base_url: str, browser_name: str):
    """The longest form in the application, so the one most likely to break
    visually when styling changes."""
    page.goto(f"{base_url}/register.htm")
    page.wait_for_load_state("networkidle")
    assert_matches_baseline(page, "register-page.png", browser_name, TOLERANCE)


# Verification note, 2026-08-30.
#
# The comparator was checked by deliberately substituting the registration page
# baseline for the login page one. It failed with 29.2497 percent of pixels
# changed against a tolerance of 0.1 percent, then passed again once the correct
# baseline was restored.
#
# A visual suite that has only ever passed proves nothing. Until it has been
# seen to fail on a real difference, a broken comparator and a correct page look
# identical from the outside.
