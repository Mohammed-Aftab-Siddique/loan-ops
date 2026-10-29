# The Batch Harness (`docs/HARNESS.md`)

Reference document for the batch-processing harness: a command-line feature
(plus one UI trigger) that processes the top 5 **waiting** applications from the
dataset queue, with each application handled by an **individual sub-agent** that
has access to all project docs. The per-application rules it executes are
exactly `docs/PROC.md` — this harness changes nothing about checks, thresholds,
or the three-outcome contract.

## What "waiting" means

The web UI marks every dataset application (`data/loan_applications.json`,
IDs `APP-0001`…) as **waiting** until an agent run exists for it in the store
(`dataset.ui_rows()` — no run → "waiting"; processed apps show their outcome).
The queue order is the dataset order. Non-waiting apps are: processed
(`approved`/`denied`), referred (`refer` pending a human underwriter), or
whose latest run ended in a decision.

## Usage

```bash
uv run loan-ops process-batch           # process the top 5 waiting apps
uv run loan-ops process-batch --batch-size 5
```

`uv run loan-ops` (no subcommand) still boots the web server. In the UI, the
dataset page has a **Process top 5 waiting** button that runs the same batch
function and shows the summary banner. The summary printed/surfaced is sourced
from the persisted audit trail — the harness never re-derives outcomes.

## Queue selection algorithm

Walk the full queue in blocks of `batch_size` (5) in dataset order:

1. Take the next block of 5 (the final block may be smaller).
2. If **all 5** members are non-waiting → skip the block entirely
   ("next top 5") and continue from step 1.
3. The first block containing **≥ 1 waiting** application is the selected
   batch. Within it, **only the waiting members are processed** — an
   application that already has a run is never re-processed (a `refer` case is
   decided only by a human underwriter, `docs/PROCESS.md`), and the harness
   stops after this block (it never scans further).
4. If the queue is exhausted with no waiting apps found, the harness reports
   "nothing to process".

Example: queue of 12 where apps 1–7 already have runs → blocks 1 (apps 1–5) and
2 (apps 6–10) are inspected; block 2 contains waiting apps 8, 9, 10 → those
three are processed individually; nothing else is touched.

## Sub-agents

Each selected application is processed by its **own sub-agent run** — one
fresh `LangChain create_agent` decision agent instance per application
(`agents.decision.build_decision_agent`), with its own isolated run state. No
state, conversation, or check results are ever shared between sub-agents, and
sub-agent runs are strictly sequential (one SQLite writer; unambiguous audit
order).

Doc access (`docs/PROC.md` "Required Reading"): before each sub-agent run the
harness reads the four required documents from disk — `docs/PROC.md`,
`docs/PROCESS.md`, `docs/POLICY.md`, `docs/TECH_STACK.md` — as real file reads
(never fabricated). Each sub-agent's task prompt carries the read context, and
a `context_loaded` audit event records the doc names + SHA-256 digests for that
application, so "the sub-agent had access to all the docs" is verifiable in the
audit trail.

Per sub-agent run (docs/PROC.md steps 2–8, unchanged):

- the four checks are executed as tools, never estimated;
- the outcome is derived deterministically from executed check results —
  borderline is always `refer`, never auto-decided;
- malformed structured output degrades to `refer`; an unreachable LLM provider
  escalates the whole run to `refer` with the executed check results;
- every run writes `application_received`, `context_loaded`, `checks_executed`,
  `decision_recorded` audit entries, and the harness verifies the trail is
  complete before counting the run as done.

## Error handling

| Situation | Behavior |
|---|---|
| Missing/unreadable doc file | Harness aborts before processing anything (reading step is mandatory). |
| Intake-invalid record (e.g. APP-0026) | Reported as `intake_rejected`; other applications continue. |
| Provider unavailable / bad output | That application is recorded as `refer`; batch continues. |
| All top 5 non-waiting | Block skipped; next block inspected. |
| No waiting apps at all | "Nothing to process" report; exit 0. |

## Concurrency & scope

- Run while the web server is stopped (or accept SQLite single-writer risk).
- Only applications inside the selected block are ever modified.
- See `docs/PLAN_HARNESS.md` for the build plan; `docs/RUN.md` for day-to-day
  operation.
