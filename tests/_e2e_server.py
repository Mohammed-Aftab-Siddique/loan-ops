"""E2E test server bootstrap (tests/test_e2e.py spawns this as a subprocess).

Boots the REAL loan-ops server on real HTTP. Either wires a deterministic
scripted model (CI-safe, no LLM needed) or leaves the factory untouched for
the live-Ollama smoke test.

Env:
    LOAN_OPS_E2E_FAKE = "scripted" | "garbage" | "live"
    LOAN_OPS_DB_URL   = sqlite file for this run (real on-disk DB)
    LOAN_OPS_PORT     = port to bind
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
ROOT = TESTS_DIR.parent

sys.path.insert(0, str(TESTS_DIR))  # so `import fakes` works in the subprocess
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from loan_ops.agents import factory as factory_mod  # noqa: E402
from loan_ops.store import create_all  # noqa: E402

scenario = os.environ.get("LOAN_OPS_E2E_FAKE", "scripted")

if scenario == "scripted":
    from fakes import ScriptedToolsModel

    factory_mod.build_chat_model = (
        lambda settings=None: ScriptedToolsModel("approved", "scripted rule")
    )
elif scenario == "garbage":
    from fakes import GarbageOutputModel

    factory_mod.build_chat_model = (
        lambda settings=None: GarbageOutputModel("approved", "ok")
    )
elif scenario != "live":  # pragma: no cover - defensive
    raise SystemExit(f"unknown LOAN_OPS_E2E_FAKE: {scenario}")

create_all()  # same as the `uv run loan-ops` entrypoint does

import uvicorn  # noqa: E402

from loan_ops.app import create_app  # noqa: E402

uvicorn.run(
    create_app(),
    host=os.environ.get("LOAN_OPS_HOST", "127.0.0.1"),
    port=int(os.environ.get("LOAN_OPS_PORT", "8000")),
    log_level="warning",
)
