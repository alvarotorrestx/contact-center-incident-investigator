from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd

from incident_investigator.contracts import IncidentSummary, VisibleCase

INCIDENT_ID_PATTERN = re.compile(r"^CC-\d{3}$")
VISIBLE_JSON_FILES = ("incident_metadata.json", "events.json")
VISIBLE_CSV_FILES = (
    "performance.csv",
    "staffing.csv",
    "forecast.csv",
    "queue_performance.csv",
)


class AgentVisibleCaseLoader:
    """Loads only case data explicitly intended for an agent or API consumer."""

    def __init__(self, cases_root: Path):
        self.cases_root = cases_root.resolve()

    def _case_dir(self, incident_id: str) -> Path:
        if not INCIDENT_ID_PATTERN.fullmatch(incident_id):
            raise ValueError(f"Invalid incident id: {incident_id!r}")
        case_dir = (self.cases_root / incident_id).resolve()
        if case_dir.parent != self.cases_root:
            raise ValueError("Incident path escapes the agent-visible cases root")
        if not case_dir.is_dir():
            raise FileNotFoundError(f"Unknown incident: {incident_id}")
        return case_dir

    @staticmethod
    def _read_json(path: Path) -> object:
        with path.open(encoding="utf-8") as handle:
            return json.load(handle)

    @staticmethod
    def _read_csv(path: Path) -> list[dict[str, object]]:
        frame = pd.read_csv(path)
        return json.loads(frame.to_json(orient="records"))

    def list_incidents(self) -> list[IncidentSummary]:
        summaries: list[IncidentSummary] = []
        if not self.cases_root.exists():
            return summaries
        for case_dir in sorted(path for path in self.cases_root.iterdir() if path.is_dir()):
            if not INCIDENT_ID_PATTERN.fullmatch(case_dir.name):
                continue
            metadata = self._read_json(case_dir / "incident_metadata.json")
            summaries.append(IncidentSummary.model_validate(metadata))
        return summaries

    def load(self, incident_id: str) -> VisibleCase:
        case_dir = self._case_dir(incident_id)
        metadata = self._read_json(case_dir / "incident_metadata.json")
        events = self._read_json(case_dir / "events.json")
        if not isinstance(metadata, dict) or not isinstance(events, list):
            raise ValueError(f"Malformed JSON in visible case {incident_id}")
        return VisibleCase(
            incident_metadata=metadata,
            performance=self._read_csv(case_dir / "performance.csv"),
            staffing=self._read_csv(case_dir / "staffing.csv"),
            forecast=self._read_csv(case_dir / "forecast.csv"),
            queue_performance=self._read_csv(case_dir / "queue_performance.csv"),
            events=events,
        )
