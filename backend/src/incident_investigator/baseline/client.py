from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from incident_investigator.contracts import FinalDiagnosis

from .prompting import BaselinePrompt


@dataclass
class BaselineResponse:
    diagnosis: FinalDiagnosis
    usage: dict[str, Any]
    response_id: str | None = None


class BaselineClient(Protocol):
    model: str

    def analyze(self, prompt: BaselinePrompt) -> BaselineResponse: ...


class OpenAIBaselineClient:
    def __init__(self, *, api_key: str, model: str, max_retries: int = 2):
        from openai import OpenAI

        self.model = model
        self.max_retries = max_retries
        self._client = OpenAI(api_key=api_key, max_retries=max_retries)

    def analyze(self, prompt: BaselinePrompt) -> BaselineResponse:
        response = self._client.responses.parse(
            model=self.model,
            input=[
                {"role": "system", "content": prompt.system},
                {"role": "user", "content": prompt.user},
            ],
            text_format=FinalDiagnosis,
        )
        if response.output_parsed is None:
            raise ValueError("OpenAI response did not contain a parsed diagnosis")
        usage = response.usage.model_dump(mode="json") if response.usage else {}
        return BaselineResponse(
            diagnosis=response.output_parsed,
            usage=usage,
            response_id=response.id,
        )
