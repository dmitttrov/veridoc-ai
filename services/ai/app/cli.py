"""Local ingestion CLI.

Ingest a PDF from disk into the configured database (useful for local testing
without the web UI). Never logs document content.

Usage:
    python -m app.cli ingest path/to/document.pdf
    python -m app.cli ingest path/to/document.pdf --database-url postgresql://...
"""
from __future__ import annotations

import argparse
import asyncio
import mimetypes
from pathlib import Path

from app.config import get_settings
from app.db.migrate import run_migrations
from app.db.pool import create_pool
from app.embeddings import build_embedding_provider
from app.ingestion.errors import IngestionError
from app.ingestion.pipeline import ingest_pdf


async def _ingest(path: Path, database_url: str) -> int:
    settings = get_settings()
    settings.database_url = database_url
    await run_migrations(database_url)

    embedder = build_embedding_provider(settings)
    pool = await create_pool(settings)
    try:
        data = path.read_bytes()
        mime = mimetypes.guess_type(path.name)[0] or "application/pdf"
        try:
            result = await ingest_pdf(
                pool, embedder, settings, data=data, filename=path.name, mime_type=mime
            )
        except IngestionError as exc:
            print(f"REJECTED [{exc.code}]: {exc.message}")
            return 1
        print(
            f"OK document={result.document_id} pages={result.page_count} "
            f"chunks={result.chunk_count} "
            f"{'(already ingested)' if result.already_ingested else '(new)'}"
        )
        return 0
    finally:
        await pool.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Veridoc AI local ingestion CLI")
    sub = parser.add_subparsers(dest="command", required=True)
    ing = sub.add_parser("ingest", help="ingest a local PDF file")
    ing.add_argument("path", type=Path, help="path to a PDF file")
    ing.add_argument(
        "--database-url",
        default=get_settings().database_url,
        help="override the database connection string",
    )
    args = parser.parse_args()

    if args.command == "ingest":
        if not args.path.is_file():
            parser.error(f"file not found: {args.path}")
        raise SystemExit(asyncio.run(_ingest(args.path, args.database_url)))


if __name__ == "__main__":
    main()
