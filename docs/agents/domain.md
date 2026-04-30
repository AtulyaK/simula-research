# Domain docs

This repository uses a multi-context domain layout.

## Layout

- Root map: `CONTEXT-MAP.md`
- Context docs: per-context `CONTEXT.md` files
- ADRs: either shared in `docs/adr/` or context-local ADR directories when needed

## Consumer rules

Skills that need domain language or architectural history should:

1. Read `CONTEXT-MAP.md` first.
2. Select the relevant context path(s) from the map.
3. Read the target context's `CONTEXT.md`.
4. Read ADRs from the applicable ADR directory for that context.

## Initial contexts

- `contexts/core/CONTEXT.md` for generation pipeline and data mechanism design.
- `contexts/eval/CONTEXT.md` for evaluation methodology and experiment semantics.
