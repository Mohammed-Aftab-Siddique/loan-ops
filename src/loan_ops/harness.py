"""Batch harness: process the top 5 waiting applications, each by an
individual sub-agent (docs/PLAN_HARNESS.md, docs/HARNESS.md).

Selection: walk the dataset queue in blocks of `batch_size`; a block whose
members are all non-waiting is skipped ("next top 5"); the first block with
>=1 waiting member selects its waiting members for processing.

Sub-agents: one fresh decision-agent instance per application
(agents.decision.build_decision_agent), each with the four docs required by
docs/PROC.md read from disk and injected as context, plus a `context_loaded`
audit entry with doc digests — doc access is executed and auditable, never
fabricated.
"""

from __future__ import annotations

import hashlib
from typing import Any

from loan_ops import records
from loan_ops.app import dataset

BATCH_SIZE = 5
DOCS_DIR = dataset.DATA_DIR.parent / "docs"
REQUIRED_DOCS = ("PROC.md", "PROCESS.md", "POLICY.md", "TECH_STACK.md")
DOC_CONTEXT_CHAR_CAP = 6000


def load_docs(docs_dir=None) -> list[dict[str, str]]:
    """Read the four docs required by docs/PROC.md from disk (executed reads).

    Raises FileNotFoundError if any required document is missing — the
    reading step is mandatory and aborts the harness before processing.
    """
    directory = docs_dir or DOCS_DIR
    docs: list[dict[str, str]] = []
    for name in REQUIRED_DOCS:
        path = directory / name
        docs.append(
            {
                "name": f"docs/{name}",
                "content": path.read_text(),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )
    return docs


def docs_context(docs: list[dict[str, str]]) -> str:
    """Bounded prompt context carrying every required doc, per sub-agent run."""
    parts = [
        "Required reading loaded from disk for this run (docs/PROC.md):"
    ]
    for doc in docs:
        content = doc["content"]
        if len(content) > DOC_CONTEXT_CHAR_CAP:
            content = content[:DOC_CONTEXT_CHAR_CAP] + "\n… [truncated]"
        parts.append(f"--- {doc['name']} (sha256 {doc['sha256']}) ---\n{content}")
    return "\n".join(parts)


def select_batch(
    rows: list[dict[str, Any]], batch_size: int = BATCH_SIZE
) -> tuple[int, list[dict[str, Any]]] | None:
    """First block of `batch_size` containing >=1 waiting application.

    Returns (block_index, waiting members of that block); None if no block has
    a waiting application. Applications that already have a run are never
    re-processed even inside the selected block.
    """
    for index in range(0, len(rows), batch_size):
        block = rows[index : index + batch_size]
        waiting = [row for row in block if not row.get("processed")]
        if waiting:
            return index, waiting
    return None


def run_batch(
    batch_size: int = BATCH_SIZE, runner: Any = None
) -> dict[str, Any]:
    """Process the top waiting block; returns an audit-sourced summary.

    Returns status, the selected block index (0-based), the count of fully
    skipped blocks, if any; and a per-application list with the outcome, rule,
    provider/model — all read back from the persisted run.
    """
    runner = runner or _sub_agent_run
    docs = load_docs()  # mandatory reading; aborts before any processing

    block = select_batch(dataset.ui_rows(), batch_size)
    if block is None:
        return {"status": "nothing_to_process", "processed": []}

    block_index, waiting = block
    results = [runner(row, docs) for row in waiting]
    failures = [r for r in results if r.get("status") == "intake_rejected"]
    return {
        "status": "ok" if not failures else "ok_with_intake_rejections",
        "batch_size": batch_size,
        "block_index": block_index,
        "skipped_blocks": block_index // batch_size,
        "processed": results,
    }


def _sub_agent_run(row: dict[str, Any], docs: list[dict[str, str]]) -> dict[str, Any]:
    """One individual sub-agent run: fresh decision agent for one application."""
    from loan_ops import pipeline

    payload = dict(row)
    payload.pop("processed", None)
    context = docs_context(docs)
    context_meta = {
        "docs": [{"name": d["name"], "sha256": d["sha256"]} for d in docs]
    }
    try:
        result = pipeline.process(payload, extra_context=context, context_meta=context_meta)
    except ValueError as exc:
        return {
            "application_id": payload.get("application_id"),
            "status": "intake_rejected",
            "reason": str(exc),
        }
    return {
        "application_id": payload.get("application_id"),
        "run_id": result["application_id"],
        "outcome": result["outcome"],
        "rule": result["rule"],
        "provider": result["provider"],
        "model": result["model"],
        "status": "processed",
    }


def audit_verified(application_id: int) -> bool:
    """docs/PROC.md step 8 for harness runs: the trail must be complete."""
    events = {entry["event"] for entry in records.get_audit(application_id)}
    return {
        "application_received",
        "context_loaded",
        "checks_executed",
        "decision_recorded",
    } <= events


def format_summary(report: dict[str, Any]) -> str:
    """Console summary, sourced from the persisted run results."""
    if report["status"] == "nothing_to_process":
        return "No waiting applications found; nothing to process."
    lines = [f"Batch block #{report['block_index']} — {len(report['processed'])} sub-agent run(s):"]
    for run in report["processed"]:
        if run["status"] == "intake_rejected":
            lines.append(f"  {run['application_id']}: intake rejected ({run['reason']})")
        else:
            lines.append(
                f"  {run['application_id']} (run #{run['run_id']}): "
                f"{run['outcome']} — {run['rule']}"
            )
    return "\n".join(lines)
