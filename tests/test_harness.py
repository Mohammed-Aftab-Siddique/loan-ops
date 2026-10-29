"""Batch harness tests (docs/HARNESS.md, docs/PLAN_HARNESS.md).

Covers: block-selection with the skip rule, end-to-end batch runs with the
scripted fake model, per-application sub-agent isolation + doc context audit,
intake rejections inside a block, the CLI subcommand, and the UI trigger.
"""

from __future__ import annotations

import sys
from typing import Any

import pytest
from conftest import clean_application
from fakes import ScriptedToolsModel
from fastapi.testclient import TestClient

import loan_ops as cli
import loan_ops.agents.factory as factory_mod
from loan_ops import harness, records


@pytest.fixture
def scripted_factory(monkeypatch):
    """Fresh scripted sub-agent model per run (no cross-run state)."""
    monkeypatch.setattr(
        factory_mod,
        "build_chat_model",
        lambda settings=None: ScriptedToolsModel("approved", "scripted rule"),
    )


# --- select_batch (pure) -------------------------------------------------


def waiting_rows(markers: list[Any]) -> list[dict[str, Any]]:
    return [{"processed": marker} for marker in markers]


def test_select_batch_all_waiting_takes_first_block() -> None:
    rows = waiting_rows([None] * 7)
    assert harness.select_batch(rows, batch_size=5) == (
        0,
        rows[0:5],
    )


def test_select_batch_skips_all_non_waiting_block() -> None:
    rows = waiting_rows([{"outcome": "approved"}] * 5 + [None] * 5)
    index, waiting = harness.select_batch(rows, batch_size=5)
    assert index == 5
    assert waiting == rows[5:10]


def test_select_batch_processes_only_waiting_members_of_mixed_block() -> None:
    rows = waiting_rows([{"outcome": "denied"}] * 5 + [None, {"outcome": "refer"}, None, None, None])
    index, waiting = harness.select_batch(rows, batch_size=5)
    assert index == 5
    assert waiting == [rows[5], rows[7], rows[8], rows[9]]


def test_select_batch_partial_final_block() -> None:
    rows = waiting_rows([{"outcome": "refer"}] * 5 + [None, None])
    index, waiting = harness.select_batch(rows, batch_size=5)
    assert (index, waiting) == (5, rows[5:7])


def test_select_batch_no_waiting_returns_none() -> None:
    rows = waiting_rows([{"outcome": "approved"}] * 7)
    assert harness.select_batch(rows, batch_size=5) is None


# --- docs access ---------------------------------------------------------


def test_load_docs_reads_all_required_docs() -> None:
    docs = harness.load_docs()
    assert [d["name"] for d in docs] == [f"docs/{n}" for n in harness.REQUIRED_DOCS]
    for doc in docs:
        assert doc["content"]
        assert len(doc["sha256"]) == 64


def test_load_docs_missing_file_aborts(tmp_path) -> None:
    with pytest.raises(FileNotFoundError):
        harness.load_docs(docs_dir=tmp_path)


def test_docs_context_carries_doc_content(tmp_path) -> None:
    (tmp_path / "POLICY.md").write_text("credit threshold is 650")
    docs = [
        {"name": "docs/POLICY.md", "content": "credit threshold is 650", "sha256": "abc"}
    ]
    context = harness.docs_context(docs)
    assert "docs/POLICY.md (sha256 abc)" in context
    assert "credit threshold is 650" in context


# --- end-to-end batch runs ------------------------------------------------


FIRST_BLOCK_OUTCOMES = {
    "APP-0001": "approved",
    "APP-0002": "approved",
    "APP-0003": "refer",  # $60,000 > auto-approval limit (docs/PROCESS.md)
    "APP-0004": "approved",
    "APP-0005": "refer",  # affordability in the 40-44% refer band
}


