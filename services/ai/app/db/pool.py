"""asyncpg connection pool with the pgvector codec registered."""
from __future__ import annotations

import asyncpg
from pgvector.asyncpg import register_vector

from app.config import Settings


async def _init_connection(conn: asyncpg.Connection) -> None:
    # Teach asyncpg how to encode/decode the `vector` type for this connection.
    await register_vector(conn)


async def create_pool(settings: Settings) -> asyncpg.Pool:
    """Create a connection pool. The vector extension must already exist
    (created by the migration); `register_vector` only installs the codec."""
    return await asyncpg.create_pool(
        dsn=settings.database_url,
        min_size=1,
        max_size=10,
        init=_init_connection,
        command_timeout=30,
    )
