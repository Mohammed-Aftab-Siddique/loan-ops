"""Scripted fake chat models — the same agent code runs against both fakes
(GOALS 3.2: provider-agnostic agent code, integration without a live LLM)."""

from __future__ import annotations

from typing import Any, Optional

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import PrivateAttr


class _Scripted(BaseChatModel):
    """Base for fakes: 4 check tool calls -> record_decision -> structured text."""

    model_name: str = "scripted-model"
    scenario_outcome: str = "approved"
    scenario_rule: str = "scripted rule"
    garbage: bool = False
    provider_label: str = "scripted"

    _turn: int = PrivateAttr(default=0)
    _app_id: str = PrivateAttr(default="0")

    @classmethod
    def create_scripted(
        cls, outcome: str, rule: str, garbage: bool = False, **kwargs: Any
    ) -> "_Scripted":
        """Constructor helper: BaseModel-style (kwargs-only) instantiation."""
        return cls(
            scenario_outcome=outcome, scenario_rule=rule, garbage=garbage, **kwargs
        )

    @property
    def _llm_type(self) -> str:
        return self.provider_label

    @property
    def _identifying_params(self) -> dict[str, Any]:
        return {"model_name": self.model_name}

    def bind_tools(self, tools: Any, **kwargs: Any) -> "_Scripted":
        return self

    def with_structured_output(self, schema: Any, **kwargs: Any) -> "_Scripted":
        return self

    def _generate(  # type: ignore[override]
        self,
        messages: list[BaseMessage],
        stop: Optional[list[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        import re

        self._turn += 1
        if self._turn == 1:
            for message in messages:
                match = re.search(r"application\s+(\S+)", str(getattr(message, "content", "")))
                if match:
                    self._app_id = match.group(1)
                    break
            else:
                self._app_id = "0"
        if self._turn == 1:
            message = AIMessage(
                content="",
                tool_calls=[
                    {"name": fn, "args": {}, "id": f"call_{fn}"}
                    for fn in (
                        "identity_check",
                        "credit_check",
                        "affordability_check",
                        "fraud_check",
                    )
                ],
            )
        elif self._turn == 2:
            message = AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "record_decision",
                        "args": {
                            "application_id": self._app_id,
                            "outcome": self.scenario_outcome,
                            "rule": self.scenario_rule,
                        },
                        "id": "call_record",
                    }
                ],
            )
        else:
            message = self._structured_message()
        return ChatResult(generations=[ChatGeneration(message=message)])

    def _structured_message(self) -> AIMessage:
        payload = (
            f'{{"application_id": "{self._app_id}", '
            f'"outcome": "{self.scenario_outcome}", '
            f'"rule": "{self.scenario_rule}"}}'
        )
        return AIMessage(content=payload)


class ScriptedToolsModel(_Scripted):
    """Writes a valid FinalDecision JSON payload in the structured step."""

    provider_label: str = "fake-ollama"

    def __init__(self, outcome: str, rule: str, garbage: bool = False, **kwargs: Any):
        super().__init__(
            scenario_outcome=outcome, scenario_rule=rule, garbage=garbage, **kwargs
        )


class GarbageOutputModel(ScriptedToolsModel):
    """Emits unparseable structured output (tests GOALS 3.4 forced-refer path)."""

    garbage: bool = True
    provider_label: str = "fake-garbage"

    def _structured_message(self) -> AIMessage:
        return AIMessage(content="not-valid-structured-output")


class ProviderUnavailableModel(BaseChatModel):
    """Simulates an unreachable/broken provider (GOALS 5.1)."""

    model_name: str = "failing-model"

    @property
    def _llm_type(self) -> str:
        return "always-failing-model"

    @property
    def _identifying_params(self) -> dict[str, Any]:
        return {}

    def bind_tools(self, tools: Any, **kwargs: Any) -> "ProviderUnavailableModel":
        return self

    def _generate(  # type: ignore[override]
        self,
        messages: list[BaseMessage],
        stop: Optional[list[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        raise RuntimeError("provider unreachable")
