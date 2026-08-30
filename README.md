# Contact Center Incident Investigator

Stage 0 provides a deterministic ten-case synthetic benchmark, evaluator-isolated ground truth,
deterministic scoring, a fair tool-free OpenAI baseline, artifact persistence, a minimal FastAPI
API, and a React/Vite smoke interface.

The benchmark is intentionally frozen at `benchmark/v1`. Do not change cases after observing model
predictions to improve a score. Genuine benchmark defects require documentation and a new version.

Stage 0 reports expected-evidence coverage and a non-allowlisted evidence rate. The latter counts
predicted structured evidence IDs absent from each case's non-exhaustive `supported_signal_ids`
allowlist; it is not a hallucination or factual-error rate.

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
$env:OPENAI_MODEL = "gpt-5.6-sol"
.\.venv\Scripts\python.exe -m incident_investigator --project-root . run-baseline
```

The CLI also loads both variables automatically from the project-root `.env`. Future controlled
baseline requests explicitly use medium reasoning effort and record it in the run manifest.

Local outputs are written beneath `results/local/<run-id>` and trajectories beneath
`trajectories/local/<run-id>`. They are ignored until intentionally curated.

## V1 tool-using investigator

V1 uses the same frozen benchmark, `gpt-5.6-sol`, medium reasoning, taxonomy, and final schema as
the pinned Stage 0 anchor. It exposes the same agent-visible incident information through bounded,
deterministic read-only tools instead of embedding every raw table in the initial prompt.

```powershell
.\.venv\Scripts\python.exe -m incident_investigator --project-root . run-v1
```

The run writes normal scores plus `comparison_to_anchor.json`, CSV, and Markdown reports against
anchor run `02b97b0d-d68e-45f8-b678-386f7558dd02`. V1 allows at most 10 tool calls per case and
does not include a hypothesis ledger, verifier, or revision loop.

The completed V1 run is `7fcf7453-609e-4006-8a72-cd1a6b26bcff`. It produced ten valid outputs and
zero execution failures but scored 5/10 RCIA versus the 9/10 pinned baseline. Its complete evidence
is curated under `results/curated/` and `trajectories/curated/`. The deterministic tools and
trajectory infrastructure are retained; the current investigator policy is not promoted as the
default system.

## V2 structured-hypothesis investigator

V2 keeps the V1 tools and adds a typed hypothesis ledger, evidence-for/evidence-against tracking,
competing-explanation evaluation, and application-enforced completion criteria. It uses the same
frozen benchmark, model, medium reasoning, taxonomy, final schema, and deterministic scorer.

```powershell
.\.venv\Scripts\python.exe -m incident_investigator --project-root . run-v2
```

The official V2 run is `d3859d8d-b252-426a-970e-89a471a5fe7c`: ten valid outputs, zero failures,
7/10 RCIA, and 34/40 expected-evidence coverage. It improved materially over V1's tool-use result
but remained below the 9/10 Stage 0 anchor and cost substantially more. Complete evidence is curated
under `results/curated/` and `trajectories/curated/`. V2 does not include a verifier or revision
loop.

## Local API and UI

```powershell
.\.venv\Scripts\python.exe -m incident_investigator --project-root . serve
corepack pnpm --dir frontend dev
```

The existing API still exposes only the Stage 0 `baseline` system version. V1/V2 experiments run
through the CLI; verifier behavior, revision loops, and polished product UI require separate phase
approval.
