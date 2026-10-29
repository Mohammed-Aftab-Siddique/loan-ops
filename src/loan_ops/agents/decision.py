"""Decision agent — LangChain `create_agent` per docs/TECH_STACK.md (mandatory).

Design (docs/PROC.md, GOALS 3.x):
- The agent's tools are exactly the four checks plus decision recording.
- Check tools execute against the concrete application and their results are
  collected per run; `record_decision` refuses to fire before all four checks
  have actually executed (no fabricated results — GOALS 3.6).
- The final outcome is derived deterministically from the executed check
  results; the agent's structured output supplies the rule narrative. Any
  malformed or missing structured output is forced to `refer` (GOALS 3.4).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from langchain.agents import create_agent
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from loan_ops import checks as check_mod
from loan_ops import policy
from loan_ops.models import CheckResult, Decision, LoanApplication

SYSTEM_PROMPT = """\
You are the loan-ops approval agent. You process applications ONLY by \
executing your check tools — you must never decide from memory or estimate.

Procedure (docs/PROC.md; rules sourced from docs/PROCESS.md and docs/POLICY.md):
1. Call the four check tools in order: identity_check, credit_check, \
affordability_check, fraud_check.
2. Read the returned result classes ("pass" / "fail" / "refer") and reasons.
3. Call record_decision exactly once with the application_id, the outcome, \
and the governing rule. Allowed outcomes: approved, denied, refer.
   - All four checks "pass" and loan amount <= $50,000 -> "approved".
   - Any check "fail" -> "denied" (cite the failing check).
   - Anything else (any "refer", or amount > $50,000) -> "refer".
4. Finally respond with ONLY a JSON object, no other text:
   {"application_id": "<id>", "outcome": "<approved|denied|refer>", \
"rule": "<the rule(s) from the process that apply>"}

