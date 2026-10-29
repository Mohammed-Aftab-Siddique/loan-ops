"""loan-ops CLI entrypoint (`uv run loan-ops`).

Commands (docs/HARNESS.md):
- (default / `serve`) start the FastAPI web app;
- `process-batch` — process the top 5 waiting applications as individual
  sub-agent runs, skipping fully non-waiting blocks (docs/PLAN_HARNESS.md).
"""

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
    parser.add_argument(
        "command", nargs="?", choices=("serve", "process-batch"), default="serve"
    )
    parser.add_argument("--host", default=settings.host)
    parser.add_argument("--port", type=int, default=settings.port)
    parser.add_argument("--batch-size", type=int, default=5)
    args = parser.parse_args()

    os.environ.setdefault("LOAN_OPS_DB_URL", settings.db_url)
    if args.command == "process-batch":
        from loan_ops import harness

        report = harness.run_batch(batch_size=args.batch_size)
        print(harness.format_summary(report))
        return

    uvicorn.run(
        "loan_ops.app:create_app",
        factory=True,
        host=args.host,
        port=args.port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
