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
    port: int = field(default_factory=lambda: int(_env("PGPORT", "5432")))
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
class Settings:
    environment: str = field(default_factory=lambda: _env("NORTHLINE_ENV", "local"))
    release: str = field(default_factory=lambda: _env("NORTHLINE_RELEASE", "unversioned"))
    sut: SutConfig = field(default_factory=SutConfig)
    warehouse: WarehouseConfig = field(default_factory=WarehouseConfig)
    reports_dir: Path = field(default_factory=lambda: REPO_ROOT / "reports")


def get_settings() -> Settings:
    settings = Settings()
    settings.reports_dir.mkdir(parents=True, exist_ok=True)
    return settings
