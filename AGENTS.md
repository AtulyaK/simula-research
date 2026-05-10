## Agent skills

### Issue tracker

Issues are tracked in GitHub Issues for this repository. See `docs/agents/issue-tracker.md`.

### New implementation agent briefing

Paste **`docs/agents/next-agent-handoff.md`** at the start of a session so the agent inherits Milestone 3 state, constraints, and prioritized follow-ups.

### Triage labels

Triage uses canonical labels: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Domain docs use a multi-context layout via `CONTEXT-MAP.md` and per-context `CONTEXT.md` files. See `docs/agents/domain.md`.

## Paper Alignment Guardrails (Research Phase)

### Source of truth
- The primary research reference is `docs/research_paper.pdf`.
- Research-phase implementation and evaluation decisions MUST be consistent with:
  - `docs/research_paper.pdf`
  - `docs/adr/0001-research-first-scope.md`
  - `docs/adr/0002-control-axes-as-first-class.md`
  - `docs/adr/0003-evaluation-protocol-and-thresholds.md`
  - `contexts/core/CONTEXT.md`
  - `contexts/eval/CONTEXT.md`

### Required workflow (medium/large tasks)
1. Run `/grill-with-docs` before implementation and include the paper + ADR/context docs above.
2. Use `/tdd` for implementation work.
3. If failures/regressions appear, run `/diagnose` before proposing fixes.
4. If scope changes materially, run `/to-issues` to update execution slices.

### Hard constraints
- Do not change evaluation thresholds, metric formulas, ablation definitions, or protocol semantics without:
  1. explicit justification against `docs/research_paper.pdf`, and
  2. explicit ADR impact assessment (usually `docs/adr/0003-evaluation-protocol-and-thresholds.md`).
- Reproducibility/comparability checks are required before interpreting weak/failed results.
- Prefer parameter-level or policy-level minimal changes over broad refactors during milestone validation.

### Required output section for substantial agent work
Every substantial response MUST include a **Paper Alignment Check** section with:
- **Traceability/Auditability:** how outputs preserve run lineage and artifact evidence.
- **Protocol/Comparability:** confirmation that baseline/ablation comparability remains intact.
- **Control-Axis Impact:** expected effects on coverage, complexity, and quality independently.
- **Deviation Log:** any conflict with paper/ADRs (or “none”).

### Escalation rule
- If paper alignment is ambiguous, stop and request HITL clarification rather than silently proceeding with assumptions.

### Definition of done (research-phase tasks)
A task is not done unless:
- paper alignment is stated explicitly,
- comparability constraints are preserved or formally waived,
- reproducibility implications are documented.
