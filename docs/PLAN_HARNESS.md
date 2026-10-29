# Plan: Batch Processing Harness (`docs/PLAN_HARNESS.md`)

Derived plan for a **command-line batch harness** on top of the existing web app
(`docs/PLAN.md` Phase 4). The harness processes applications from the `waiting`
queue in batches of five, with each application handled by an individual
sub-agent that has access to all project docs.

This is a development plan, not part of `docs/PROC.md` — it does not change the
per-application processing rules, checks, thresholds, or the three-outcome
contract (`approved` / `denied` / `refer`).

## Feature: `process-batch` CLI command

Adds a command-line feature to the existing app (alongside `uv run loan-ops`
server launcher in `src/loan_ops/main.py`):

- **Selection rule:** take the applications in `waiting` status from the store,
  ordered by their queue order (top of the list first). Process the top 5.
- **Skip rule:** if **all 5** candidates picked at the top of the queue are
  non-waiting (already processed / referred / decided), skip past them and take
  the **next top 5**, and so on, until a batch containing at least one `waiting`
  application is found or the queue is exhausted.
  - Interpretation: the batch advances in blocks of 5 over the ordered queue;
    a block whose members are all non-waiting is skipped, never processed.
- **Per-application sub-agent:** each of the 5 applications is processed by its
  own individual sub-agent run — one agent instance per application, never
  shared state, never batch-level decisions.
- **Docs access:** every sub-agent runs the full `docs/PROC.md` required
  reading (`docs/PROCESS.md`, `docs/POLICY.md`, `docs/TECH_STACK.md`, plus
  `docs/PROC.md` itself) before touching its application — same reading
  obligation as a single-run agent.
- **Outcomes & audit:** unchanged — each sub-agent runs checks with executed
  tools, classifies against `docs/POLICY.md`, and writes its decision plus
  justifying tool results to the audit log (`docs/PROC.md` steps 3–8).
  Borderline → `refer`, never auto-decided.
- **Reused plumbing:** `pipeline.process()` per application, `store` for queue
  state, `records` for audit, LLM factory from `agents/factory.py`
  (provider-agnostic; Ollama default, OpenRouter optional).

## To-do list

1. [x] **Queue query** — the dataset (`data/loan_applications.json`) order +
  `dataset.processed_runs()` provide the ordered queue with statuses; the
  harness walks it in blocks without extra store queries.
2. [x] **Batch selector** — `harness.select_batch(rows, batch_size=5)` in
  `src/loan_ops/harness.py`; unit-tested for mixed queues, all-non-waiting
  heads, exhausted queue, and final partial block.
3. [x] **Sub-agent runner** — `harness._sub_agent_run` builds a fresh
  decision-agent instance per application (no shared state) and injects the
  `docs/PROC.md` required reading, read from disk, into its prompt; doc reads
  are audited via a `context_loaded` event.
4. [x] **CLI wiring** — `loan-ops process-batch [--batch-size N]` in
  `src/loan_ops/__init__.py`; works without the web server; SQLite
  single-writer caveat documented in `docs/HARNESS.md`.
5. [x] **Sequential processing** — batch members are processed one at a time.
6. [x] **Summary output** — `harness.format_summary` prints id, run id,
  outcome, deciding rule from the persisted run.
7. [x] **Error handling** — missing docs abort before processing;
  intake-invalid rows report `intake_rejected`; provider failure/malformed
  output → `refer` via the existing pipeline paths.
8. [x] **Web app visibility** — "Process top 5 waiting" button on the dataset
  page (`POST /harness/process-batch`) renders the same audit-sourced summary.
9. [x] **Tests** — `tests/test_harness.py`: selection boundaries, end-to-end
  batches with the scripted fake model, skip-past-non-waiting, `context_loaded`
  audit completeness, intake rejection, CLI + web triggers.
10. [x] **Verify & gate** — `uv run pytest -q` (all green incl. the three
  outcomes across a batch) and `uv run ruff check .` clean; scripted-backend
  runs exercise the full block/skip flow end-to-end.
11. [x] **Docs** — `docs/HARNESS.md` (design/reference), `docs/RUN.md` usage
  section, cross-link from `docs/PLAN.md` Phase 4.

## Acceptance criteria

- Running `uv run loan-ops process-batch` on a seeded DB processes exactly the
  top block of 5 containing waiting applications, skipping earlier
  all-non-waiting blocks.
- Each processed application was handled by an individual sub-agent run that
  had read the required docs, executed every check with a tool, and produced
  exactly one outcome in {`approved`, `denied`, `refer`} with a complete audit
  entry.
- No application outside the selected batch is modified.
