from __future__ import annotations

from pathlib import Path

import pytest

from incident_investigator.benchmark.generator import generate_benchmark
from incident_investigator.benchmark.validation import (
    BenchmarkValidationError,
    validate_benchmark,
)


def test_generation_is_reproducible_and_valid(project_root: Path, tmp_path: Path) -> None:
    first_root = tmp_path / "first"
    second_root = tmp_path / "second"
    first = generate_benchmark(project_root, output_root=first_root)
    second = generate_benchmark(project_root, output_root=second_root)

    assert first["file_hashes"] == second["file_hashes"]
    assert first["case_ids"] == [
        "CC-001",
        "CC-002",
        "CC-003",
        "CC-004",
        "CC-005",
        "CC-007",
        "CC-009",
        "CC-012",
        "CC-014",
        "CC-015",
    ]
    assert validate_benchmark(project_root, first_root) == first["case_ids"]
    assert validate_benchmark(project_root, second_root) == second["case_ids"]

    tampered = first_root / "cases" / "CC-001" / "events.json"
    tampered.write_text("[]\n ", encoding="utf-8")
    with pytest.raises(BenchmarkValidationError, match="Manifest checksum mismatch"):
        validate_benchmark(project_root, first_root)
