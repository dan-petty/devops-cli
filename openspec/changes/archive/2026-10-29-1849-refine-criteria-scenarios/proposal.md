# Proposal

## Why

Issue #1849, step 7 of the OpenSpec adoption (ADR 0010, "Readiness, closing and the roadmap jobs"). Since the switch, the plan of an item is written as spec-delta requirements with scenarios, but the refine job still proposes each acceptance criterion as `{description, verification}` and renders it as `- Criterion N:` with a `Verification:` line. A person or an agent translates every refined proposal into the shape that the change folder takes. Refine also does not ask the question that AGENTS.md rule 3 and the "Existing Tool Considered" field of the feature request form ask of every plan.

## What Changes

- `AcceptanceCriterion` in `src/devops_cli/roadmap/refine.py` holds the parts of one OpenSpec requirement block: `name`, `requirement`, `scenario`, `when` and `then`. A validator rejects a `requirement` that does not contain SHALL or MUST, with the pattern that OpenSpec 1.14.3 uses. The `description` and `verification` keys are deleted, with no alias.
- `RefinementProposal` gains `existing_tool`: the open, maintained tool or library that covers the need and what it lacks, or the written cost of building instead. It is required. `check_ready` sets an item Ready only when each of the five criterion parts and `existing_tool` are not empty.
- The `## Proposed design` section renders each criterion as an OpenSpec requirement block (`### Requirement:`, the requirement text, `#### Scenario:`, `- **WHEN**`, `- **THEN**`) and the answer under `### Existing Tool Considered`. The `Criterion N` and `Verification:` lines are deleted.
- `roadmap_refine_reply.md` names the new keys. `roadmap_refine_proposal.md` and `roadmap_refine_investigation.md` ask the existing-tool question, so the investigation also looks for the tool.
- Refine's output changes, so the change carries a spec delta: ADDED requirements in `roadmap-refine`.
- This change fits one pull request.

## Capabilities

### Modified Capabilities

- `roadmap-refine`: each criterion is an OpenSpec requirement block, and the proposal answers the existing-tool question.

## Impact

- `src/devops_cli/roadmap/refine.py`.
- `src/devops_cli/ai/tasks/roadmap_refine_reply.md`, `roadmap_refine_proposal.md`, `roadmap_refine_investigation.md`.
- `tests/test_roadmap_refine.py`, `tests/test_roadmap_refine_investigation.py`, `tests/test_ai_client_structured.py`, which use `RefinementProposal` as a sample schema.

## Feasibility

- On origin/main `97ed0ea9` (2026-10-29), `AcceptanceCriterion` is `{description, verification}` (`src/devops_cli/roadmap/refine.py:138`), `check_ready` checks those two keys, and `render_proposal_section` writes `- Criterion {idx}:` and `Verification:`. No prompt under `src/devops_cli/ai/tasks/` asks the existing-tool question.
- `RefinementProposal` is read only in `refine.py` and its tests. No code parses a stored proposal or the rendered `### Acceptance criteria` lines (`git grep "Verification:\|Acceptance criteria" -- src`), so the shape can change with no reader left behind.
- The reply keys are described in one prompt, `roadmap_refine_reply.md`, which refine appends to both the proposal and the investigation prompt (`refine.py:1497`). `test_refines_prompts_load_and_the_reply_prompt_names_every_field` already holds the prompt and the model's fields equal. #2398 replaced the `roadmap_refine_research.md` that the issue names with `roadmap_refine_investigation.md`.
- OpenSpec 1.14.3, the pinned version, defines a requirement block as `### Requirement: <name>` (`REQUIREMENT_HEADER_REGEX` in `dist/core/parsers/requirement-blocks.js`), with a body that matches `/\b(SHALL|MUST)\b/` (`containsShallOrMust` in `dist/core/parsers/requirement-text.js`); a SHALL in the header alone does not count (`validator.js`), and each requirement needs at least one `#### Scenario:` block. A criterion of only `{requirement, when, then}`, as the issue words it, has no name for either heading, so the block that refine renders would not pass `openspec validate --strict`. The model therefore holds a requirement name and a scenario name as well. A block rendered by the new code, put under `## ADDED Requirements` in a scratch change, passed `openspec validate --strict` with OpenSpec 1.14.3 on 2026-10-29.
- No builder or reviewer brief exists in the repository (`git ls-files` finds no such file and no agent definition directory). The briefs that #1833 names are written for each task by the person or agent that delegates, and AGENTS.md rule 3 already binds them. That part of the issue has nothing to change.

## Existing Tool Considered

OpenSpec's requirement and scenario format is the shape, and Pydantic validates the reply as before; the SHALL or MUST check uses OpenSpec's own pattern. Nothing new is built. The change deletes the `description` and `verification` keys, their prompt text, and the renderer's `Criterion N` and `Verification:` lines. ADR 0010's step 8 later replaces the hand-kept reply prompt with `openspec instructions` and `openspec validate`.
