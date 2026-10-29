"""Routes: JSON API + pages.

UI (docs/PLAN.md Phase 4): there is no intake form — the pages browse the
fictional dataset in data/, show per-application details, and fire the agent
with one click. Free-form intake lives only in the JSON API. Referrals are
closable only by a human decision (GOALS 4.3); audit entries are read-only
from the app (GOALS 4.4).
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse

from loan_ops import pipeline, records
from loan_ops.app import dataset, templates

api_router = APIRouter(prefix="/api")
page_router = APIRouter()


# --- JSON API -----------------------------------------------------------


@api_router.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    return {"status": "ok"}


@api_router.post("/applications", tags=["applications"])
def submit_application(payload: dict[str, Any]) -> dict[str, Any]:
    """Submit an application: runs the full docs/PROC.md pipeline synchronously."""
    try:
        return pipeline.process(payload)
    except ValueError as exc:  # intake validation failure
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@api_router.get("/applications", tags=["applications"])
def list_applications() -> list[dict[str, Any]]:
    return records.list_applications()


@api_router.get("/applications/{app_id}", tags=["applications"])
def application_detail(app_id: int) -> dict[str, Any]:
    stored = records.get_application(app_id)
    if stored is None:
        raise HTTPException(status_code=404, detail="application not found")
    return {**stored, "audit": records.get_audit(app_id)}


@api_router.get("/referrals", tags=["underwriter"])
def referrals() -> list[dict[str, Any]]:
    """Queue of cases awaiting a human underwriter (docs/PROCESS.md Refer)."""
    return records.referral_queue()


@api_router.post("/referrals/{app_id}/decision", tags=["underwriter"])
def resolve_referral(app_id: int, decision: str, underwriter_id: str) -> dict[str, Any]:
    """Record a human underwriter's decision on a referred case (GOALS 4.3)."""
    try:
        records.resolve_referral(app_id, decision, underwriter_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"status": "recorded", "application_id": app_id, "decision": decision}


# --- Pages --------------------------------------------------------------


@page_router.get("/", response_class=HTMLResponse, tags=["pages"])
def index(request: Request):
    """Dataset browser: the fictional dataset + resolved underwriter queue."""
    return templates.TemplateResponse(
        request,
        "index.html",
        {"rows": dataset.ui_rows(), "referrals": records.referral_queue()},
    )


@page_router.get("/dataset/{app_id}", response_class=HTMLResponse, tags=["pages"])
def dataset_detail(request: Request, app_id: str):
    """Detail view for one dataset application + one-click agent run."""
    context = dataset.get_record(app_id)
    if context is None:
        raise HTTPException(status_code=404, detail="application not in dataset")
    return templates.TemplateResponse(request, "dataset_detail.html", context)


@page_router.post("/dataset/{app_id}/process", response_class=HTMLResponse, tags=["pages"])
def dataset_process(request: Request, app_id: str):
    """Fire the agent on the dataset application; re-render the detail page."""
    context = dataset.get_record(app_id)
    if context is None:
        raise HTTPException(status_code=404, detail="application not in dataset")
    try:
        result = pipeline.process(context["application"])
    except ValueError as exc:  # intake rejection (e.g. APP-0026) — never a crash
        context["error"] = str(exc)
    else:
        # refresh so `processed` reflects this run (resolve form state etc.)
        context = dataset.get_record(app_id)
        context["result"] = result
    return templates.TemplateResponse(request, "dataset_detail.html", context)


@page_router.post("/underwriter/{app_id}", response_class=HTMLResponse, tags=["pages"])
def underwriter_decision(
    request: Request,
    app_id: int,
    decision: Annotated[str, Form()],
    underwriter_id: Annotated[str, Form()],
):
    """Record a human underwriter decision from the queue (GOALS 4.3)."""
    try:
        records.resolve_referral(app_id, decision, underwriter_id)
    except ValueError as exc:
        return HTMLResponse(f"<p class='outcome-denied'>Not recorded: {exc}</p>", status_code=409)
    return templates.TemplateResponse(
        request,
        "index.html",
        {"rows": dataset.ui_rows(), "referrals": records.referral_queue()},
    )


@page_router.post("/harness/process-batch", response_class=HTMLResponse, tags=["pages"])
def harness_process_batch(request: Request):
    """Process the top 5 waiting applications via batch sub-agents
    (docs/HARNESS.md) and re-render the dataset page with the summary."""
    from loan_ops import harness

    report = harness.run_batch()
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "rows": dataset.ui_rows(),
            "referrals": records.referral_queue(),
            "batch_report": harness.format_summary(report),
        },
    )


@page_router.get("/audit/{app_id}", response_class=HTMLResponse, tags=["pages"])
def audit_page(request: Request, app_id: int):
    stored = records.get_application(app_id)
    if stored is None:
        raise HTTPException(status_code=404, detail="application not found")
    return templates.TemplateResponse(
        request,
        "audit.html",
        {"app": stored, "audit": records.get_audit(app_id)},
    )
