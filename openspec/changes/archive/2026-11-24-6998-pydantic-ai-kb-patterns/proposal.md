# Proposal: #6998

## Why
Knowledge base manuals for `pydantic-ai` and `pydantic-ai-harness` pin `applies_to` patterns to `@2.71.*` and `@0.71.*`.
When Renovate PR #6989 upgrades dependencies to `2.73.0` and `0.73.0`, `tests/review/test_kb_manuals_metadata.py` reports drift and fails in CI shards.
Other library manuals use major wildcards (for example `pydantic@2.*`).
Widening these patterns to `2.*` and `0.*` allows minor and patch updates to pass validation without false drift.

## What Changes
- Widen `applies_to` in `src/devops_cli/ai/knowledge_base/devops_cli/libraries/pydantic_ai.md` to `pkg:pypi/pydantic-ai@2.*`.
- Widen `applies_to` in `src/devops_cli/ai/knowledge_base/devops_cli/libraries/pydantic_ai_harness.md` to `pkg:pypi/pydantic-ai-harness@0.*`.
- Widen `applies_to` in `src/devops_cli/ai/knowledge_base/it_domains/tools/pydantic_ai.md` to `pkg:pypi/pydantic-ai@2.*`.
- Add test coverage in `tests/review/test_kb_manuals_metadata.py` asserting resolution of minor updates.
- This change alters no behavior that external consumers observe, so it has no spec delta and sets `skip_specs: true` in `.openspec.yaml`.

This change fits one pull request.

## Capabilities
- Knowledge base manual matching for `pydantic-ai` 2.x and `pydantic-ai-harness` 0.x series.

## Impact
- Renovate pull requests upgrading `pydantic-ai` and `pydantic-ai-harness` pass quality checks.
- Zero breaking changes.

## Feasibility
- Verified in CI logs of PR #6989: `tests/review/test_kb_manuals_metadata.py` failed due to drift on `2.73.0` against `@2.71.*`.
- Verified locally with pytest.

## Existing Tool Considered
- Knowledge base metadata system (#1149). No new external tool required.
