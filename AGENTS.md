# Project Instructions

Loan-ops is a local web application that approves loan applications (see `docs/PROCESS.md` and `docs/POLICY.md`).

- **Audience — who does what here:**
  - The **loan-processing agent** (the LangChain agent this app builds, responsible for processing loan applications) must follow `docs/PROC.md` exactly: read its required reading list (`docs/PROCESS.md`, `docs/POLICY.md`, `docs/TECH_STACK.md`) before any run, execute every check with a tool, and close every run with a verified audit entry. That mandate applies to the processing agent — not to agents doing development on this codebase.
  - Agents doing **development work** on this repo follow just the bullets below.
- Stack: Python ≥3.12 managed with **uv**; the approval agent must use LangChain `create_agent`. See `docs/TECH_STACK.md`.
- Install dependencies with `uv sync`, run with `uv run`, add packages with `uv add` — never use pip or raw `python -m`.
- Run `uv run pytest` and `uv run ruff check .` before finishing any change.
- Outcomes are exactly `approved`, `denied`, or `refer` (see `docs/PROC.md` steps 3–5). Thresholds in `docs/POLICY.md` are the source of truth for check logic.
- Every check result must come from an executed tool — never estimate or fabricate. Borderline cases are always `refer`, never auto-decided.
- Log every decision (approve / deny / refer) with the tool results that justified it, then verify the audit entry before marking the task done.
- LLM provider is pluggable: Ollama by default, OpenRouter optionally (`LOAN_OPS_LLM_PROVIDER`). API keys come from the environment only; app logic must stay provider-agnostic. See `docs/TECH_STACK.md`.
- Run/operational questions (setup, env vars, API, troubleshooting) go through `docs/RUN.md`.
