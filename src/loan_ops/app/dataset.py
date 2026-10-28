"""Dataset-backed UI context: the fictional dataset in data/ is the UI's
content source (docs/PLAN.md Phase 4 — no intake form in the UI; free-form
intake stays JSON-API-only).

UI behavior: every application starts in a waiting state; the agent only runs
when the user fires the process button on the detail page, and the status
then reflects the actual outcome. The expected statuses in
data/expected_decisions.json are verification data — never shown in the UI.

Each dataset record carries its `application_id` (e.g. APP-0001) into the
stored payload when the agent processes it, so processed runs are traceable
back to their dataset row.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from loan_ops import records

DATA_DIR = Path(__file__).resolve().parents[3] / "data"
INPUT_FILE = DATA_DIR / "loan_applications.json"
EXPECTED_FILE = DATA_DIR / "expected_decisions.json"


def load_applications() -> list[dict[str, Any]]:
    return json.loads(INPUT_FILE.read_text())["applications"]


def load_expected() -> dict[str, dict[str, Any]]:
    return {d["application_id"]: d for d in json.loads(EXPECTED_FILE.read_text())["decisions"]}


def processed_runs() -> dict[str, dict[str, Any]]:
    """Map dataset application_id -> newest DB run (list is newest-first)."""
    runs: dict[str, dict[str, Any]] = {}
    for row in records.list_applications():
        dataset_id = (row.get("payload") or {}).get("application_id")
        if dataset_id and dataset_id not in runs:
            runs[dataset_id] = row
    return runs


def ui_rows() -> list[dict[str, Any]]:
    """Dataset rows merged with the latest agent run (if any).

    Status is only revealed once a run exists — the UI never shows the
    expected statuses from data/expected_decisions.json.
    """
    processed = processed_runs()
    return [
        {**app, "processed": processed.get(app["application_id"])}
        for app in load_applications()
    ]


def get_record(app_id: str) -> dict[str, Any] | None:
    """Full context for one dataset application (None if not in the dataset)."""
    application = next(
        (a for a in load_applications() if a["application_id"] == app_id), None
    )
    if application is None:
        return None
    return {
        "application": application,
        "processed": processed_runs().get(app_id),
    }