def test_first_batch_processes_top_five_waiting(scripted_factory) -> None:
    report = harness.run_batch()
    assert report["status"] == "ok"
    assert report["block_index"] == 0
    assert report["skipped_blocks"] == 0
    assert [run["application_id"] for run in report["processed"]] == [
        "APP-0001",
        "APP-0002",
        "APP-0003",
        "APP-0004",
        "APP-0005",
    ]
    assert {
        run["application_id"]: run["outcome"] for run in report["processed"]
    } == FIRST_BLOCK_OUTCOMES


def test_second_batch_skips_processed_block(scripted_factory) -> None:
    harness.run_batch()
    report = harness.run_batch()
    assert report["block_index"] == 5
    assert report["skipped_blocks"] == 1
    outcomes = {run["application_id"]: run["outcome"] for run in report["processed"]}
    assert [run["application_id"] for run in report["processed"]] == [
        "APP-0006",
        "APP-0007",
        "APP-0008",
        "APP-0009",
        "APP-0010",
    ]
    assert outcomes == {
        "APP-0006": "denied",
        "APP-0007": "refer",
        "APP-0008": "approved",
        "APP-0009": "denied",
        "APP-0010": "refer",
    }


def test_sub_agent_run_records_doc_context_audit(scripted_factory) -> None:
    report = harness.run_batch()
    for run in report["processed"]:
        assert harness.audit_verified(run["run_id"])
        audit = records.get_audit(run["run_id"])
        loaded = next(e for e in audit if e["event"] == "context_loaded")
        names = {d["name"] for d in loaded["detail"]["docs"]}
        assert names == {f"docs/{n}" for n in harness.REQUIRED_DOCS}


def test_audit_verified_false_without_complete_trail() -> None:
    application_id = records.create_application(clean_application())
    assert not harness.audit_verified(application_id)


def test_intake_rejected_app_reported_and_batch_continues(
    monkeypatch, scripted_factory
) -> None:
    from loan_ops.app import dataset as dataset_mod

    rows = [dict(app) for app in dataset_mod.load_applications()]
    bad = {**rows[0], "application_id": "APP-BAD", "loan_amount": 0}
    monkeypatch.setattr(dataset_mod, "load_applications", lambda: [rows[0], bad])
    report = harness.run_batch()
    assert report["status"] == "ok_with_intake_rejections"
    assert report["processed"][0]["status"] == "processed"
    assert report["processed"][1]["status"] == "intake_rejected"
    assert "validation error" in report["processed"][1]["reason"]


def test_nothing_to_process_when_queue_exhausted(monkeypatch) -> None:
    monkeypatch.setattr(
        "loan_ops.app.dataset.load_applications",
        lambda: [{"application_id": f"APP-{i:04d}", "noop": True} for i in range(1, 7)],
    )
    monkeypatch.setattr(
        harness.dataset,
        "processed_runs",
        lambda: {f"APP-{i:04d}": {"id": i} for i in range(1, 7)},
    )
    report = harness.run_batch()
    assert report == {"status": "nothing_to_process", "processed": []}


# --- CLI + web triggers ---------------------------------------------------


def test_cli_process_batch(scripted_factory, monkeypatch, capsys) -> None:
    monkeypatch.setattr(sys, "argv", ["loan-ops", "process-batch"])
    cli.main()
    out = capsys.readouterr().out
    assert "APP-0001" in out and "APP-0005" in out and "approved" in out
    assert "Batch block #0" in out


@pytest.fixture
def batch_client(monkeypatch):
    from loan_ops.app import create_app

    monkeypatch.setattr(
        factory_mod,
        "build_chat_model",
        lambda settings=None: ScriptedToolsModel("approved", "scripted rule"),
    )
    return TestClient(create_app())


def test_web_process_batch_button(batch_client) -> None:
    response = batch_client.post("/harness/process-batch")
    assert response.status_code == 200
    assert "Batch block #0" in response.text and "approved" in response.text
    # second click processes the next block (docs/HARNESS.md skip rule)
    response = batch_client.post("/harness/process-batch")
    assert "Batch block #5" in response.text
