# Goals & Success Criteria

This document defines measurable success cases for each phase of `docs/PLAN.md`. A phase is complete only when every goal in its section is met and checked off with evidence (test names, command output, or a recorded run).

## Phase 1 — Foundation

| # | Goal | Success case (measurable) |
|---|---|---|
| 1.1 | Dependencies pinned and installable | `uv sync` completes on a clean clone with zero resolution errors; `uv.lock` committed. |
| 1.2 | Package layout matches plan | Every directory from Phase 1 step 2 exists and imports without error: `uv run python -c "import loan_ops"`. |
| 1.3 | Env-driven config | Renaming `LOAN_OPS_MODEL` / `OLLAMA_BASE_URL` / `LOAN_OPS_LLM_PROVIDER` changes behavior without code edits; test proves no hardcoded endpoints in `src/`. |
| 1.4 | DB migrations | `uv run alembic upgrade head` on an empty file creates all 4 tables (applications, check_results, decisions, audit_log). |
| 1.5 | Server boots | `uv run loan-ops` serves HTTP; `GET /health` (or equivalent) returns 200 within 5 seconds. |

## Phase 2 — Domain Models & Checks

| # | Goal | Success case (measurable) |
|---|---|---|
| 2.1 | Outcome contract enforced | 100% of unit tests assert outcomes in {`approved`, `denied`, `refer`}; constructing any other value fails type validation. |
| 2.2 | Policy thresholds encoded once | Exactly one constants module depends on raw numbers; a change test asserts score 650, DTI 40%/44%, $50k cap are the values applied. |
| 2.3 | Every check is an agent-usable tool | Each of the 4 checks is callable with a typed schema and returns `CheckResult` (class + reason strings); zero boolean-only returns. |
| 2.4 | Full boundary coverage | `uv run pytest tests/checks` contains ≥ 1 test per boundary in `docs/POLICY.md` — at minimum: score 579/580/649/650, DTI 39.9/40.1/43.9/44.1%, loan ≤/> $50k, fraud 0/1/2 soft signals. |
| 2.5 | Deterministic results | Re-running the same check on the same input twice yields identical `CheckResult` (equality test). |

## Phase 3 — Approval Agent

| # | Goal | Success case (measurable) |
|---|---|---|
| 3.1 | Agent built with `create_agent` | Code review: agent constructed via LangChain `create_agent`; grep shows no hand-rolled chain replacing it. |
| 3.2 | Provider-agnostic | The same agent code runs against both the Ollama-backed and a fake OpenRouter-compatible model in tests; no provider names appear outside the LLM factory. |
| 3.3 | Three outcomes reachable | For each of `approved`, `denied`, `refer`: ≥ 1 scripted end-to-end run produces that outcome from the four real checks. |
| 3.4 | Malformed output degrades safely | When the model returns invalid output, the run is forced to `refer` — 100% of induced-failure tests, zero invalid outcomes emitted. |
| 3.5 | Complete audit trail | Every test run produces an audit entry containing: all 4 check results, final outcome, and the model/provider used. Automated assertion, 100% of agent runs. |
| 3.6 | No fabricated results | Test asserts an agent run that skips a tool call cannot reach `approved`/`denied` — it must end in `refer`. |

## Phase 4 — Web App

| # | Goal | Success case (measurable) |
|---|---|---|
| 4.1 | Core routes exist | HTTP tests cover all route groups: dataset browser, detail view + one-click agent run, submit (JSON API), status, list, underwriter queue, audit viewer — all green. |
| 4.2 | End-to-end UI flow | A scripted request walk-through completes dataset (all rows `waiting`) → open application → fire agent → checks → outcome → audit display in < 30s with no manual intervention. Free-form intake happens via the JSON API or the dataset detail view. |
| 4.3 | Referral integrity | Attempting to auto-close a referred case returns 4xx; only a recorded underwriter decision closes it (test with and without decision). |
| 4.4 | Audit immutability | Attempting to modify an audit entry via any route fails; DB check confirms entry unchanged. |

## Phase 5 — Hardening & Docs

| # | Goal | Success case (measurable) |
|---|---|---|
| 5.1 | Provider failure degrades to refer | With Ollama stopped and an invalid OpenRouter key, an in-flight application ends in `refer` with a logged error; 0 crashes. |
| 5.2 | Fail-fast config | Missing API key for the selected provider stops startup with an actionable message within 5 seconds. |
| 5.3 | Quality gates green | `uv run pytest && uv run ruff check .` pass with 0 warnings; coverage of `checks/`, `agents/`, `store/` ≥ 90%. |
| 5.4 | Fresh-clone reproducibility | From a fresh clone with only uv + Ollama installed: `uv sync && uv run loan-ops` produces a working app; verification recorded in README. |
| 5.5 | Docs complete | README and all `docs/` files cross-reference each other; a reviewer can run Phase 4's walk-through using docs alone. |

## Milestone Sign-off

Each milestone (M1–M5) maps to the matching phase. Sign-off requires: all goal rows checked off, evidence linked, and the phase's verify command re-run from a clean state on the day of sign-off.
