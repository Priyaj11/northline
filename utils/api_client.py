"""HTTP client for ParaBank's REST services.

One place that knows the base address, sets headers, applies timeouts, and logs
every request and response. It deliberately makes NO assumptions about response
shape: it returns the raw response object and lets each test assert on the
content. A client that parses responses hides exactly the detail a failing test
needs to show you.

Logging every request matters more than it looks. When a test fails in a
pipeline nobody is watching, the log is the only witness to what was actually
sent and what came back.
"""

from __future__ import annotations

from typing import Any

import requests

from utils.config import Settings
from utils.logger import get_logger

log = get_logger("api")

MAX_LOGGED_BODY_CHARS = 400


class ApiClient:
    """A thin, logged wrapper around a requests session."""

    def __init__(self, settings: Settings) -> None:
        self._base = settings.sut.services_url
        self._timeout = settings.framework.api_timeout_s
        self._session = requests.Session()
        self._session.headers.update({"Accept": "application/json"})

    @property
    def base_url(self) -> str:
        return self._base

    @property
    def session(self) -> requests.Session:
        """Exposed so tests can inspect or clear cookies deliberately."""
        return self._session

    def _url(self, path: str) -> str:
        return f"{self._base}/{path.lstrip('/')}"

    def request(self, method: str, path: str, **kwargs: Any) -> requests.Response:
        url = self._url(path)
        kwargs.setdefault("timeout", self._timeout)
        log.info("-> %s %s %s", method.upper(), url, kwargs.get("params") or "")
        response = self._session.request(method, url, **kwargs)
        body = (response.text or "").strip().replace("\n", " ")
        if len(body) > MAX_LOGGED_BODY_CHARS:
            body = body[:MAX_LOGGED_BODY_CHARS] + " ...truncated"
        log.info("<- %s %s in %d ms | %s",
                 response.status_code, url,
                 int(response.elapsed.total_seconds() * 1000), body)
        return response

    def get(self, path: str, **kwargs: Any) -> requests.Response:
        return self.request("GET", path, **kwargs)

    def post(self, path: str, **kwargs: Any) -> requests.Response:
        return self.request("POST", path, **kwargs)

    def login(self, username: str, password: str) -> requests.Response:
        """ParaBank's login endpoint takes credentials as path segments.

        This shape is recorded as security observation REQ-SEC-003 and tested by
        TC-SEC-005. The client mirrors the application as it is; it does not
        pretend the interface is better designed than it is.
        """
        return self.get(f"/login/{username}/{password}")

    def customer_accounts(self, customer_id: int | str) -> requests.Response:
        return self.get(f"/customers/{customer_id}/accounts")

    def account(self, account_id: int | str) -> requests.Response:
        return self.get(f"/accounts/{account_id}")

    def account_transactions(self, account_id: int | str) -> requests.Response:
        return self.get(f"/accounts/{account_id}/transactions")

    def transfer(self, from_account_id: Any, to_account_id: Any, amount: Any) -> requests.Response:
        return self.post("/transfer", params={
            "fromAccountId": from_account_id,
            "toAccountId": to_account_id,
            "amount": amount,
        })

    def clean_db(self) -> requests.Response:
        return self.post("/cleanDB")

    def initialize_db(self) -> requests.Response:
        return self.post("/initializeDB")
