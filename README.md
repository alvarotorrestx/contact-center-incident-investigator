# Contact Center Incident Investigator

Stage 0 provides a deterministic ten-case synthetic benchmark, evaluator-isolated ground truth,
deterministic scoring, a fair tool-free OpenAI baseline, artifact persistence, a minimal FastAPI
API, and a React/Vite smoke interface.

The benchmark is intentionally frozen at `benchmark/v1`. Do not change cases after observing model
predictions to improve a score. Genuine benchmark defects require documentation and a new version.

## Local setup

Python 3.12 is preferred; compatible Python 3.11+ is supported. From the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.lock
.\.venv\Scripts\python.exe -m pip install -e backend
corepack pnpm --dir frontend install --frozen-lockfile
```

Generate and validate the frozen benchmark:

```powershell
.\.venv\Scripts\python.exe -m incident_investigator --project-root . generate
.\.venv\Scripts\python.exe -m incident_investigator --project-root . validate
```

Run backend and frontend tests:

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests
corepack pnpm --dir frontend test
corepack pnpm --dir frontend lint
corepack pnpm --dir frontend build
```

## Live ten-case baseline

The baseline requires an OpenAI model that supports structured Responses output. It runs every
frozen case with the same model configuration and preserves all valid outputs and failures.

```powershell
$env:OPENAI_API_KEY = "your-key"
$env:OPENAI_MODEL = "your-model-name"
.\.venv\Scripts\python.exe -m incident_investigator --project-root . run-baseline
```

Local outputs are written beneath `results/local/<run-id>` and trajectories beneath
`trajectories/local/<run-id>`. They are ignored until intentionally curated.

## Local API and UI

```powershell
.\.venv\Scripts\python.exe -m incident_investigator --project-root . serve
corepack pnpm --dir frontend dev
```

Stage 0 exposes only the `baseline` system version. Tool use, a hypothesis ledger, verification,
revision loops, and the polished product UI require separate phase approval.

