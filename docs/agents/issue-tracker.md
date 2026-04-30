# Issue tracker

This repository uses GitHub Issues as the source of truth for planning and execution.

## System of record

- Tracker: GitHub Issues
- Interface: `gh` CLI
- Scope: This repository

## Agent workflow

Skills that create or manage issues should use GitHub Issues operations. Typical actions include:

- create issues for scoped implementation slices
- update issue state and labels during triage
- reference issue numbers in implementation and PR workflows

## Notes

- If the tracker changes in the future, update this file and the `## Agent skills` block in `AGENTS.md`.
