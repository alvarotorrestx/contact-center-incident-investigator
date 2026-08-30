from __future__ import annotations

import argparse
import json
from pathlib import Path


def _project_root(value: str) -> Path:
    return Path(value).resolve()


def _evaluate_run(project_root: Path, run_id: str) -> dict[str, object]:
    from incident_investigator.config import get_settings
    from incident_investigator.evaluation import GroundTruthLoader, score_benchmark
    from incident_investigator.persistence import RunStore

    settings = get_settings(project_root)
    store = RunStore(project_root, run_id=run_id)
    predictions = {}
    for truth in GroundTruthLoader(settings.ground_truth_root).load_all():
        path = store.result_root / "predictions" / f"{truth.incident_id}.json"
        predictions[truth.incident_id] = (
            json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None
        )
    scores = score_benchmark(
        predictions,
        GroundTruthLoader(settings.ground_truth_root).load_all(),
    )
    store.write_json(store.result_root / "scores.json", scores.model_dump(mode="json"))
    store.write_text(store.result_root / "comparison.csv", scores.to_csv())
    store.write_text(store.result_root / "scores.md", scores.to_markdown())
    return scores.model_dump(mode="json")


def main() -> None:
    parser = argparse.ArgumentParser(description="Contact-center incident benchmark commands")
    parser.add_argument("--project-root", default=".", type=_project_root)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("generate", help="Generate and freeze benchmark v1")
    subparsers.add_parser("validate", help="Validate benchmark v1")
    subparsers.add_parser("run-baseline", help="Run the live OpenAI baseline on all cases")
    evaluate = subparsers.add_parser("evaluate", help="Score saved predictions")
    evaluate.add_argument("--run-id", required=True)
    serve = subparsers.add_parser("serve", help="Run the local FastAPI server")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", default=8000, type=int)
    args = parser.parse_args()
    project_root: Path = args.project_root

    if args.command == "generate":
        from incident_investigator.benchmark.generator import generate_benchmark

        print(json.dumps(generate_benchmark(project_root), indent=2))
    elif args.command == "validate":
        from incident_investigator.benchmark.validation import validate_benchmark

        print(json.dumps({"valid_cases": validate_benchmark(project_root)}, indent=2))
    elif args.command == "run-baseline":
        from incident_investigator.baseline.batch import run_live_baseline
        from incident_investigator.config import get_settings

        run_id, scores = run_live_baseline(get_settings(project_root))
        print(json.dumps({"run_id": run_id, "scores": scores}, indent=2))
    elif args.command == "evaluate":
        print(json.dumps(_evaluate_run(project_root, args.run_id), indent=2))
    elif args.command == "serve":
        import uvicorn

        uvicorn.run("incident_investigator.api:app", host=args.host, port=args.port)


if __name__ == "__main__":
    main()
