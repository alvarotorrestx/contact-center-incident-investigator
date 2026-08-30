from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Protocol

from .models import VerificationResult
from .prompting import VerifierPrompt


@dataclass(frozen=True)
class VerifierResponse:
    result: VerificationResult
    response_id: str
    usage: dict[str, Any]


class VerifierClient(Protocol):
    model: str
    reasoning_effort: str

    def verify(self, prompt: VerifierPrompt) -> VerifierResponse: ...


class OpenAIVerifierClient:
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

    def verify(self, prompt: VerifierPrompt) -> VerifierResponse:
        response = self._client.responses.parse(
            model=self.model,
            instructions=prompt.system,
            input=prompt.user,
            tools=[],
            tool_choice="none",
            parallel_tool_calls=False,
            reasoning={"effort": self.reasoning_effort},
            text_format=VerificationResult,
        )
        if response.output_parsed is None:
            raise ValueError("Verifier returned no structured result")
        usage = response.usage.model_dump(mode="json") if response.usage else {}
        return VerifierResponse(
            result=response.output_parsed,
            response_id=response.id,
            usage=usage,
        )
