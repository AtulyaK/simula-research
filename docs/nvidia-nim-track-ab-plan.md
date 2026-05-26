# NVIDIA NIM — Track A & Track B Operator Plan

**Status:** operator-ready on `main` (engineering closure unchanged).  
**Rate limit assumed:** **40 requests/minute** (`SIMULA_NIM_MAX_RPM=40`, ~1.5s between critic calls).

## Model & endpoint defaults (free integrate API)

| Setting | Default | Notes |
| --- | --- | --- |
| Base URL | `https://integrate.api.nvidia.com/v1/chat/completions` | NVIDIA integrate OpenAI-compatible API |
| Critic model (A & B) | `mistralai/mistral-large-3-675b-instruct-2512` | Matches NVIDIA integrate catalog; override with `SIMULA_NIM_MODEL` |
| Alt models | `meta/llama-3.1-8b-instruct`, `microsoft/phi-3-mini-128k-instruct` | Set via env if your key exposes them |
| API key | `NVIDIA_API_KEY` or `NVAPI_KEY` | `Bearer nvapi-...` in HTTP header; **never commit or paste in chat** |
| Streaming | **off** for critics | Pipeline uses `stream=false` JSON (`choices[0].message.content`); SSE not used in Stage 4 |
| Max RPM | `40` | Client-side spacing in `critic_provider_adapter.py` |

Preset **manifest `model_ids`** stay frozen (`gpt-4.1-mini` / `gpt-4.1`) for comparability; live NIM model IDs are recorded in `provider_runtime.nim_critic` only (ADR 0003 / Issue #9 discipline).

---

## Track A — Provider-backed Phase 4 (live critics)

**Goal:** A full Issue #7/#9-style validation packet with `SIMULA_CRITIC_BACKEND=nim`, separate from the signed deterministic packet `20260526T025931Z`.

### Steps

1. **Prerequisites**
   - `PYTHONPATH=src python3 -m unittest discover -s tests -v` → green
   - Export `NVIDIA_API_KEY` (or `NVAPI_KEY`)

2. **Smoke (recommended first)**
   ```bash
   chmod +x scripts/run_nim_smoke.sh scripts/run_track_a_phase4_nim.sh scripts/run_track_b_promotion_assessment.sh
   source scripts/nim_env_defaults.sh
   export NVIDIA_API_KEY='...'
   ./scripts/run_nim_smoke.sh
   ```
   Expect: `artifacts/reports/llm-smoke/nim_smoke_<timestamp>.json` with `run_id` and `nim_model`.

3. **Full matrix + reproducibility**
   ```bash
   ./scripts/run_track_a_phase4_nim.sh
   ```
   Produces:
   - `artifacts/reports/issue7/<execution_id>/` — B0/A1/A4 gate + comparison tables
   - `artifacts/reports/issue8/milestone_gate_review_addendum_provider_template.json` — **pending** HITL template (does not amend deterministic sign-off)
   - Issue #9 rerun under `artifacts/reports/issue9/issue7/<execution_id>/`

4. **Interpret rerun**
   - `exact` → bonus
   - `acceptable_drift` (≤0.02) → pass per `docs/provider-stochastic-reproducibility-policy.md`
   - `mismatch` → stop; diagnose before promotion

5. **Human sign-off**
   - Copy provider addendum template → signed JSON with `human_sign_off.status: signed`
   - Do **not** edit `milestone_gate_review_addendum_20260526T025931Z.json`

### Runtime budget (40 RPM)

Rough critic calls per matrix (dual-critic presets, regenerations): **~80–150** HTTP requests. At 40 RPM, plan **~2–4 minutes** of wall-clock spacing plus model latency. Increase `SIMULA_HTTP_TIMEOUT_SECONDS` if timeouts occur.

---

## Track B — Playbook promotion → integration planning

**Goal:** Decide whether hypotheses H1–H4 are accepted or bounded **using persisted gate evidence**, then gate integration planning.

### Steps

1. After Track A (or on deterministic packet for dry run):
   ```bash
   ./scripts/run_track_b_promotion_assessment.sh artifacts/reports/issue7/<execution_id>
   ```

2. Read `artifacts/reports/track-b/promotion_assessment.json`:
   - Per-hypothesis: `accepted` | `bounded` | `not_accepted`
   - `ready_for_integration_planning`: boolean
   - `blocking_gaps`: list

3. **Promotion requires** (per `docs/research-validation-playbook.md`):
   - H1–H4 accepted or bounded (A2/A3 marked **bounded** until run)
   - B0 gate pass on active packet
   - Issue #9 reproducibility classified (provider: often `acceptable_drift`)
   - Risks/owners documented for provider cost and drift
   - Human sign-off on **provider** addendum if promoting past research phase

4. **Out of scope unless waived:** ADR 0004 Option B (#62 engine-core refactor)

---

## Verbose operator logging

Enable step-by-step progress on **stderr** (pipeline stages, NIM requests, matrix presets). Does **not** log API keys or sample/prompt text.

```bash
export SIMULA_VERBOSE=1   # or SIMULA_LOG=1
./scripts/run_nim_smoke.sh 2>run.log   # optional: capture log file
```

Example lines:

```text
[simula 03:48:12] pipeline run_id=run-... seed=7
[simula 03:48:12] stage start: 40_dual_critic_quality
[simula 03:48:14] nim request #1 critic=critic_a sample=...abc12345 model=mistralai/...
[simula 03:48:14]   nim_rate_limit_wait_s=1.5
[simula 03:48:15]   nim_request_1_verdict=accept
```

## Quick reference — env block

Equivalent to the NVIDIA integrate `requests.post` snippet (non-streaming for binary critic verdicts):

```bash
cp .env.example .env   # once; then set NVAPI_KEY=... in .env (gitignored)
source scripts/nim_env_defaults.sh   # loads .env automatically
export SIMULA_VERBOSE=1
export SIMULA_NIM_MAX_RPM=40
# Optional overrides (defaults match integrate URL + Mistral model above):
# export SIMULA_NIM_BASE_URL='https://integrate.api.nvidia.com/v1/chat/completions'
# export SIMULA_NIM_MODEL='mistralai/mistral-large-3-675b-instruct-2512'
```

Our adapter sends `temperature: 0`, `max_tokens: 16`, and `Accept: application/json` (not SSE). Your reference uses `stream=True` for chat UX; keep **stream off** for this pipeline.

## Paper Alignment Check

- **Traceability/Auditability:** Provider packet is a new execution_id; deterministic evidence and April fail preserved.
- **Protocol/Comparability:** Thresholds and preset comparability fields unchanged; NIM metadata in `provider_runtime` only.
- **Control-axis impact:** Live critics primarily affect quality axis interpretation; coverage/complexity stages remain deterministic.
- **Deviations:** none on ADR 0003 constants.