You must never flip a "refer" case to approved/denied yourself.
"""


class FinalDecision(BaseModel):
    """Structured contract for the three-outcome decision (GOALS 3.3/3.4)."""

    application_id: str = Field(min_length=1)
    outcome: Literal["approved", "denied", "refer"]
    rule: str = Field(min_length=1, description="Rule(s) from the process that apply")


@dataclass
class _RunState:
    application: LoanApplication
    results: dict[str, CheckResult] = field(default_factory=dict)

    @property
    def all_checks_executed(self) -> bool:
        return all(name in self.results for name in check_mod.CHECK_NAMES)


def deterministic_outcome(
    results: dict[str, CheckResult], loan_amount: float
) -> tuple[str, str]:
    """Decision rules from docs/PROCESS.md, applied to executed results.

    Missing check results mean the run is incomplete -> always refer.
    """
    classes = [results[name].result_class for name in check_mod.CHECK_NAMES if name in results]
    if len(results) < len(check_mod.CHECK_NAMES):
        return "refer", "Incomplete check results; cannot decide automatically."
    failures = [n for n, r in results.items() if r.result_class == "fail"]
    if failures:
        return "denied", f"Hard fail in {failures[0]} check: {results[failures[0]].reason}"
    if loan_amount > policy.AUTO_APPROVAL_MAX_AMOUNT:
        return "refer", f"Loan amount ${loan_amount:,.2f} exceeds the automated limit."
    refers = [n for n, r in results.items() if r.result_class == "refer"]
    if refers:
        return "refer", f"Borderline result in {', '.join(sorted(refers))}: " + "; ".join(
            results[n].reason for n in sorted(refers)
        )
    if all(c == "pass" for c in classes):
        return (
            "approved",
            "All four checks passed and the amount is within the automated limit.",
        )
    return "refer", "Incomplete check results; cannot decide automatically."


def build_decision_agent(model: BaseChatModel, app: LoanApplication) -> tuple[Any, _RunState]:
    """Construct the loan decision agent for one application run.

    Returns (compiled create_agent graph, run state collecting tool results).
    """
    state = _RunState(application=app)

    def _run_check(name: str) -> dict[str, Any]:
        check_fn = getattr(check_mod, f"{name}_check")
        result: CheckResult = check_fn(app)
        state.results[name] = result
        return result.model_dump()

    @tool
    def identity_check() -> dict[str, Any]:
        """Run the identity check (docs/POLICY.md §1). Takes no arguments."""
        return _run_check("identity")

    @tool
    def credit_check() -> dict[str, Any]:
        """Run the credit check (docs/POLICY.md §2). Takes no arguments."""
        return _run_check("credit")

    @tool
    def affordability_check() -> dict[str, Any]:
        """Run the affordability check (docs/POLICY.md §3). Takes no arguments."""
        return _run_check("affordability")

    @tool
    def fraud_check() -> dict[str, Any]:
        """Run the fraud check (docs/POLICY.md §4). Takes no arguments."""
        return _run_check("fraud")

    @tool
    def record_decision(
        application_id: str,
        outcome: Literal["approved", "denied", "refer"],
        rule: str,
    ) -> dict[str, Any]:
        """Record the final decision. All four checks must have been executed first.

        Args:
            application_id: the application being decided
            outcome: one of approved | denied | refer
            rule: the rule(s) from the process that produced the outcome
        """
        if not state.all_checks_executed:
            missing = [n for n in check_mod.CHECK_NAMES if n not in state.results]
            return {
                "error": (
                    f"Checks {missing} have not been executed. Run the check tools "
                    "first; results must not be fabricated."
                )
            }
        if application_id not in ("", str(app.application_id)):
            return {"error": f"application_id mismatch: {application_id}"}
        return {"recorded": True, "outcome": outcome, "rule": rule}

    agent = create_agent(
        model=model,
        tools=[
            identity_check,
            credit_check,
            affordability_check,
            fraud_check,
            record_decision,
        ],
        system_prompt=SYSTEM_PROMPT,
        response_format=FinalDecision,
        name="loan_decision_agent",
    )
    return agent, state


def run_decision(
    app: LoanApplication,
    model: BaseChatModel | None = None,
    extra_context: str | None = None,
) -> Decision:
    """Run the agent end-to-end for one application and return the Decision.

    Each call builds a fresh agent instance and run state — one isolated
    sub-agent run per application. `extra_context` (e.g. harness-loaded
    required reading, docs/HARNESS.md) is appended to the task prompt.

    Any structured-output failure degrades to outcome "refer" (GOALS 3.4);
    provider errors are raised to callers (docs/PROC.md step 3).
    """
    from loan_ops.agents.factory import build_chat_model

    model = model or build_chat_model()
    agent, state = build_decision_agent(model, app)

    app_id = app.application_id or "unsaved"
    prompt = (
        f"Process loan application {app_id} from {app.applicant_name} "
        f"for ${app.loan_amount:,.2f} ({app.loan_purpose}). "
        "Run all four checks in order, then record the decision."
    )
    if extra_context:
        prompt = f"{prompt}\n\n{extra_context}"
    outcome, rule = "refer", "Agent produced no structured decision; escalated."
    structured_ok = False
    try:
        result = agent.invoke({"messages": [("user", prompt)]})
        structured = result.get("structured_response") or _parse_structured(result)
        if isinstance(structured, FinalDecision) and structured.application_id == str(
            app.application_id or ""
        ):
            structured_ok = True
            if state.all_checks_executed:
                outcome = structured.outcome
                rule = structured.rule
                if app.loan_amount > policy.AUTO_APPROVAL_MAX_AMOUNT and outcome != "refer":
                    rule = f"Overridden to refer: {rule} (amount exceeds auto-approval limit)."
                    outcome = "refer"
    except Exception as exc:  # structured/parse/provider failure
        if not state.results:
            # the run never started (e.g. unreachable provider): reraise so the
            # caller can apply its degraded path instead of a blind refer
            raise
        rule = f"Agent decision failed ({type(exc).__name__}), escalated to refer."

    expected_outcome, expected_rule = deterministic_outcome(state.results, app.loan_amount)
    if structured_ok and state.all_checks_executed and outcome != expected_outcome:
        # agent narrative may differ, but the outcome obeys the process rules
        outcome = expected_outcome
        rule = f"[rule-mismatch: agent said otherwise] {expected_rule}"

    return Decision(
        application_id=str(app.application_id or ""),
        outcome=outcome,
        rule=rule,
        check_results=[state.results[n] for n in check_mod.CHECK_NAMES if n in state.results],
        model=str(getattr(model, "model_name", "") or getattr(model, "model", "") or ""),
        provider=_provider_name(model),
    )


def _parse_structured(result: dict) -> FinalDecision | None:
    """Extract FinalDecision from the agent's final AI message.

    Prefers the graph's structured_response; falls back to parsing the final
    non-empty text as JSON. Works with any provider since it inspects plain
    message content.
    """
    import json
    import re

    messages = result.get("messages", [])
    for message in reversed(messages):
        text = getattr(message, "content", None)
        if not text or getattr(message, "tool_calls", None):
            continue
        text = str(text).strip()
        fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        candidate = fenced.group(1) if fenced else text
        try:
            data = json.loads(candidate)
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(data, dict) and {"application_id", "outcome", "rule"} <= set(data):
            try:
                return FinalDecision(**data)
            except Exception:
                return None
        return None
    return None


def _provider_name(model: BaseChatModel) -> str:
    return getattr(model, "_llm_type", "") or type(model).__name__
