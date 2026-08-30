from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

import pandas as pd
from openai import pydantic_function_tool
from pydantic import BaseModel, ConfigDict, Field

from incident_investigator.contracts import VisibleCase

TOOL_VERSION = "v1_tools_1"
TimeWindow = Literal["full", "pre_incident", "incident_and_after"]
ComparisonWindow = Literal["pre_vs_post_incident", "first_half_vs_second_half"]
MetricName = Literal[
    "offered_calls",
    "answered_calls",
    "abandoned_calls",
    "service_level_pct",
    "asa_seconds",
    "aht_seconds",
    "transfer_rate_pct",
    "scheduled_agents",
    "logged_in_agents",
    "productive_agents",
    "adherence_pct",
    "occupancy_pct",
    "agents_in_training",
]


class ToolArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")


class NoArguments(ToolArguments):
    pass


class QueueArguments(ToolArguments):
    queue_name: str = Field(min_length=1)


class EventArguments(ToolArguments):
    time_window: TimeWindow = "full"
    scope: str | None = None


class MetricChangeArguments(ToolArguments):
    metric: MetricName
    time_window: ComparisonWindow = "pre_vs_post_incident"


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    arguments_model: type[ToolArguments]
    handler_name: str

    def api_schema(self) -> dict[str, Any]:
        wrapped = pydantic_function_tool(
            self.arguments_model,
            name=self.name,
            description=self.description,
        )
        function = wrapped["function"]
        return {
            "type": "function",
            "name": function["name"],
            "description": function.get("description"),
            "parameters": function["parameters"],
            "strict": function["strict"],
        }


TOOL_DEFINITIONS = (
    ToolDefinition(
        "summarize_incident_window",
        "Summarize visible source coverage, time ranges, queues, events, and key pre/post metrics.",
        NoArguments,
        "summarize_incident_window",
    ),
    ToolDefinition(
        "get_performance_trends",
        "Return center performance intervals and deterministic pre/post incident metric summaries.",
        NoArguments,
        "get_performance_trends",
    ),
    ToolDefinition(
        "compare_actual_vs_forecast",
        "Compare actual volume and AHT with forecast by interval and before/after the incident.",
        NoArguments,
        "compare_actual_vs_forecast",
    ),
    ToolDefinition(
        "analyze_staffing",
        "Return staffing intervals, capacity gaps, and deterministic pre/post summaries.",
        NoArguments,
        "analyze_staffing",
    ),
    ToolDefinition(
        "analyze_queue",
        "Analyze one validated queue with interval detail and pre/post metric summaries.",
        QueueArguments,
        "analyze_queue",
    ),
    ToolDefinition(
        "compare_queues",
        "Compare pre/post performance and staffing across every visible queue.",
        NoArguments,
        "compare_queues",
    ),
    ToolDefinition(
        "get_events",
        "Return visible operational events, optionally filtered by incident-relative window "
        "and scope.",
        EventArguments,
        "get_events",
    ),
    ToolDefinition(
        "calculate_metric_change",
        "Calculate a validated center metric change across the incident boundary or window halves.",
        MetricChangeArguments,
        "calculate_metric_change",
    ),
    ToolDefinition(
        "recalculate_service_level",
        "Recalculate service level from visible counts and compare it with every reported "
        "interval.",
        NoArguments,
        "recalculate_service_level",
    ),
)


def _number(value: Any) -> float | int | None:
    if value is None or pd.isna(value):
        return None
    numeric = float(value)
    if numeric.is_integer():
        return int(numeric)
    return round(numeric, 4)


