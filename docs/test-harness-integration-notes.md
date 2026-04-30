# Test Harness Integration Notes (#2/#3)

This harness is intentionally stage-agnostic so issue #2 and issue #3 can share setup code without coupling tests to provider-specific outputs.

## Provided modules

- `tests/support/fixtures.py`
  - `make_taxonomy_node()`
  - `make_meta_prompt()`
  - `make_instantiation()`
- `tests/support/traceability.py`
  - `assert_meta_prompt_traceability()`
  - `assert_instantiation_traceability()`

## Expected integration points

- Issue #2 tests should validate taxonomy linkage by asserting every produced `meta_prompt` carries `taxonomy_node_id`.
- Issue #3 tests should validate instantiation lineage by asserting each `instantiation` carries:
  - root `meta_prompt_id`
  - nested `lineage.meta_prompt_id`
  - nested `lineage.taxonomy_node_id`
- If #2/#3 add extra metadata fields, keep them additive; do not remove current traceability keys.

## Design constraints

- No concrete provider model IDs or API response shapes are embedded in fixtures.
- Fixture IDs are deterministic and human-readable to simplify assertion diffs.
- Assertions fail with explicit expected/actual values to improve debugging speed.
