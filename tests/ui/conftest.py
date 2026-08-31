"""Fixtures for the browser suite.

pytest-playwright supplies the browser, context and page fixtures, the
--browser flag for cross-browser runs, and the failure artifact options. This
file configures those rather than reimplementing them.

Failure artifacts are requested on the command line, not here, because they are
run options rather than code:

    --screenshot=only-on-failure
    --video=retain-on-failure
    --tracing=retain-on-failure
    --output=reports/artifacts

Those are wired into the `make ui` target. Capturing artifacts only on failure
matters: capturing them always fills the disk with pictures of things that
worked, and slows every run to pay for evidence nobody reads.
"""

from __future__ import annotations

from typing import Any

import pytest

from utils.config import Settings


@pytest.fixture(autouse=True)
def _apply_default_timeout(page, settings: Settings):
    """Apply the configured timeout to every browser action.

    Playwright's default is 30 seconds. Ours is shorter and configurable, so a
    genuinely stuck test fails in a useful amount of time rather than holding a
    pipeline open.
    """
    page.set_default_timeout(settings.framework.default_timeout_ms)
    yield


@pytest.fixture
def overview(page, base_url: str, settings: Settings):
    """A logged-in session sitting on the account overview.

    Most browser tests need a session before they can do anything. Doing it
    through the interface rather than by injecting a cookie means the login
    path is exercised on every run, and it keeps the test honest about what a
    real user does.
    """
    from pages.login_page import LoginPage
    from pages.overview_page import OverviewPage

    LoginPage(page, base_url).open().log_in_as(settings.sut.username, settings.sut.password)
    return OverviewPage(page, base_url).wait_until_loaded()
