# Tech Stack

This document lists the required stack for the **loan-ops** local web application, which implements the loan process in `docs/PROCESS.md` under the policies in `docs/POLICY.md`. The stack is chosen for local-first operation — no external SaaS is required to run the application.

## Core

| Layer | Choice | Notes |
|---|---|---|
| Language | **Python ≥ 3.12** | All application code, agents, and tooling. |
| Package manager | **uv** | Dependency management, virtual environments, and task running (`pyproject.toml` + `uv.lock` are the source of truth). |
| AI framework | **LangChain** (`create_agent`) | The decision agent is built with `langchain`'s `create_agent`, orchestrating the four checks as tool calls. |
| Agent runtimes | **LangGraph / deepagents** | Backing runtime used by `create_agent`; deepagents for tool-heavy agent flows. |
| Validation | **Pydantic** | Typed models for applications, check results, and outcomes (`approved` / `denied` / `refer`). |

## Application Layer

| Concern | Choice | Notes |
|---|---|---|
| Web server | **FastAPI** | Serves the local UI and JSON API for submitting and tracking applications. |
| UI | **Jinja2 templates + lightweight HTMX/Alpine.js** | Simple server-rendered frontend; no Node build step required. |
| Database | **SQLite** (via SQLAlchemy/Alembic) | Local single-file store for applications, check results, audit log, and underwriter referrals. |
| Background work | FastAPI background tasks / LangGraph async runs | Sufficient for local use; no message broker needed. |

## LLM Provider

- Providers are pluggable and selected at runtime via `LOAN_OPS_LLM_PROVIDER`:

  | Provider | Package | Config |
  |---|---|---|
  | **Ollama** (default) | `langchain-ollama` | `OLLAMA_BASE_URL`, `LOAN_OPS_MODEL` — fully offline, no keys. |
  | **OpenRouter** | `langchain-openai` (OpenAI-compatible endpoint) | `LOAN_OPS_LLM_PROVIDER=openrouter`, `LOAN_OPS_MODEL` (e.g. `provider/model`), `OPENROUTER_API_KEY` from the environment. |

- Provider endpoints are chosen by the user at runtime; the code must not hardcode either provider. API keys are read from the environment only — never stored in the repo or config files.
- Hosted models (OpenRouter) are optional convenience, not a requirement: the app must remain fully functional with Ollama alone.

## Tooling & Quality

| Tool | Purpose |
|---|---|
| **uv** | `uv sync`, `uv run`, `uv add` — install, run, and manage dependencies. |
| **pytest** (+ `pytest-cov`) | Unit and integration tests; check rules in `docs/POLICY.md` must have test coverage. |
| **ruff** | Linting and formatting. |

## Constraints

- Everything must run locally; only Ollama is required for a fully offline setup. Hosted models via **OpenRouter** are an optional runtime choice (`LOAN_OPS_LLM_PROVIDER`), never a mandatory dependency.
- The approval agent must be implemented with **LangChain `create_agent`** — ad-hoc prompt scripts or hand-rolled chains are not acceptable substitutes.
- Provider selection is confined to the LLM factory: application and check logic must be provider-agnostic.
- All agent decisions (approve / deny / refer) must be logged to the audit trail with the tool results that justified them.
