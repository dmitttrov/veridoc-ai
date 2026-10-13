"""Forward-only SQL migration runner.

Each file in `migrations/` (sorted by name) is applied exactly once, inside a
transaction, and recorded in `schema_migrations`. Re-running is a no-op.

Usage:
    python -m app.db.migrate            # apply pending migrations
    python -m app.db.migrate --status   # show applied/pending without applying
"""
from __future__ import annotations

import argparse
import asyncio
import logging
from pathlib import Path

import asyncpg

from app.config import get_settings

logger = logging.getLogger("veridoc.ai.migrate")

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def _migration_files() -> list[Path]:
    return sorted(MIGRATIONS_DIR.glob("*.sql"))


async def _applied_versions(conn: asyncpg.Connection) -> set[str]:
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version    text PRIMARY KEY,
            applied_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    rows = await conn.fetch("SELECT version FROM schema_migrations")
    return {r["version"] for r in rows}


async def run_migrations(database_url: str) -> list[str]:
    """Apply all pending migrations. Returns the versions newly applied."""
    conn = await asyncpg.connect(database_url)
    newly_applied: list[str] = []
    try:
        applied = await _applied_versions(conn)
        for path in _migration_files():
            version = path.stem
            if version in applied:
                continue
            sql = path.read_text(encoding="utf-8")
            async with conn.transaction():
                await conn.execute(sql)
                await conn.execute(
                    "INSERT INTO schema_migrations (version) VALUES ($1)", version
                )
            newly_applied.append(version)
            logger.info("applied migration %s", version)
    finally:
        await conn.close()
    return newly_applied


async def migration_status(database_url: str) -> tuple[list[str], list[str]]:
    conn = await asyncpg.connect(database_url)
    try:
        applied = await _applied_versions(conn)
    finally:
        await conn.close()
    versions = [p.stem for p in _migration_files()]
    pending = [v for v in versions if v not in applied]
    return sorted(applied), pending


async def _main() -> None:
    parser = argparse.ArgumentParser(description="Veridoc AI migration runner")
    parser.add_argument("--status", action="store_true", help="show status only")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    settings = get_settings()

    if args.status:
        applied, pending = await migration_status(settings.database_url)
        print(f"Applied:  {applied or '(none)'}")
        print(f"Pending:  {pending or '(none)'}")
        return

    applied = await run_migrations(settings.database_url)
    if applied:
        print(f"Applied {len(applied)} migration(s): {applied}")
    else:
        print("No pending migrations.")


if __name__ == "__main__":
    asyncio.run(_main())
