"""GOALS 4.1-4.4 — routes, walk-through, referral integrity, audit immutability."""

from __future__ import annotations

import pytest
from conftest import clean_application
from fakes import GarbageOutputModel, ScriptedToolsModel
from fastapi.testclient import TestClient

from loan_ops import records
from loan_ops.agents import factory as factory_mod
from loan_ops.app import create_app


@pytest.fixture()
def client(monkeypatch) -> TestClient:
    """Boot the app with a scripted Ollama-flavored model."""
    monkeypatch.setattr(
        factory_mod, "build_chat_model", lambda settings=None: ScriptedToolsModel("approved", "ok")
    )
    app = create_app()
    return TestClient(app)


@pytest.fixture()
def garbage_client(monkeypatch) -> TestClient:
    monkeypatch.setattr(
        factory_mod, "build_chat_model", lambda settings=None: GarbageOutputModel("approved", "ok")
    )
    return TestClient(create_app())


# --- GOALS 4.1: all five route groups exist and respond ---


def test_health(client) -> None:
    assert client.get("/api/health").status_code == 200


def test_submit_and_status_route(client) -> None:
    response = client.post("/api/applications", json=clean_application())
    assert response.status_code == 200
    body = response.json()
    assert body["outcome"] == "approved"
    detail = client.get(f"/api/applications/{body['application_id']}")
    assert detail.status_code == 200
    assert {e["event"] for e in detail.json()["audit"]} >= {"decision_recorded"}


def test_list_route(client) -> None:
    client.post("/api/applications", json=clean_application())
    listing = client.get("/api/applications")
    assert listing.status_code == 200
    assert listing.json()


def test_underwriter_queue_route(client) -> None:
    assert client.get("/api/referrals").status_code == 200


def test_submit_validation_error_is_422(client) -> None:
    bad = clean_application()
    bad["applicant_name"] = ""
    response = client.post("/api/applications", json=bad)
    assert response.status_code == 422


def test_malformed_agent_output_still_yields_contract_outcome(garbage_client) -> None:
    response = garbage_client.post("/api/applications", json=clean_application())
    assert response.json()["outcome"] == "refer"


# --- GOALS 4.2: scripted walk-through completes without manual intervention ---


def test_submit_to_audit_walkthrough(client) -> None:
    import time

    start = time.monotonic()
    created = client.post("/api/applications", json=clean_application()).json()
    app_id = created["application_id"]
    page = client.get("/audit/" + str(app_id))
    elapsed = time.monotonic() - start
    assert page.status_code == 200
    assert "decision_recorded" in page.text
    assert elapsed < 30


def test_ui_pages_render(client) -> None:
    home = client.get("/")
    assert home.status_code == 200
    # dataset browser replaced the intake form (docs/PLAN.md Phase 4)
    assert "APP-0001" in home.text and "APP-0026" in home.text
    assert "Status" in home.text
    # every application starts in a waiting state (docs/PLAN.md Phase 4)
    assert home.text.count(">waiting</span>") == 26
    assert ">approved<" not in home.text and ">denied<" not in home.text
    # currency renders as text, never leaked template code
    assert "$50,000.00" in home.text and "$20,000" in home.text
    assert "${" not in home.text
    assert 'hx-post="/apply"' not in home.text and "/apply" not in home.text


# --- dataset detail + one-click agent run (Phase 4 rework) ---


def test_dataset_detail_page(client) -> None:
    page = client.get("/dataset/APP-0001")
    assert page.status_code == 200
    assert "APP-0001" in page.text and "Maya Fernandez" in page.text
    assert "waiting" in page.text  # no expected status is revealed up front
    assert ">approved<" not in page.text
    assert "Run agent on this application" in page.text

    missing = client.get("/dataset/APP-9999")
    assert missing.status_code == 404


