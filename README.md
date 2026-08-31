# Contact Center Incident Investigator

Built by Alvaro Torres for the micro1 Frontier Engineering Challenge 2026

**Demo video:** [Watch the project walkthrough](https://www.youtube.com/watch?v=RNXo3g1WeTI)

The project now includes a polished React/FastAPI investigation experience over a deterministic
ten-case synthetic benchmark. The product presents incident impact, a structured diagnosis,
supporting evidence, causal reasoning, queue and capacity context, rejected alternatives,
recommended actions, a stakeholder brief, and a concise public investigation history.

The measured default remains the Stage 0 complete-context single-stage analyst. The preserved V2
tool and hypothesis-ledger workflow is available as an optional deep-investigation view for richer
drill-down and auditability; it is not presented as a higher-accuracy tier. V3 verification and
adaptive escalation remain removed experiments rather than active product modes.

The benchmark is intentionally frozen at `benchmark/v1`. Do not change cases after observing model
predictions to improve a score. Genuine benchmark defects require documentation and a new version.

Reasoning experiments and V4 product/UI work are complete. The repository is submission-ready; no
further reasoning experiment is planned or authorized.

Stage 0 reports expected-evidence coverage and a non-allowlisted evidence rate. The latter counts
predicted structured evidence IDs absent from each case's non-exhaustive `supported_signal_ids`
allowlist; it is not a hallucination or factual-error rate.

## Local setup

Python 3.12 is preferred; compatible Python 3.11+ is supported. The frontend requires Node.js
`^20.19.0` or `>=22.12.0`, Corepack, and the repository-pinned pnpm 11.19.0. From the repository
root:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.lock
.\.venv\Scripts\python.exe -m pip install -e backend
corepack enable
Push-Location frontend
corepack pnpm install --frozen-lockfile
Pop-Location
```

Generate and validate the frozen benchmark:

```powershell
.\.venv\Scripts\python.exe -m incident_investigator --project-root . generate
.\.venv\Scripts\python.exe -m incident_investigator --project-root . validate
```

Run backend and frontend tests:

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests
Push-Location frontend
corepack pnpm test
corepack pnpm lint
corepack pnpm build
Pop-Location
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

Score a saved run deterministically against benchmark v1 ground truth:

```powershell
.\.venv\Scripts\python.exe -m incident_investigator --project-root . evaluate --run-id <run-id>
```

The evaluator writes `scores.json`, `scores.md`, and `comparison.csv` into the saved run's
`results/local/<run-id>/` directory.

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
but remained below the 9/10 Stage 0 anchor. It ran for 793.080 seconds, used 1,410,169 tokens, and
cost an estimated $3.284164. Complete evidence is curated under `results/curated/` and
`trajectories/curated/`. V2 does not include a verifier or revision loop.

## V3 adversarial verification

V3 preserves the V2 investigator and adds one tool-free structured verifier. A `REVISE` result can
return findings to the investigator at most twice; the verifier cannot rewrite the diagnosis or use
ground truth, scores, historical outcomes, or filesystem tools.

```powershell
.\.venv\Scripts\python.exe -m incident_investigator --project-root . run-v3
```

Official run `5324184e-c646-456c-b58b-8e1c2e89a2fc` completed all ten cases with zero failures and
scored 7/10 RCIA, unchanged from V2. It made 13 verifier calls and 3 revisions, but no final category
changed and no V2 error was corrected. Runtime increased to 1,421.897 seconds, token use to
2,259,724, and estimated cost to $5.8938618. The complete run is curated under `results/curated/`
and `trajectories/curated/`. This controlled negative result is preserved; V3 verification is not
recommended for the final workflow without a separately approved new experiment.

## Final candidate: full context with V2 discipline

The final candidate removes V3 verification, retains the V2 tools/ledger/termination workflow, and
supplies every agent-visible incident table in the initial request, matching Stage 0 information
visibility.

```powershell
.\.venv\Scripts\python.exe -m incident_investigator --project-root . run-final-candidate
```

Official run `9730ac8f-89d6-4102-acef-528d9027d80e` completed all ten cases with zero failures and
scored 8/10 RCIA. It improved CC-007 versus V2 with no V2 RCIA regression and used 4.4 tools per
case, but remained below Stage 0's 9/10, covered 31/40 expected evidence items, used 2,462,287
tokens, ran for 850.179 seconds, and cost an estimated $4.542473. The measured recommendation is to
use the Stage 0 complete-context structured analyst as the default reasoning path while retaining
the deterministic tools, V2 ledger workflow, and trajectories as an optional deep-investigation
and audit mode. The V3 verifier remains removed.

## Adaptive escalation experiment

The final reasoning experiment kept the Stage 0 complete-context analyst as the first pass and
invoked complete-context V2 investigation only when the frozen generic deterministic gate found
uncertainty, insufficient structured support, a hard visible-data inconsistency, or a missing/late
claimed causal event.

```powershell
.\.venv\Scripts\python.exe -m incident_investigator --project-root . run-adaptive
```

Official run `678d826d-8f74-43eb-9ce9-0157ebec8587` completed all ten cases with zero failures and
scored 8/10 RCIA. It escalated only CC-012, used five tools there, changed no category, corrected no
incorrect first pass, and harmed no correct first pass. It covered 36/40 expected evidence items,
used 489,793 tokens, ran for 338.335 seconds, and cost an estimated $1.6058762. Because it remained
below the Stage 0 anchor's 9/10 while costing more, Stage 0 remains the recommended default. This
negative experiment is preserved and curated; it is not active product behavior, and no further
reasoning-architecture experiment is planned.

## Final product reasoning decision

The measured default reasoning path is the Stage 0 complete-context single-stage structured
analyst, which remained strongest at 9/10 RCIA. V2 deterministic tools and the hypothesis ledger
are retained only as an optional deep-investigation, drill-down, and audit capability. V3
verification and adaptive escalation are preserved as measured negative experiments and are not
default product behavior. No further reasoning experiments are planned or authorized. V4 product/UI
quality and presentation work is complete and did not change this measured decision.

## Representative Agent Trajectories

[`trajectories/representative/`](trajectories/representative/) contains the four selected
submission-facing trajectories covering Stage 0, V1, V2, and V3. Complete official sets remain
available under [`trajectories/curated/`](trajectories/curated/), with experimental results and
decisions documented in [`CHANGELOG.md`](CHANGELOG.md).

## Local API and UI

Start the API and UI in separate terminals from the repository root:

```powershell
.\.venv\Scripts\python.exe -m incident_investigator --project-root . serve
Set-Location frontend
corepack pnpm dev
```

Open `http://localhost:5173`. **Standard analysis** is selected by default and immediately loads the
saved, configuration-matched complete-context diagnosis for a fast and repeatable demo. **Deep
Investigation** is optional: it displays the preserved deterministic tool activity, hypothesis
ledger, and richer audit trail. It is a drill-down/auditability mode, not a higher-accuracy tier,
and it never launches a fresh V2 model run.

**Run fresh analysis** appears only in Standard mode. It posts the selected incident ID and
`system_version="baseline"` to `/api/investigations`, which loads the same complete visible incident
context and executes the existing single-stage structured analyst with medium reasoning. The new
run is persisted beneath `results/local/` and `trajectories/local/`. When it completes, the screen
keeps the selected incident and its visible operational/KPI context but replaces the displayed
diagnosis and compact two-step history with the fresh response for the current session. Switching
incidents clears that in-memory response and loads the selected incident's saved report; switching
back does not restore the earlier live response. Because this is a new model call, its category,
confidence, and findings may differ from the saved demo diagnosis.

Fresh analysis requires `OPENAI_API_KEY` and `OPENAI_MODEL=gpt-5.6-sol` in the project-root `.env`
(or process environment). Missing credentials, network failure, or unavailable model access is
shown inline while the saved report remains visible and retryable.

The V4 presentation endpoint derives KPI and queue summaries only from agent-visible case files and
combines them with curated structured diagnoses and sanitized public trajectory events. It never
returns evaluator scores, expected answers, supported-signal allowlists, expected causal chains, or
other evaluator-only fields. The benchmark, scorer, prompts, reasoning implementations, and
historical artifacts remain unchanged.
