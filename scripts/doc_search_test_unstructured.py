"""Smoke test: unstructured-based session document ingestion outside Temporal."""

from __future__ import annotations

import asyncio
import os
import sys
import time
from pathlib import Path
from urllib.parse import urlparse, urlunparse

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from dotenv import dotenv_values, load_dotenv  # noqa: E402

_DOCKER_ENV = _REPO_ROOT / "docker" / ".env"
_ROOT_ENV = _REPO_ROOT / ".env"

load_dotenv(_DOCKER_ENV)
if _ROOT_ENV.is_file():
    for key, value in dotenv_values(_ROOT_ENV).items():
        if value is None:
            continue
        s = str(value).strip()
        if not s and key in ("DATABASE_URL", "QDRANT_URL"):
            continue
        os.environ[key] = str(value)

if not os.environ.get("DATABASE_URL", "").strip():
    raise RuntimeError(
        "DATABASE_URL is not set after loading env files. "
        f"Expected {_DOCKER_ENV} to define DATABASE_URL=... "
        f"(file exists: {_DOCKER_ENV.is_file()})."
    )


def _database_url_use_localhost_when_run_on_host() -> None:
    """Rewrite a container PostgreSQL hostname for execution from the local host.

    Returns:
        None.
    """
    if os.path.exists("/.dockerenv"):
        return
    raw = os.environ.get("DATABASE_URL")
    if not raw or not raw.strip():
        return
    u = raw.strip()
    if u.startswith("postgresql+psycopg_async://"):
        u = "postgresql://" + u.removeprefix("postgresql+psycopg_async://")
    if not u.startswith("postgresql://"):
        return
    parsed = urlparse(u)
    if parsed.hostname not in ("postgres", "app-postgres"):
        return
    port = str(parsed.port or os.environ.get("POSTGRES_PORT", "5433"))
    user = parsed.username or ""
    password = parsed.password or ""
    if password:
        netloc = f"{user}:{password}@127.0.0.1:{port}"
    else:
        netloc = f"{user}@127.0.0.1:{port}" if user else f"127.0.0.1:{port}"
    os.environ["DATABASE_URL"] = urlunparse(
        parsed._replace(netloc=netloc, scheme="postgresql")
    )


def _qdrant_url_use_localhost_when_run_on_host() -> None:
    """Rewrite a container Qdrant hostname for execution from the local host.

    Returns:
        None.
    """
    if os.path.exists("/.dockerenv"):
        return
    raw = os.environ.get("QDRANT_URL")
    if not raw or not raw.strip():
        return
    parsed = urlparse(raw.strip())
    if parsed.hostname != "qdrant":
        return
    port = os.environ.get("QDRANT_PORT", str(parsed.port or 6333))
    netloc = f"127.0.0.1:{port}"
    os.environ["QDRANT_URL"] = urlunparse(parsed._replace(netloc=netloc))


_database_url_use_localhost_when_run_on_host()
_qdrant_url_use_localhost_when_run_on_host()

import database.db as db  # noqa: E402

from backend.config import SESSION_UPLOADS_SUBDIR  # noqa: E402
from backend.logging_setup import configure_logging  # noqa: E402
from backend.tools.doc_search.process_docs.process_docs_unstructured import (  # noqa: E402
    ProcessDocumentsUnstructured,
)
from database.session_dao import SessionDAO  # noqa: E402

SESSION_ID = "14036716-2284-4395-bac9-a09b11ec81d1"
USER_ID = "andy2"
USER_QUERY = "what chemical is most corrosive to metal surfaces"


async def main() -> None:
    """Run the Unstructured ingestion and retrieval smoke test.

    Returns:
        None.
    """
    configure_logging()
    await db.engine_init()
    maker = db._async_session_maker
    if maker is None:
        print("Database session factory not initialized.", file=sys.stderr)
        sys.exit(1)

    try:
        async with maker() as session_db:
            dao = SessionDAO(session_db)
            t0 = time.perf_counter()
            result = await ProcessDocumentsUnstructured(SESSION_ID).process_session_documents(
                dao,
                sub_dir=SESSION_UPLOADS_SUBDIR,
            )
            await session_db.commit()
            elapsed = time.perf_counter() - t0

        print("tool: process_session_documents (unstructured, direct, outside Temporal)")
        print(f"session_id: {SESSION_ID}")
        print(f"user_id: {USER_ID}")
        print(f"user_query: {USER_QUERY}")
        print(f"sub_dir: {SESSION_UPLOADS_SUBDIR}")
        print(f"elapsed_seconds: {elapsed:.2f}")
        print(f"all_ok: {result.all_ok}")
        print(f"processed_files: {len(result.files)}")
        for i, f in enumerate(result.files, 1):
            print(
                f"{i}. ok={f.ok} file_id={f.file_id} "
                f"filename={f.filename} chunks={f.chunk_count} error={f.error}"
            )
        if not result.files:
            print("WARN: no files were processed in this run.", file=sys.stderr)
        if result.all_ok:
            print("PASS: direct ingestion with unstructured completed.")
        else:
            print("FAIL: direct ingestion with unstructured had file-level errors.", file=sys.stderr)
    finally:
        await db.engine_dispose()


if __name__ == "__main__":
    asyncio.run(main())
