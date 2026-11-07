# Proposal

## Why

Issue #3247: security and scope questions are left to the model, so plan reviews and fixes returned findings that needed a person, such as a loosened guard, a stored URL, ambient environment variables and a credential redaction in the wrong layer. A deterministic trigger and a non-blank security section make the plan answer what crosses a trust boundary, what a person must confirm, and what test fails if the rule breaks.

## What Changes

- `src/devops_cli/roadmap/stage/stage_change.py` holds the trigger lists, the trigger match, the refusal in `content_problems`, the `security` field of `StageProposal` and the `## Security` section of `_design_file`.
- `src/devops_cli/lang/en/messages.py` holds the refusal that names the matched path or word.
- `src/devops_cli/ai/tasks/roadmap_stage_change.md` states the `security` key and the trigger.
- `tests/roadmap/stage/test_roadmap_stage_security.py` holds the refused plan, the accepted plan, the plan with no trigger and the existence test of each trigger path.
- The golden set gains a case of the security refusal, so the replay measures the new rule.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage`: A security trigger needs a security section, The security triggers are a fixed list of paths and words, The design file holds the security section, The stage prompt names the security rule

## Impact

- Code: `src/devops_cli/roadmap/stage/stage_change.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/roadmap/stage/stage_eval_cases.py`
- Documents: `src/devops_cli/ai/tasks/roadmap_stage_change.md`
- Tests: `tests/roadmap/stage/test_roadmap_stage_security.py`

## Feasibility

- The probes confirm the premise: `The path `SECURITY.md` is a file of the staging commit.` and `The path `pyproject.toml` is a file of the staging commit.` Both are trigger paths that the existence test resolves.
- The probes correct the paths of the issue: `The path `src/devops_cli/roadmap/stage_change.py` is no file at the root of the staging commit.` and `Commit bff2f14f 2026-11-06 refactor(roadmap): group the job modules in subpackages (#3897) deleted or renamed it.` The module is `src/devops_cli/roadmap/stage/stage_change.py`, and the tests are under `tests/roadmap/stage/`. The plan uses those paths and does not restore the old ones.
- `src/devops_cli/roadmap/stage/stage_change.py:def content_problems` collects the text rules of a plan, so the security refusal joins it and no new gate is needed.
- `src/devops_cli/roadmap/stage/stage_change.py:def _design_file` writes `design.md` from the proposal, so a `security` field is the only way the model gives the section text.
- `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py:test_the_top_level_keys_of_the_reply_are_the_fields_of_the_proposal` reads the prompt's key bullets and compares them with `StageProposal`, so the prompt and the field change together.
- A checkout of the repository: `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_security.py` runs the new tests from the checkout.
- A checkout of the repository: `uv run devops roadmap eval stage --replay` replays the golden set through the gates and needs the staged files.
- A network: `uv run devops docs generate --sync-readme` regenerates the documents, and the command reads its catalog from the checkout only.
- The first check runs `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_security.py` against the real suite.
- The second check runs `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_prompt_rules.py` for criterion 4.

## Existing Tool Considered

No open, maintained tool covers a repository-specific gate on a plan's text. The change adds about 90 lines to `src/devops_cli/roadmap/stage/stage_change.py`, its tests and its golden case, at a cost of 30k tokens and 4 hours to build, keep and fix. It deletes no internal code.

## Dependencies

None.
