from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from incident_investigator.contracts import FinalDiagnosis

from .prompting import InvestigatorPrompt


@dataclass(frozen=True)
class RequestedToolCall:
    call_id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class ToolOutput:
    call_id: str
    output: dict[str, Any]


@dataclass
class InvestigatorTurn:
    response_id: str
    diagnosis: FinalDiagnosis | None = None
    tool_calls: list[RequestedToolCall] = field(default_factory=list)
    decision_summary: str | None = None
    usage: dict[str, Any] = field(default_factory=dict)


class InvestigatorClient(Protocol):
    model: str
    reasoning_effort: str

    def respond(
        self,
        prompt: InvestigatorPrompt,
        *,
        previous_response_id: str | None = None,
        tool_outputs: list[ToolOutput] | None = None,
        allow_tools: bool = True,
    ) -> InvestigatorTurn: ...


class OpenAIInvestigatorClient:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        max_retries: int = 2,
        reasoning_effort: Literal["medium"] = "medium",
    ):
        from openai import OpenAI

        self.model = model
        self.max_retries = max_retries
        self.reasoning_effort = reasoning_effort
        self._client = OpenAI(api_key=api_key, max_retries=max_retries)

    def respond(
        self,
        prompt: InvestigatorPrompt,
        *,
        previous_response_id: str | None = None,
        tool_outputs: list[ToolOutput] | None = None,
        allow_tools: bool = True,
    ) -> InvestigatorTurn:
        if previous_response_id is None:
            request_input: Any = prompt.user
        else:
            request_input = [
                {
                    "type": "function_call_output",
                    "call_id": item.call_id,
                    "output": json.dumps(item.output, sort_keys=True),
                }
                for item in (tool_outputs or [])
            ]
            if not allow_tools:
                request_input.append(
                    {
                        "role": "user",
                        "content": (
                            "The tool-call limit has been reached. Return the best-supported final "
                            "diagnosis now, using INCONCLUSIVE if the evidence is insufficient."
                        ),
                    }
                )

        request: dict[str, Any] = {
            "model": self.model,
            "instructions": prompt.system,
            "input": request_input,
            "previous_response_id": previous_response_id,
            "tools": prompt.tools if allow_tools else [],
            "tool_choice": (
                "required"
                if allow_tools and previous_response_id is None
                else ("auto" if allow_tools else "none")
            ),
            "parallel_tool_calls": False,
            "reasoning": {"effort": self.reasoning_effort},
        }
        if previous_response_id is not None:
            request["text_format"] = FinalDiagnosis
        response = self._client.responses.parse(
            **request,
        )
        tool_calls: list[RequestedToolCall] = []
        for item in response.output:
            if item.type != "function_call":
                continue
            parsed_arguments = getattr(item, "parsed_arguments", None)
            arguments = (
                parsed_arguments
                if isinstance(parsed_arguments, dict)
                else json.loads(item.arguments)
            )
            if not isinstance(arguments, dict):
                raise ValueError(f"Tool arguments for {item.name} were not a JSON object")
            tool_calls.append(
                RequestedToolCall(
                    call_id=item.call_id,
                    name=item.name,
                    arguments=arguments,
                )
            )
        usage = response.usage.model_dump(mode="json") if response.usage else {}
        decision_summary = (
            response.output_text.strip() if tool_calls and response.output_text else None
        )
        return InvestigatorTurn(
            response_id=response.id,
            diagnosis=response.output_parsed,
            tool_calls=tool_calls,
            decision_summary=decision_summary,
            usage=usage,
        )
