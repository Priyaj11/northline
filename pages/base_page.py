"""Base class for every page object.

A page object owns the selectors for one page and exposes methods named after
what a user does, not what the automation clicks. Tests then read as behaviour:

    login_page.log_in_as("john", "demo")

rather than as a list of clicks. Two benefits. A renamed field is a one-line
change here instead of an edit across forty tests. And a test that reads as
behaviour can be reviewed by someone who does not write code, which in a bank
is often the analyst who wrote the requirement.

Page objects hold no assertions. They describe the page; tests decide what is
correct. Mixing the two produces objects that can only be used by the one test
they were written for.
"""

from __future__ import annotations

from urllib.parse import urlparse

from playwright.sync_api import Locator, Page


class BasePage:
    """Shared navigation and error handling."""

    #: Overridden by each subclass, e.g. "/transfer.htm"
    path: str = "/index.htm"

    def __init__(self, page: Page, base_url: str) -> None:
        self.page = page
        self.base_url = base_url.rstrip("/")

    @property
    def url(self) -> str:
        return f"{self.base_url}{self.path}"

    def open(self):
        self.page.goto(self.url)
        return self

    @property
    def current_path(self) -> str:
        """The path portion of the current address, for landing assertions."""
        return urlparse(self.page.url).path

    @property
    def title_text(self) -> str:
        heading = self.page.locator("h1.title, h1").first
        return heading.inner_text().strip() if heading.count() else ""

    @property
    def error(self) -> Locator:
        """ParaBank renders validation and login failures inside .error."""
        return self.page.locator(".error").first

    def error_text(self) -> str:
        """The visible error message, or an empty string if there is none.

        Returns a string rather than raising, so a test can assert on the
        absence of an error as easily as on its content.
        """
        locator = self.error
        if locator.count() == 0:
            return ""
        try:
            return locator.inner_text().strip()
        except Exception:  # noqa: BLE001 - an element that vanished is simply no error
            return ""
