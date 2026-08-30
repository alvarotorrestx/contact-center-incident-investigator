from __future__ import annotations

import json
from typing import Literal, Protocol

from incident_investigator.contracts import FinalDiagnosis
from incident_investigator.investigator.client import (
    InvestigatorTurn,
    RequestedToolCall,
    ToolOutput,
)

from .prompting import V2Prompt

V2TurnMode = Literal["initialize_ledger", "update_ledger", "investigate", "force_final"]


class V2InvestigatorClient(Protocol):
    model: str
    reasoning_effort: str

    def respond(
        self,
        prompt: V2Prompt,
        *,
        mode: V2TurnMode,
        previous_response_id: str | None = None,
        tool_outputs: list[ToolOutput] | None = None,
        instruction: str | None = None,
    ) -> InvestigatorTurn: ...


class OpenAIV2InvestigatorClient:
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
        prompt: V2Prompt,
        *,
        mode: V2TurnMode,
        previous_response_id: str | None = None,
        tool_outputs: list[ToolOutput] | None = None,
        instruction: str | None = None,
    ) -> InvestigatorTurn:
        if previous_response_id is None:
            request_input: object = prompt.user
        else:
            items: list[dict[str, str]] = [
                {
                    "type": "function_call_output",
                    "call_id": item.call_id,
                    "output": json.dumps(item.output, sort_keys=True),
                }
                for item in (tool_outputs or [])
            ]
            if instruction:
                items.append({"role": "user", "content": instruction})
            request_input = items

        if mode in {"initialize_ledger", "update_ledger"}:
            tools = [prompt.ledger_tool]
            tool_choice = "required"
        elif mode == "investigate":
            tools = prompt.operational_tools
            tool_choice = "auto"
        else:
            tools = []
            tool_choice = "none"

        request: dict[str, object] = {
            "model": self.model,
            "instructions": prompt.system,
            "input": request_input,
            "previous_response_id": previous_response_id,
            "tools": tools,
            "tool_choice": tool_choice,
            "parallel_tool_calls": False,
            "reasoning": {"effort": self.reasoning_effort},
        }
        if mode in {"investigate", "force_final"}:
            request["text_format"] = FinalDiagnosis
        response = self._client.responses.parse(**request)

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
