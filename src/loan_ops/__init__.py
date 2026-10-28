"""loan-ops CLI entrypoint (`uv run loan-ops`)."""

from __future__ import annotations

import argparse
import os

import uvicorn

from loan_ops.config import get_settings


def main() -> None:
    settings = get_settings()
    settings.validate_provider()  # fail fast on misconfiguration (GOALS 5.2)

    from loan_ops import store

    store.create_all()  # dev convenience; Alembic is canonical (GOALS 1.4)

    parser = argparse.ArgumentParser(prog="loan-ops")
    parser.add_argument("--host", default=settings.host)
    parser.add_argument("--port", type=int, default=settings.port)
    args = parser.parse_args()

    os.environ.setdefault("LOAN_OPS_DB_URL", settings.db_url)
    uvicorn.run(
        "loan_ops.app:create_app",
        factory=True,
        host=args.host,
        port=args.port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
