# Running loan-ops

This document explains how to run the local web application, operate it day-to-day, and troubleshoot common failures. It reflects the stack in `docs/TECH_STACK.md`; the process it executes is `docs/PROC.md`.

## Prerequisites

| Requirement | Notes |
|---|---|
| Python ≥ 3.12 | Managed by uv; set `.python-version` is respected. |
| [uv](https://docs.astral.sh/uv/) | All commands go through `uv run` — never pip or raw `python`. |
| [Ollama](https://ollama.com) | Default provider; pull the model once: `ollama pull qwen3.5:4b`. |
| OpenRouter key *(optional)* | Only if you select the `openrouter` provider; read from the environment, never stored in the repo. |

## First-time setup

```bash
uv sync                                   # install dependencies into .venv
ollama pull qwen3.5:4b                    # default model (once)
uv run alembic -c alembic.ini upgrade head  # initialize the database (canonical way)
```

`uv run loan-ops` also creates the schema automatically if the DB is empty — step 3 is optional in development.

## Run the app

```bash
uv run loan-ops                # boots at http://127.0.0.1:8000
```

You will get:

- the UI at `/` — a browser for the fictional dataset in `data/` (no intake form). Every application starts in a **waiting** state; opening one shows its details and a button that fires the agent, and its status updates to the actual outcome once processed,
- audit pages at `/audit/{id}` (read-only, append-only trail),
- the JSON API (see below) and interactive docs at `/docs`,
- an audit log in SQLite (`applications`, `check_results`, `decisions`, `audit_log`).

Free-form intake is JSON-API-only; every application submitted through the dataset UI keeps its dataset ID (`application_id` like `APP-0001`) in the stored payload.

## Operating from the command line: the batch harness

While `uv run loan-ops` drives one application at a time through the UI, the
batch harness (see `docs/HARNESS.md`) processes the queue on its own:

```bash
uv run loan-ops process-batch              # process the top 5 waiting applications
uv run loan-ops process-batch --batch-size 5
```

It walks the dataset queue in blocks of 5: a block whose members all already
have a run is skipped; the first block containing waiting applications is
processed, one **individual sub-agent run per application** (each with the four
documents required by `docs/PROC.md` read from disk and audited via a
`context_loaded` event). The dataset page also has a **Process top 5 waiting**
button running the same batch through the web app. Only applications inside
the selected block are ever modified; run it while the server is stopped
(SQLite single-writer).

## Configuration (environment variables only)

| Variable | Default | Purpose |
|---|---|---|
| `LOAN_OPS_LLM_PROVIDER` | `ollama` | `ollama` (fully local) or `openrouter` (hosted fallback). |
| `LOAN_OPS_MODEL` | `qwen3.5:4b` | Model name; for openrouter use `provider/model` form. |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama endpoint. |
| `OPENROUTER_BASE_URL` | `https://openrouter.ai/api/v1` | OpenAI-compatible endpoint override. |
| `OPENROUTER_API_KEY` | *(unset)* | Required only when provider is `openrouter`. |
| `LOAN_OPS_DB_URL` | `sqlite:///./loan_ops.db` | Database URL (SQLite default). |
| `LOAN_OPS_HOST` / `LOAN_OPS_PORT` | `127.0.0.1` / `8000` | Server bind address (also `--host` / `--port` CLI flags). |

Secrets never enter the repo or config files. Bad configuration fails fast at startup with an actionable message.

Examples:

```bash
uv run loan-ops --port 9000                                   # custom port
LOAN_OPS_MODEL=deepseek-r1:7b uv run loan-ops                 # different local model
OLLAMA_BASE_URL=http://192.168.1.5:11434 uv run loan-ops      # remote Ollama
LOAN_OPS_LLM_PROVIDER=openrouter \
OPENROUTER_API_KEY=sk-... \
LOAN_OPS_MODEL=mistralai/mistral-small \
uv run loan-ops                                               # hosted model via OpenRouter
```

OpenRouter is optional: the app must always run fully offline with Ollama alone.

## Using the API

Submit an application (runs the full `docs/PROC.md` pipeline synchronously):

```bash
curl -s -X POST http://127.0.0.1:8000/api/applications \
  -H 'Content-Type: application/json' \
  -d '{
    "applicant_name": "Jane Doe",
    "applicant_id_number": "ID-123456",
    "identity_doc_valid": true,
    "proof_of_address_age_days": 30,
    "credit_score": 700,
    "credit_history_months": 48,
    "monthly_income": 8000,
    "income_documents_current": true,
    "existing_monthly_debt": 500,
    "loan_amount": 12000,
    "loan_purpose": "home"
  }'
```

Response contains the outcome (`approved` / `denied` / `refer`), the decision rule, all four check results, and the audit event count.

Other endpoints:

| Method & path | Purpose |
|---|---|
| `GET /api/health` | Liveness check. |
| `GET /api/applications` | List applications (newest first). |
| `GET /api/applications/{id}` | Detail incl. check results + full audit trail. |
| `GET /api/referrals` | Queue awaiting a human underwriter. |
| `POST /api/referrals/{id}/decision?decision=approved|denied&underwriter_id=<id>` | Record a human decision (referrals only; invalid values → 409). |

Rules the app enforces (from `docs/PROCESS.md`): outcomes are exactly `approved`, `denied`, `refer`; loans above $50,000 are always `refer`; only a recorded human decision closes a referral; audit entries are append-only.

## Operator playbook

| Situation | Action |
|---|---|
| Application is `refer` | Open `/api/referrals`, review the check reasons in `/audit/{id}`, record a decision with your underwriter ID. |
| Audit review | `GET /api/applications/{id}` returns every check result and the deciding rule + model/provider that produced it. |
| Database reset (dev only) | Delete `loan_ops.db` and re-run the alembic command above. |
| Provider down mid-run | Application is recorded as `refer` with the executed check results; nothing is guessed. Restart Ollama and re-run. |
| Backups | Copy `loan_ops.db` while the server is stopped (SQLite single-file snapshot). |

## Verification & quality gates

```bash
uv run pytest -q --cov=loan_ops   # tests + coverage (gate: ≥90% on checks/agents/store)
uv run ruff check .               # lint; 0 warnings tolerated
```

Run migrations from a clean clone on a fresh DB before signing off anything (see `docs/GOALS.md`).

## Troubleshooting

| Symptom | Cause & fix |
|---|---|
| Startup error: `LOAN_OPS_LLM_PROVIDER=... is not supported` | Only `ollama` / `openrouter` are accepted. |
| Startup error: `requires OPENROUTER_API_KEY` | Export the key before selecting the openrouter provider. |
| Every application becomes `refer` with "provider unavailable" | Ollama isn't reachable: check `curl $OLLAMA_BASE_URL/api/tags` and that `ollama serve` is running. |
| Model emits invalid narratives | Not a threat: the agent derives the final outcome from the executed check results, so invalid narratives are discarded. Prefer a larger model (or OpenRouter) if narratives matter for review quality. |
| Port already in use | `uv run loan-ops --port 9000`. |
| Slow first decision | Local model cold start; once the model warms up, subsequent runs are faster. |
