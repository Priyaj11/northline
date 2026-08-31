"""Fixtures for the accessibility suite.

base_url and browser_context_args come from the root conftest, shared with the
UI suite. Only the timeout is set here, because it has to attach to the page
fixture and an autouse fixture at the root would pull a browser into every
suite, including the ones that never touch one.
"""

from __future__ import annotations

import pytest

from utils.config import Settings


@pytest.fixture(autouse=True)
def _apply_default_timeout(page, settings: Settings):
    page.set_default_timeout(settings.framework.default_timeout_ms)
    yield
