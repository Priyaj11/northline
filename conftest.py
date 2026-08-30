"""Shared pytest fixtures for the whole Northline suite.

pytest discovers this file automatically, so any test can request `settings` or
`api` without importing anything. It sits at the repository root so it applies
to every suite under tests/.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from utils.api_client import ApiClient
from utils.config import Settings, get_settings
from utils.logger import get_logger

log = get_logger("conftest")


@pytest.fixture(scope="session")
def settings() -> Settings:
    """Configuration, read once per test run."""
    return get_settings()


@pytest.fixture(scope="session")
def api(settings: Settings) -> ApiClient:
    """A logged HTTP client for ParaBank's REST services.

    Session scoped because the client holds no per-test state. Any test that
    needs a clean cookie jar clears it explicitly, which makes that intent
    visible rather than accidental.
    """
    return ApiClient(settings)


@pytest.fixture(scope="session")
def artifacts_dir(settings: Settings) -> Path:
    """Where screenshots, traces and videos from failed tests are written."""
    return settings.artifacts_dir


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Record each test's result on the item itself.

    Fixtures cannot normally see whether the test that used them passed or
    failed. Stashing the report here lets teardown code capture artifacts only
    on failure, instead of writing a screenshot for every passing test and
    filling the disk with pictures of things that worked.
    """
    outcome = yield
    report = outcome.get_result()
    setattr(item, f"report_{report.when}", report)


def pytest_configure(config):
    """Log the environment once at the start of the run."""
    s = get_settings()
    log.info("Northline run | environment=%s | release=%s | SUT=%s",
             s.environment, s.release, s.sut.base_url)
