from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import platform
import sys
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from incident_investigator.contracts import FinalDiagnosis


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _package_version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def _file_hash(path: Path) -> str | None:
    if not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def runtime_metadata(project_root: Path) -> dict[str, Any]:
    return {
        "python_version": platform.python_version(),
        "python_executable": sys.executable,
        "platform": platform.platform(),
        "packages": {
            name: _package_version(name)
            for name in ["fastapi", "pydantic", "pandas", "numpy", "openai"]
        },
        "dependency_lock_sha256": _file_hash(project_root / "backend" / "requirements.lock"),
    }


def _atomic_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
        os.replace(temporary_name, path)
    except Exception:
        Path(temporary_name).unlink(missing_ok=True)
        raise


class RunStore:
    def __init__(self, project_root: Path, run_id: str | None = None):
        self.project_root = project_root.resolve()
        self.run_id = run_id or str(uuid.uuid4())
        self.result_root = self.project_root / "results" / "local" / self.run_id
        self.trajectory_root = self.project_root / "trajectories" / "local" / self.run_id

    @property
    def manifest_path(self) -> Path:
        return self.result_root / "manifest.json"

    def create_manifest(self, values: dict[str, Any]) -> dict[str, Any]:
        manifest = {
            "run_id": self.run_id,
            "created_at": utc_now(),
            "status": "RUNNING",
            "runtime": runtime_metadata(self.project_root),
            **values,
        }
        self.write_json(self.manifest_path, manifest)
        return manifest

    def update_manifest(self, **values: Any) -> dict[str, Any]:
        manifest = self.read_json(self.manifest_path)
        manifest.update(values)
        self.write_json(self.manifest_path, manifest)
        return manifest

    @staticmethod
    def write_json(path: Path, value: object) -> None:
        _atomic_text(path, json.dumps(value, indent=2, sort_keys=True, default=str) + "\n")

    @staticmethod
    def write_text(path: Path, value: str) -> None:
        _atomic_text(path, value)

    @staticmethod
    def read_json(path: Path) -> dict[str, Any]:
        with path.open(encoding="utf-8") as handle:
            value = json.load(handle)
        if not isinstance(value, dict):
            raise ValueError(f"Expected JSON object in {path}")
        return value

    def write_prediction(self, prediction: FinalDiagnosis) -> Path:
        path = self.result_root / "predictions" / f"{prediction.incident_id}.json"
        self.write_json(path, prediction.model_dump(mode="json"))
        return path

    def write_error(self, incident_id: str, error: Exception) -> Path:
        path = self.result_root / "errors" / f"{incident_id}.json"
        self.write_json(
            path,
            {"incident_id": incident_id, "error_type": type(error).__name__, "message": str(error)},
        )
        return path

    def append_trajectory(self, incident_id: str, event: dict[str, Any]) -> Path:
        path = self.trajectory_root / f"{incident_id}.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"timestamp": utc_now(), **event}
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(payload, sort_keys=True, default=str) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        return path
