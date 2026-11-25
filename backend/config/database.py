"""Centralized database selection for MEBELCHI AI.

Priority (see docs/DEPLOYMENT.md):
  1. DB_ENGINE=postgresql (default when POSTGRES_DB is set) -> PostgreSQL.
  2. PostgreSQL is probed once at process start with a short timeout.
  3. If it is unreachable and DATABASE_FALLBACK_ENABLED=true -> SQLite at SQLITE_PATH,
     logged as WARNING and exposed in the admin system status.
     If fallback is disabled -> ImproperlyConfigured (the process refuses to start).
  4. Data is never copied or merged between the two databases.

The resolver is a pure function (env mapping + injected probe) so it can be tested
without a running PostgreSQL server.
"""
from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Mapping, Optional

from django.core.exceptions import ImproperlyConfigured

logger = logging.getLogger("mebelchi.db")

ENGINE_POSTGRESQL = "postgresql"
ENGINE_SQLITE = "sqlite"
PROBE_TIMEOUT_SECONDS = 3

Probe = Callable[[dict], Optional[str]]  # returns None when reachable, else a short error text


@dataclass
class DatabaseStatus:
    configured_engine: str        # what DB_ENGINE asked for
    active_engine: str            # what Django actually uses
    fallback_enabled: bool
    fallback_active: bool
    connectivity_error: Optional[str] = None  # PostgreSQL probe error when it was unreachable

    def as_dict(self) -> dict:
        return asdict(self)


def _to_bool(value: Optional[str], default: bool = False) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def postgres_probe(pg: dict) -> Optional[str]:
    """Try a real connection to PostgreSQL. Returns None on success, else a safe error string.

    The password is never included in the returned text.
    """
    try:
        import psycopg
    except ImportError as exc:  # pragma: no cover - psycopg is a hard requirement
        return f"psycopg not installed: {exc.__class__.__name__}"
    try:
        with psycopg.connect(
            host=pg["HOST"],
            port=pg["PORT"],
            dbname=pg["NAME"],
            user=pg["USER"],
            password=pg["PASSWORD"],
            connect_timeout=PROBE_TIMEOUT_SECONDS,
        ) as conn:
            conn.execute("SELECT 1")
        return None
    except psycopg.Error as exc:
        return exc.__class__.__name__


def _sqlite_config(env: Mapping[str, str], base_dir: Path) -> dict:
    raw_path = env.get("SQLITE_PATH") or "db.sqlite3"
    path = Path(raw_path)
    if not path.is_absolute():
        path = base_dir / path
    return {"ENGINE": "django.db.backends.sqlite3", "NAME": path}


def _postgres_params(env: Mapping[str, str]) -> dict:
    return {
        "NAME": env.get("POSTGRES_DB", ""),
        "USER": env.get("POSTGRES_USER", "mebelchi"),
        "PASSWORD": env.get("POSTGRES_PASSWORD", ""),
        "HOST": env.get("POSTGRES_HOST", "localhost"),
        "PORT": env.get("POSTGRES_PORT", "5432"),
    }


def resolve_database(
    env: Mapping[str, str],
    base_dir: Path,
    probe: Probe = postgres_probe,
) -> tuple[dict, DatabaseStatus]:
    """Return (DATABASES['default'], status) according to the rules in the module docstring."""
    has_postgres_name = bool(env.get("POSTGRES_DB"))
    default_engine = ENGINE_POSTGRESQL if has_postgres_name else ENGINE_SQLITE
    configured = (env.get("DB_ENGINE") or default_engine).strip().lower()
    if configured not in (ENGINE_POSTGRESQL, ENGINE_SQLITE):
        raise ImproperlyConfigured(f"DB_ENGINE must be 'postgresql' or 'sqlite', got {configured!r}.")
    fallback_enabled = _to_bool(env.get("DATABASE_FALLBACK_ENABLED"), default=False)

    if configured == ENGINE_SQLITE:
        status = DatabaseStatus(configured, ENGINE_SQLITE, fallback_enabled, fallback_active=False)
        return _sqlite_config(env, base_dir), status

    if not has_postgres_name:
        raise ImproperlyConfigured("DB_ENGINE=postgresql requires POSTGRES_DB to be set.")

    pg = _postgres_params(env)
    error = probe(pg)
    if error is None:
        pg_config = {"ENGINE": "django.db.backends.postgresql", "CONN_MAX_AGE": 60,
                     "OPTIONS": {"connect_timeout": PROBE_TIMEOUT_SECONDS}, **pg}
        return pg_config, DatabaseStatus(configured, ENGINE_POSTGRESQL, fallback_enabled, fallback_active=False)

    if not fallback_enabled:
        raise ImproperlyConfigured(
            f"PostgreSQL is unreachable ({error}) and DATABASE_FALLBACK_ENABLED is false. "
            "Fix the database or enable the SQLite fallback explicitly."
        )
    status = DatabaseStatus(configured, ENGINE_SQLITE, fallback_enabled, fallback_active=True,
                            connectivity_error=error)
    return _sqlite_config(env, base_dir), status


def log_database_status(status: DatabaseStatus) -> None:
    """Announce the active database. Called once from settings after LOGGING is configured."""
    if status.fallback_active:
        logger.warning(
            "Database: SQLITE FALLBACK ACTIVE. PostgreSQL unreachable (%s). "
            "Data written now stays in SQLite and is NOT merged into PostgreSQL automatically.",
            status.connectivity_error,
        )
    else:
        logger.info("Database: %s (configured: %s)", status.active_engine, status.configured_engine)