def _record(frame: pd.DataFrame, columns: list[str]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for row in frame[columns].to_dict(orient="records"):
        records.append(
            {
                key: value.isoformat() if isinstance(value, pd.Timestamp) else _number(value)
                for key, value in row.items()
            }
        )
    return records


def _metric_summary(
    frame: pd.DataFrame,
    metrics: list[str],
    incident_start: pd.Timestamp,
) -> dict[str, dict[str, float | int | None]]:
    before = frame.loc[frame["timestamp"] < incident_start]
    after = frame.loc[frame["timestamp"] >= incident_start]
    result: dict[str, dict[str, float | int | None]] = {}
    for metric in metrics:
        before_mean = float(before[metric].mean()) if not before.empty else None
        after_mean = float(after[metric].mean()) if not after.empty else None
        change = (
            after_mean - before_mean if before_mean is not None and after_mean is not None else None
        )
        percent_change = (
            change / before_mean * 100
            if change is not None and before_mean not in (None, 0)
            else None
        )
        result[metric] = {
            "pre_incident_mean": _number(before_mean),
            "incident_and_after_mean": _number(after_mean),
            "absolute_change": _number(change),
            "percent_change": _number(percent_change),
            "window_min": _number(frame[metric].min()),
            "window_max": _number(frame[metric].max()),
        }
    return result


class CaseToolbox:
    """Deterministic read-only analysis over one already-loaded visible case."""

    def __init__(self, case: VisibleCase):
        self.case = case
        self.incident_start = pd.Timestamp(case.incident_metadata["incident_start"])
        self._definitions = {definition.name: definition for definition in TOOL_DEFINITIONS}

    @property
    def schemas(self) -> list[dict[str, Any]]:
        return [definition.api_schema() for definition in TOOL_DEFINITIONS]

    @property
    def queue_names(self) -> list[str]:
        return sorted({str(row["queue_name"]) for row in self.case.queue_performance})

    def execute(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        definition = self._definitions.get(name)
        if definition is None:
            raise ValueError(f"Unknown tool: {name}")
        parsed = definition.arguments_model.model_validate(arguments)
        handler: Callable[..., dict[str, Any]] = getattr(self, definition.handler_name)
        return handler(**parsed.model_dump())

    @staticmethod
    def _frame(rows: list[dict[str, Any]]) -> pd.DataFrame:
        frame = pd.DataFrame(rows).copy()
        frame["timestamp"] = pd.to_datetime(frame["timestamp"], errors="raise")
        return frame.sort_values("timestamp", kind="stable").reset_index(drop=True)

    def summarize_incident_window(self) -> dict[str, Any]:
        performance = self._frame(self.case.performance)
        key_metrics = ["service_level_pct", "asa_seconds", "aht_seconds", "offered_calls"]
        return {
            "incident_id": self.case.incident_id,
            "incident_metadata": dict(self.case.incident_metadata),
            "visible_sources": {
                "performance_intervals": len(self.case.performance),
                "staffing_intervals": len(self.case.staffing),
                "forecast_intervals": len(self.case.forecast),
                "queue_intervals": len(self.case.queue_performance),
                "event_count": len(self.case.events),
            },
            "available_queues": self.queue_names,
            "time_range": {
                "first_interval": performance["timestamp"].min().isoformat(),
                "last_interval": performance["timestamp"].max().isoformat(),
                "incident_start": self.incident_start.isoformat(),
            },
            "key_performance_summary": _metric_summary(
                performance, key_metrics, self.incident_start
            ),
        }

    def get_performance_trends(self) -> dict[str, Any]:
        frame = self._frame(self.case.performance)
        metrics = [
            "offered_calls",
            "answered_calls",
            "abandoned_calls",
            "service_level_pct",
            "asa_seconds",
            "aht_seconds",
            "transfer_rate_pct",
        ]
        return {
            "incident_start": self.incident_start.isoformat(),
            "summary": _metric_summary(frame, metrics, self.incident_start),
            "intervals": _record(frame, ["timestamp", *metrics]),
        }

    def compare_actual_vs_forecast(self) -> dict[str, Any]:
        performance = self._frame(self.case.performance)
        forecast = self._frame(self.case.forecast)
        frame = performance[["timestamp", "offered_calls", "aht_seconds"]].merge(
            forecast,
            on="timestamp",
            how="inner",
            validate="one_to_one",
        )
        frame["offered_variance"] = frame["offered_calls"] - frame["forecast_offered_calls"]
        frame["offered_variance_pct"] = (
            frame["offered_variance"] / frame["forecast_offered_calls"] * 100
        )
        frame["aht_variance_seconds"] = frame["aht_seconds"] - frame["forecast_aht_seconds"]
        frame["aht_variance_pct"] = (
            frame["aht_variance_seconds"] / frame["forecast_aht_seconds"] * 100
        )
        metrics = [
            "offered_variance",
            "offered_variance_pct",
            "aht_variance_seconds",
            "aht_variance_pct",
        ]
        return {
            "incident_start": self.incident_start.isoformat(),
            "summary": _metric_summary(frame, metrics, self.incident_start),
            "intervals": _record(
                frame,
                [
                    "timestamp",
                    "offered_calls",
                    "forecast_offered_calls",
                    "offered_variance",
                    "offered_variance_pct",
                    "aht_seconds",
                    "forecast_aht_seconds",
                    "aht_variance_seconds",
                    "aht_variance_pct",
                    "required_agents",
                ],
            ),
        }

    def analyze_staffing(self) -> dict[str, Any]:
        frame = self._frame(self.case.staffing)
        frame["scheduled_to_logged_gap"] = frame["scheduled_agents"] - frame["logged_in_agents"]
        frame["logged_to_productive_gap"] = frame["logged_in_agents"] - frame["productive_agents"]
        metrics = [
            "scheduled_agents",
            "logged_in_agents",
            "productive_agents",
            "scheduled_to_logged_gap",
            "logged_to_productive_gap",
            "adherence_pct",
            "occupancy_pct",
            "agents_in_training",
        ]
        return {
            "incident_start": self.incident_start.isoformat(),
            "summary": _metric_summary(frame, metrics, self.incident_start),
            "intervals": _record(frame, ["timestamp", *metrics]),
        }

    def analyze_queue(self, queue_name: str) -> dict[str, Any]:
        if queue_name not in self.queue_names:
            raise ValueError(
                f"Unknown queue {queue_name!r}; expected one of {', '.join(self.queue_names)}"
            )
        frame = self._frame(self.case.queue_performance)
        frame = frame.loc[frame["queue_name"] == queue_name].reset_index(drop=True)
        metrics = [
            "offered_calls",
            "answered_calls",
            "service_level_pct",
            "asa_seconds",
            "aht_seconds",
            "transfer_rate_pct",
            "staffed_agents",
        ]
        return {
            "queue_name": queue_name,
            "incident_start": self.incident_start.isoformat(),
            "summary": _metric_summary(frame, metrics, self.incident_start),
            "intervals": _record(frame, ["timestamp", *metrics]),
        }

    def compare_queues(self) -> dict[str, Any]:
        frame = self._frame(self.case.queue_performance)
        metrics = [
            "offered_calls",
            "service_level_pct",
            "asa_seconds",
            "aht_seconds",
            "transfer_rate_pct",
            "staffed_agents",
        ]
        comparisons = []
        for queue_name in self.queue_names:
            queue = frame.loc[frame["queue_name"] == queue_name]
            comparisons.append(
                {
                    "queue_name": queue_name,
                    "metrics": _metric_summary(queue, metrics, self.incident_start),
                }
            )
        comparisons.sort(
            key=lambda item: (
                item["metrics"]["service_level_pct"]["incident_and_after_mean"],
                item["queue_name"],
            )
        )
        return {
            "incident_start": self.incident_start.isoformat(),
            "queues_ranked_by_post_incident_service_level_ascending": comparisons,
        }

    def get_events(
        self, time_window: TimeWindow = "full", scope: str | None = None
    ) -> dict[str, Any]:
        events = sorted(self.case.events, key=lambda event: str(event["timestamp"]))
        available_scopes = sorted({str(event["scope"]) for event in events})
        if scope is not None:
            matched_scope = next(
                (
                    candidate
                    for candidate in available_scopes
                    if candidate.casefold() == scope.casefold()
                ),
                None,
            )
            if matched_scope is None:
                raise ValueError(
                    f"Unknown event scope {scope!r}; expected one of {', '.join(available_scopes)}"
                )
            events = [event for event in events if str(event["scope"]) == matched_scope]
        if time_window != "full":
            events = [
                event
                for event in events
                if (pd.Timestamp(event["timestamp"]) < self.incident_start)
                == (time_window == "pre_incident")
            ]
        return {
            "time_window": time_window,
            "scope": scope,
            "available_scopes": available_scopes,
            "events": events,
        }

    def calculate_metric_change(
        self,
        metric: MetricName,
        time_window: ComparisonWindow = "pre_vs_post_incident",
    ) -> dict[str, Any]:
        performance_metrics = set(self.case.performance[0])
        staffing_metrics = set(self.case.staffing[0])
        if metric in performance_metrics:
            source = "performance"
            frame = self._frame(self.case.performance)
        elif metric in staffing_metrics:
            source = "staffing"
            frame = self._frame(self.case.staffing)
        else:
            raise ValueError(f"Metric {metric!r} is not available for center-level change analysis")
        if time_window == "pre_vs_post_incident":
            first = frame.loc[frame["timestamp"] < self.incident_start]
            second = frame.loc[frame["timestamp"] >= self.incident_start]
            first_label, second_label = "pre_incident", "incident_and_after"
        else:
            midpoint = len(frame) // 2
            first, second = frame.iloc[:midpoint], frame.iloc[midpoint:]
            first_label, second_label = "first_half", "second_half"
        first_mean = float(first[metric].mean())
        second_mean = float(second[metric].mean())
        absolute_change = second_mean - first_mean
        return {
            "source": source,
            "metric": metric,
            "comparison": time_window,
            f"{first_label}_mean": _number(first_mean),
            f"{second_label}_mean": _number(second_mean),
            "absolute_change": _number(absolute_change),
            "percent_change": _number(absolute_change / first_mean * 100 if first_mean else None),
            "first_period_intervals": len(first),
            "second_period_intervals": len(second),
        }

    def recalculate_service_level(self) -> dict[str, Any]:
        frame = self._frame(self.case.performance)
        denominator = frame["offered_calls"] - frame["short_abandoned_calls"]
        frame["recalculated_service_level_pct"] = (
            frame["answered_within_threshold"] / denominator.where(denominator != 0) * 100
        )
        frame["difference_pct_points"] = (
            frame["service_level_pct"] - frame["recalculated_service_level_pct"]
        )
        columns = [
            "timestamp",
            "offered_calls",
            "short_abandoned_calls",
            "answered_within_threshold",
            "service_level_pct",
            "recalculated_service_level_pct",
            "difference_pct_points",
        ]
        return {
            "formula": (
                "answered_within_threshold / (offered_calls - short_abandoned_calls) * 100"
            ),
            "zero_denominator_intervals": int((denominator == 0).sum()),
            "mismatch_intervals_over_0_01_points": int(
                (frame["difference_pct_points"].abs() > 0.01).sum()
            ),
            "maximum_absolute_difference_pct_points": _number(
                frame["difference_pct_points"].abs().max()
            ),
            "intervals": _record(frame, columns),
        }