def test_dataset_process_route_fires_the_agent(client) -> None:
    page = client.post("/dataset/APP-0001/process")
    assert page.status_code == 200
    assert "approved" in page.text and "open audit page" in page.text

    # the run is traceable back to the dataset item
    row = next(r for r in records.list_applications())
    assert (row["payload"] or {}).get("application_id") == "APP-0001"

    # the table reveals the status only for the processed application
    home = client.get("/").text
    assert home.count(">waiting</span>") == 25
    assert ">approved</span>" in home


def test_dataset_process_referral_shows_human_decision_form(client) -> None:
    page = client.post("/dataset/APP-0023/process")  # single soft fraud signal -> refer
    assert "refer" in page.text
    assert "Underwriter ID" in page.text  # only a human may close it


def test_dataset_process_intake_rejection_is_not_a_crash(client) -> None:
    page = client.post("/dataset/APP-0026/process")  # loan_amount 0
    assert page.status_code == 200
    assert "Intake rejected" in page.text
    assert page.text.count("decision_recorded") == 0  # nothing was decided


def test_dataset_process_repeated_runs_are_recorded(client) -> None:
    client.post("/dataset/APP-0008/process")
    second = client.post("/dataset/APP-0008/process")
    assert second.status_code == 200
    runs_for_app = [
        r for r in records.list_applications()
        if (r["payload"] or {}).get("application_id") == "APP-0008"
    ]
    assert len(runs_for_app) == 2  # each click fires a fresh agent run


def test_underwriter_decision_from_llm_queue(client) -> None:
    client.post("/dataset/APP-0023/process")
    top = records.referral_queue()[0]
    response = client.post(
        "/underwriter/" + str(top["id"]),
        data={"decision": "approved", "underwriter_id": "uw-1"},
    )
    assert response.status_code == 200
    stored = records.get_application(top["id"])
    assert stored["outcome"] == "approved" and stored["state"] == "resolved"


# --- GOALS 4.3: referrals closable only by a human decision ---


def test_referral_queue_and_human_resolution(client) -> None:
    from conftest import clean_application as ca

    refer = client.post(
        "/api/applications", json=ca(fraud_soft_signals=1)
    ).json()
    app_id = refer["application_id"]
    assert refer["outcome"] == "refer"
    assert app_id in {r["id"] for r in client.get("/api/referrals").json()}

    # invalid decision values are rejected before touching the audit trail
    bad = client.post(
        f"/api/referrals/{app_id}/decision?decision=maybe&underwriter_id=uw-1"
    )
    assert bad.status_code == 409

    ok = client.post(
        f"/api/referrals/{app_id}/decision?decision=denied&underwriter_id=uw-2"
    )
    assert ok.status_code == 200
    assert app_id not in {r["id"] for r in client.get("/api/referrals").json()}
    assert any(e["actor"] == "uw-2" for e in records.get_audit(app_id))


def test_form_submission_into_referral_queue(client, monkeypatch) -> None:
    """Processing a dataset row with amount > cap lands it in the queue."""
    from loan_ops import records as rec

    response = client.post("/dataset/APP-0003/process")  # $60,000 -> refer
    assert response.status_code == 200

    referrals = rec.referral_queue()
    top = next(r for r in referrals if (r["payload"] or {}).get("application_id") == "APP-0003")
    assert top["loan_amount"] > 50_000


# --- GOALS 4.4: audit entries immutable from the app ---


def test_no_mutation_routes_for_audit(client) -> None:
    schema = client.get("/openapi.json").json()["paths"]
    paths = set(schema)
    assert "/audit/{app_id}" in paths  # read-only page exists

    audit_paths = {p for p in paths if "audit" in p}
    for p in audit_paths:
        methods = schema[p] if isinstance(schema[p], dict) else {}
        for method in ("put", "patch", "delete"):
            assert method not in methods, f"audit route {p} is mutable"

    # applications: create (POST) and read (GET) only — no update/delete
    assert set(schema["/api/applications"]) == {"post", "get"}
    assert set(schema["/api/applications/{app_id}"]) == {"get"}
