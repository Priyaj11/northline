"""Central configuration for the Northline framework.

Every value is read from an environment variable so that nothing
environment specific and no credential is hard coded in the repository.
Local defaults point at the docker compose stack defined in
docker-compose.yml.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent

load_dotenv(REPO_ROOT / ".env")


def _env(name: str, default: str) -> str:
    value = os.getenv(name, default)
    if value is None or value == "":
        raise ValueError(f"Environment variable {name} is empty and has no default")
    return value


def _env_bool(name: str, default: str) -> bool:
    return _env(name, default).strip().lower() in ("1", "true", "yes", "on")


def _env_int(name: str, default: str) -> int:
    return int(_env(name, default))


@dataclass(frozen=True)
class SutConfig:
    """Where the System Under Test lives and how we log into it."""

    base_url: str = field(default_factory=lambda: _env("SUT_BASE_URL", "http://localhost:8080/parabank"))
    username: str = field(default_factory=lambda: _env("SUT_USERNAME", "john"))
    password: str = field(default_factory=lambda: _env("SUT_PASSWORD", "demo"))

    @property
    def home_url(self) -> str:
        return f"{self.base_url}/index.htm"

    @property
    def services_url(self) -> str:
        return f"{self.base_url}/services/bank"


@dataclass(frozen=True)
class WarehouseConfig:
    """The PostgreSQL certification data store owned by Northline."""

    host: str = field(default_factory=lambda: _env("PGHOST", "localhost"))
    port: int = field(default_factory=lambda: _env_int("PGPORT", "5433"))
    database: str = field(default_factory=lambda: _env("PGDATABASE", "northline"))
    user: str = field(default_factory=lambda: _env("PGUSER", "northline"))
    password: str = field(default_factory=lambda: _env("PGPASSWORD", "northline"))

    @property
    def dsn(self) -> str:
        return (
            f"host={self.host} port={self.port} dbname={self.database} "
            f"user={self.user} password={self.password}"
        )


@dataclass(frozen=True)
class FrameworkConfig:
    """How the test framework itself behaves.

    Every value is an environment variable so the same suite runs unchanged on
    a developer machine and in continuous integration. Continuous integration
    typically sets HEADLESS=true and RETRIES=1; locally both default to the
    values that make debugging easiest.
    """

    headless: bool = field(default_factory=lambda: _env_bool("HEADLESS", "true"))
    slow_mo_ms: int = field(default_factory=lambda: _env_int("SLOW_MO_MS", "0"))
    default_timeout_ms: int = field(default_factory=lambda: _env_int("DEFAULT_TIMEOUT_MS", "10000"))
    api_timeout_s: int = field(default_factory=lambda: _env_int("API_TIMEOUT_S", "30"))
    retries: int = field(default_factory=lambda: _env_int("RETRIES", "0"))
    is_ci: bool = field(default_factory=lambda: _env_bool("CI", "false"))


@dataclass(frozen=True)
class Settings:
    environment: str = field(default_factory=lambda: _env("NORTHLINE_ENV", "local"))
    release: str = field(default_factory=lambda: _env("NORTHLINE_RELEASE", "unversioned"))
    sut: SutConfig = field(default_factory=SutConfig)
    warehouse: WarehouseConfig = field(default_factory=WarehouseConfig)
    framework: FrameworkConfig = field(default_factory=FrameworkConfig)
    reports_dir: Path = field(default_factory=lambda: REPO_ROOT / "reports")

    @property
    def artifacts_dir(self) -> Path:
        """Where screenshots, traces and videos from failed tests are written."""
        return self.reports_dir / "artifacts"


def get_settings() -> Settings:
    settings = Settings()
    settings.reports_dir.mkdir(parents=True, exist_ok=True)
    settings.artifacts_dir.mkdir(parents=True, exist_ok=True)
    return settings
