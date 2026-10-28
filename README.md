# loan-ops

Local web application that processes loan applications through the four checks of [`docs/PROCESS.md`](docs/PROCESS.md) and produces exactly one of three outcomes: **approved**, **denied**, or **refer** (human underwriter).

## Documentation

| Document | Purpose |
|---|---|
| [`docs/PROCESS.md`](docs/PROCESS.md) | The loan approval process — intake, the four checks, outcomes. |
| [`docs/POLICY.md`](docs/POLICY.md) | Policies and thresholds behind each check. |
| [`docs/PROC.md`](docs/PROC.md) | The mandatory step-by-step procedure an agent follows per application. |
| [`docs/TECH_STACK.md`](docs/TECH_STACK.md) | Required stack: Python, uv, LangChain `create_agent`. |
| [`docs/PLAN.md`](docs/PLAN.md) | Implementation plan, phase by phase. |
| [`docs/GOALS.md`](docs/GOALS.md) | Measurable success criteria for every plan phase. |
| [`docs/RUN.md`](docs/RUN.md) | How to run the app: setup, configuration, API, operations, troubleshooting. |

The loan-processing agent follows [`docs/PROC.md`](docs/PROC.md) — it defines the mandatory reading and the step-by-step rules every application run must complete.

## Quickstart

Requirements: Python ≥3.12 with [uv](https://docs.astral.sh/uv/), and [Ollama](https://ollama.com) with a model pulled (default `qwen3.5:4b`).

```bash
uv sync                 # install dependencies into .venv
uv run loan-ops         # boot the web app at http://127.0.0.1:8000
```

Open `http://127.0.0.1:8000` to browse the bundled fictional dataset (`data/`), click an application to see its details and fire the agent on it (every application starts in a *waiting* state); free-form intake via the API:

## Sample dataset

[`data/loan_applications.json`](data/loan_applications.json) is a fictional intake dataset aligned with the docs and code (every field name matches `LoanApplication`; every policy boundary — the $50k cap, DTI 40/44 edges, score 580/650, 90-day address doc, 11-month history, 24-month settled default, banned purposes, fraud soft signals — is exercised). [`data/expected_decisions.json`](data/expected_decisions.json) holds the loan approval status per record plus the reason, produced by running the real code path — regenerate it anytime with:

```bash
uv run python scripts/generate_expected.py
```


```bash
curl -s -X POST http://127.0.0.1:8000/api/applications \
  -H 'Content-Type: application/json' \
  -d '{"applicant_name":"Jane","applicant_id_number":"ID-1","identity_doc_valid":true,
       "proof_of_address_age_days":30,"credit_score":700,"credit_history_months":48,
       "monthly_income":8000,"income_documents_current":true,
       "existing_monthly_debt":500,"loan_amount":12000,"loan_purpose":"home"}'
```

## Configuration (environment only)

| Variable | Default | Purpose |
|---|---|---|
| `LOAN_OPS_LLM_PROVIDER` | `ollama` | `ollama` (local) or `openrouter` (hosted via OpenAI-compatible endpoint). |
| `LOAN_OPS_MODEL` | `qwen3.5:4b` | Model name for the selected provider. |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama endpoint. |
| `OPENROUTER_API_KEY` | — | Required when provider is `openrouter`; read from the environment only. |
| `LOAN_OPS_DB_URL` | `sqlite:///./loan_ops.db` | Database (SQLite by default). |

OpenRouter is always optional — the app must run fully offline with Ollama alone (see `docs/TECH_STACK.md`).

## Database

Migrations are canonical; initialize with:

```bash
LOAN_OPS_DB_URL=sqlite:///./loan_ops.db uv run alembic -c alembic.ini upgrade head
```

`uv run loan-ops` also creates the schema for convenience (tables: applications, check_results, decisions, audit_log).

## Development

```bash
uv run pytest -q --cov=loan_ops   # tests + coverage gate (≥90% on checks/agents/store)
uv run ruff check .               # lint (0 warnings tolerated)
```
