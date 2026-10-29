# Implementation Plan

This document is the build plan for the local web application described in `docs/PROCESS.md`, `docs/POLICY.md`, and `docs/TECH_STACK.md`. Follow this order; each phase ends with a verifiable outcome.

## Phase 1 — Foundation

1. Finalize `pyproject.toml`: description, dependencies (fastapi, uvicorn, SQLAlchemy, alembic, jinja2, pytest, ruff) via `uv add`, and the `loan-ops` CLI entrypoint.
2. Scaffold `src/loan_ops/` package layout:

   ```text
   src/loan_ops/
   ├── main.py          # CLI entrypoint, uvicorn launcher
   ├── app/             # FastAPI app, routes, templates
   ├── agents/          # LangChain create_agent setup, Ollama wiring
   ├── checks/          # identity, credit, affordability, fraud checks
   ├── models/          # Pydantic schemas + SQLAlchemy ORM models
   ├── store/           # SQLite persistence, audit log
   └── config.py        # env-based settings (LOAN_OPS_MODEL, OLLAMA_BASE_URL)
   ```

3. Set up config with Pydantic settings: Ollama endpoint/model and optional OpenRouter settings (`LOAN_OPS_LLM_PROVIDER`, `OPENROUTER_API_KEY`) are env-driven; keys never live in the repo.
4. Implement an LLM factory in `agents/` that returns the configured chat model (Ollama default, OpenRouter alternative) behind one interface — the agent, checks, and app logic stay provider-agnostic.
5. Alembic migration for initial schema: applications, check_results, decisions, audit_log.
6. **Verify:** `uv run loan-ops` starts the FastAPI server with an empty local DB.

## Phase 2 — Domain Models & Checks

1. Pydantic models: `LoanApplication`, `CheckResult` (pass / fail-hard / refer + reason), `Outcome` (`approved` / `denied` / `refer`).
2. Implement the four checks in `checks/`, one module each, all thresholds read from a single policy constants module sourced from `docs/POLICY.md` (score 650, DTI 40% / 44% hard limit, $50k auto-approval cap, fraud soft-signal rules).
3. Each check is a typed tool callable by the agent; a check never returns a bare boolean — always result class + reason.
4. **Verify:** unit tests in `tests/` cover every pass / hard-fail / refer boundary from `docs/POLICY.md` (e.g., 580 vs 649 vs 650 scores; 40% vs 44% DTI).

## Phase 3 — Approval Agent

1. Build the decision agent with LangChain `create_agent`, backed by the LLM factory (Ollama by default, OpenRouter optionally via `LOAN_OPS_LLM_PROVIDER`).
2. The agent depends only on the factory's chat-model interface; it must not import or branch on a specific provider.
3. The agent's tools are exactly the four checks plus audit logging; the system prompt encodes the decision rules and the `refer` escalation rules from `docs/PROC.md`.
4. Guarantee the three-outcome contract: the agent must emit a structured `Outcome` object; malformed output forces `refer`.
5. Log every agent run: tool calls, raw results, final outcome, and the model/provider used, to the audit log.
6. **Verify:** integration tests with a fake backend drive an application end-to-end to each of the three outcomes — once against an Ollama-backed model and once against a fake OpenRouter-compatible model.

## Phase 4 — Web App

1. FastAPI routes: dataset browser, per-application detail, one-click agent processing, applications list/status, underwriter queue for `refer` cases, audit log viewer.
2. Jinja2 (+ HTMX) UI: **no intake form** — the UI lists the fictional dataset from `data/` (**every application starts in a waiting state**); clicking an application opens its details (full intake fields) with a button that fires the agent to process it, after which the status reflects the actual outcome. Free-form submission stays available via the JSON API.
3. Audit entries immutable from the UI; referrals only closable by a human decision.
4. **Verify:** manual walk-through with the local server: open dataset → open an application → fire the agent → outcome + audit entry visible.

*Follow-up: the batch harness (process the top 5 waiting applications via
individual sub-agents from the CLI) is planned and built in
`docs/PLAN_HARNESS.md` / `docs/HARNESS.md`.*

## Phase 5 — Hardening & Docs

1. Error handling: unreachable or misconfigured provider (dead Ollama, bad OpenRouter key) → application states as `refer` (never guess), with a clear error surfaced; missing API keys fail fast at startup with an actionable message.
2. Add `pytest-cov` gate and fix ruff warnings; no warnings tolerated in CI-style local run.
3. Update `README.md` with run instructions (`uv sync`, `uv run loan-ops`, provider configuration) and linking all `docs/` files; refresh `docs/PROCESS.md` conventions section.
4. **Verify:** full suite `uv run pytest && uv run ruff check .` passes, and a fresh clone runs with only `uv sync` + Ollama installed (OpenRouter remaining optional).

## Milestones

| Milestone | Definition of done |
|---|---|
| M1 | Phase 1 — server boots, DB migrated |
| M2 | Phase 2 — checks implemented, all policy boundary tests green |
| M3 | Phase 3 — agent produces all three outcomes with authored audit logs |
| M4 | Phase 4 — full local UI flow works end-to-end |
| M5 | Phase 5 — clean test/lint run, docs complete |
