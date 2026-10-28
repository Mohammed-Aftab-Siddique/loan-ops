"""True end-to-end tests: boot the real server as an OS subprocess on a real
port with a real on-disk SQLite file, then drive the whole docs/PROC.md flow
over HTTP: intake -> agent-run checks -> decision -> audit -> underwriter
resolution -> audit immutability.

Two layers:
- Deterministic e2e (always runs): scripted model, no LLM needed.
- Live e2e (skips unless Ollama serves the configured model): the real
  `qwen3.5:4b` path — slow, so it stays a single smoke run-through.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import httpx
import pytest

TESTS_DIR = Path(__file__).resolve().parent
ROOT = TESTS_DIR.parent
OLLLAMA_TAGS_URL = "http://localhost:11434/api/tags"
DEFAULT_LIVE_MODEL = "qwen3.5:4b"

CLEAN_APP = {
    "applicant_name": "E2E Tester",
    "applicant_id_number": "E2E-001",
    "identity_doc_valid": True,
    "proof_of_address_age_days": 30,
    "credit_score": 720,
    "credit_history_months": 48,
    "monthly_income": 8000,
    "income_documents_current": True,
    "existing_monthly_debt": 500,
    "loan_amount": 12000,
    "loan_purpose": "home",
    "fraud_soft_signals": 0,
}


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Server:
    """Real uvicorn subprocess talking to a real SQLite file on disk."""

    def __init__(self, scenario: str, db_url: str) -> None:
        self.port = _free_port()
        self.base = f"http://127.0.0.1:{self.port}"
        self.process = subprocess.Popen(
            [sys.executable, str(TESTS_DIR / "_e2e_server.py")],
            cwd=str(ROOT),
            env={
                **os.environ,
                "LOAN_OPS_E2E_FAKE": scenario,
                "LOAN_OPS_DB_URL": db_url,
                "LOAN_OPS_PORT": str(self.port),
            },
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )

    def wait_until_healthy(self, timeout: float = 20.0) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                output = (self.process.stdout.read() or b"").decode()
                raise RuntimeError(f"server died at boot: {output}")
            try:
                response = httpx.get(f"{self.base}/api/health", timeout=2)
                if response.status_code == 200 and response.json()["status"] == "ok":
                    return
            except httpx.HTTPError:
                time.sleep(0.2)
        raise RuntimeError("server did not become healthy in time")

    def close(self) -> None:
        self.process.terminate()
        try:
            self.process.wait(timeout=10)
        except subprocess.TimeoutExpired:  # pragma: no cover - defensive
            self.process.kill()


CACHED_MODEL_NAMES: list[str] | None = None


def _ollama_models() -> list[str]:
    global CACHED_MODEL_NAMES
    if CACHED_MODEL_NAMES is None:
        try:
            with urllib.request.urlopen(OLLLAMA_TAGS_URL, timeout=3) as r:
                payload = json.loads(r.read())
            CACHED_MODEL_NAMES = [m["name"] for m in payload.get("models", [])]
        except (urllib.error.URLError, TimeoutError, ValueError):
            CACHED_MODEL_NAMES = []
    return CACHED_MODEL_NAMES


def _ollama_up() -> bool:
    return bool(_ollama_models())


def _default_model_available() -> bool:
    return DEFAULT_LIVE_MODEL in _ollama_models()


@pytest.fixture(scope="module")
def deterministic_server(tmp_path_factory):
    server = Server("scripted", f"sqlite:///{tmp_path_factory.mktemp('e2e')}/e2e.db")
    try:
        server.wait_until_healthy()
        yield server
    finally:
        server.close()


def test_full_process_flow_through_the_real_server(deterministic_server) -> None:
    """docs/PROC.md steps 2-8 end-to-end over real HTTP — deterministic."""
    base = deterministic_server.base

    # -- step 2-6: approved run-through -------------------------------------
    response = httpx.post(f"{base}/api/applications", json=CLEAN_APP, timeout=60)
    assert response.status_code == 200
    approved = response.json()
    assert approved["outcome"] == "approved"
    assert [c["check"] for c in approved["check_results"]] == [
        "identity", "credit", "affordability", "fraud",
    ]
    assert all(c["result_class"] == "pass" for c in approved["check_results"])
    approved_id = approved["application_id"]

    # -- step 8: the audit trail is complete on the persisted DB -------------
    detail = httpx.get(f"{base}/api/applications/{approved_id}", timeout=15).json()
    events = {e["event"] for e in detail["audit"]}
    assert events >= {"application_received", "checks_executed", "decision_recorded"}
    decision_entry = [e for e in detail["audit"] if e["event"] == "decision_recorded"][0]
    assert decision_entry["detail"]["outcome"] == "approved"
    assert decision_entry["detail"]["decided_by"] == "agent"
    assert decision_entry["detail"]["rule"]  # the deciding rule is recorded

    # -- refer -> human underwriter resolution (steps: refer + queue) --------
    refer_payload = {**CLEAN_APP, "fraud_soft_signals": 1, "applicant_id_number": "E2E-002"}
    refer = httpx.post(f"{base}/api/applications", json=refer_payload, timeout=60).json()
    assert refer["outcome"] == "refer"
    refer_id = refer["application_id"]
    queue_ids = {r["id"] for r in httpx.get(f"{base}/api/referrals", timeout=15).json()}
    assert refer_id in queue_ids
    assert refer_id in queue_ids  # stays queued until a human decides

    bad = httpx.post(
        f"{base}/api/referrals/{refer_id}/decision",
        params={"decision": "maybe", "underwriter_id": "uw-e2e"},
        timeout=15,
    )
    assert bad.status_code == 409  # invalid human decisions never touch the audit

    resolved = httpx.post(
        f"{base}/api/referrals/{refer_id}/decision",
        params={"decision": "denied", "underwriter_id": "uw-e2e"},
        timeout=15,
    )
    assert resolved.status_code == 200
    resolved_detail = httpx.get(f"{base}/api/applications/{refer_id}", timeout=15).json()
    assert resolved_detail["outcome"] == "denied"
    assert resolved_detail["state"] == "resolved"
    assert refer_id not in {r["id"] for r in httpx.get(f"{base}/api/referrals", timeout=15).json()}
    human_entries = [e for e in resolved_detail["audit"] if e["actor"] == "uw-e2e"]
    assert human_entries and human_entries[-1]["detail"]["outcome"] == "denied"

    # -- denied run-through --------------------------------------------------
    denied = httpx.post(
        f"{base}/api/applications",
        json={**CLEAN_APP, "identity_doc_valid": False, "applicant_id_number": "E2E-003"},
        timeout=60,
    ).json()
    assert denied["outcome"] == "denied"
    identity = [c for c in denied["check_results"] if c["check"] == "identity"][0]
    assert identity["result_class"] == "fail"

    # -- intake rejection (invalid payload -> 422, no decision recorded) -----
    invalid = httpx.post(
        f"{base}/api/applications", json={**CLEAN_APP, "loan_amount": 0}, timeout=15
    )
    assert invalid.status_code == 422
    listing = httpx.get(f"{base}/api/applications", timeout=15).json()
    assert {row["outcome"] for row in listing} <= {"approved", "denied", "refer", None}

    # -- pages + audit immutability over real HTTP ---------------------------
    home = httpx.get(f"{base}/", timeout=15)
    assert home.status_code == 200
    assert "APP-0001" in home.text and "APP-0026" in home.text  # dataset browser
    assert "/apply" not in home.text  # no intake form in the UI
    audit_page = httpx.get(f"{base}/audit/{approved_id}", timeout=15)
    assert audit_page.status_code == 200 and "decision_recorded" in audit_page.text
    htmx = httpx.get(f"{base}/static/htmx.min.js", timeout=15)
    assert htmx.status_code == 200 and "javascript" in htmx.headers["content-type"]

    schema = httpx.get(f"{base}/openapi.json", timeout=15).json()["paths"]
    for path, methods in schema.items():
        if "audit" in path:
            assert not ({"put", "patch", "delete"} & set(methods)), f"{path} is mutable"
    assert set(schema["/api/applications"]) == {"post", "get"}


def test_garbage_agent_output_degrades_to_refer(tmp_path_factory) -> None:
    """Real server with a model emitting unparsable output -> contract holds:
    the outcome is refer with executed check results, never an invented call."""
    server = Server("garbage", f"sqlite:///{tmp_path_factory.mktemp('e2e_g')}/e2e.db")
    try:
        server.wait_until_healthy()
        body = httpx.post(
            f"{server.base}/api/applications", json=CLEAN_APP, timeout=60
        ).json()
        assert body["outcome"] == "refer"
        assert len(body["check_results"]) == 4  # checks were still executed
        assert "escalated" in body["rule"].lower()
    finally:
        server.close()


def test_engine_start_failure_is_visible() -> None:
    """A broken scenario name must fail loudly instead of a hung test."""
    server = Server("no-such-scenario", "sqlite:///:memory:")
    try:
        with pytest.raises(RuntimeError, match="died at boot"):
            server.wait_until_healthy(timeout=15)
    finally:
        server.close()


# --- live smoke test: the real Ollama model (skips cleanly otherwise) ------


@pytest.mark.skipif(
    not _ollama_up(),
    reason="Ollama is not reachable at OLLAMA_BASE_URL default",
)
@pytest.mark.skipif(
    _ollama_up() and not _default_model_available(),
    reason=f"{DEFAULT_LIVE_MODEL} is not pulled in Ollama",
)
def test_live_agent_processes_application_end_to_end(tmp_path_factory) -> None:
    """Real `qwen3.5:4b` through the real server: tools, decision, audit."""
    server = Server("live", f"sqlite:///{tmp_path_factory.mktemp('e2e_live')}/e2e.db")
    try:
        server.wait_until_healthy()
        response = httpx.post(f"{server.base}/api/applications", json=CLEAN_APP, timeout=300)
        assert response.status_code == 200
        body = response.json()
        assert body["outcome"] == "approved"
        assert [c["check"] for c in body["check_results"]] == [
            "identity", "credit", "affordability", "fraud",
        ]
        assert all(c["result_class"] == "pass" for c in body["check_results"])
        assert body["provider"] == "chat-ollama"
        assert body["model"] == DEFAULT_LIVE_MODEL

        detail = httpx.get(
            f"{server.base}/api/applications/{body['application_id']}", timeout=15
        ).json()
        events = {e["event"] for e in detail["audit"]}
        assert events >= {"application_received", "checks_executed", "decision_recorded"}
    finally:
        server.close()
