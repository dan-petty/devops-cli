# Proposal: #4827

## Why

`devops ai pipeline` sends a goal through a chain of personas and asks each model to find defects. ADR 0005 rejected that approach: 26 of 219 persona rows (11.9 %) were valid. The command does not store or score its output, and no other command or job calls it. #1151 deleted the persona stage of `devops review`, but the review still labels its result with the DevSecOps persona. A pull request comment thus says `Review by DevSecOps` and `Personas: DevSecOps` for a review that ran no persona. Documents and unread model fields still describe persona review. Closes #4827.

## What Changes

- Delete the `pipeline` command of `src/devops_cli/commands/ai.py` with its stage helpers, its four defaults, its help texts, its dry-run plan `plan_ai_pipeline` and the unread constant `CONST_PIPELINE_STAGE_TRUNCATION_SUFFIX`. Delete its tests and its rows in the dry-run and help tests. Alpha keeps no compatibility, so no shim stays.
- `execute_review_workflow` and the functions under it return a list of `ReviewResult | str`, not of `(PersonaDefinition, ReviewResult | str)` pairs. The pull request comment drops the `Personas:` line and the `Review by <persona>` heading. The model notes of more than one result follow one another under one heading.
- The message of a review whose every file is a routed file says that only the secret scan reads those files, not that nothing is left for the personas. The ambiguous candidate message names the fingerprint and the location, the key it compares.
- Delete `ScratchpadBuffer` and `ScratchpadEntry` from `src/devops_cli/models/ai.py`, and the `persona` fields and `persona_distribution` of the review request and result models. Nothing reads them.
- Fix `ARCHITECTURE.md` (the review section), `docs/SELF_IMPROVEMENT.md`, `k8s/README.md`, the help text of `--explain` and the description of the `ai` settings. Regenerate `README.md`, `docs/CLI_REFERENCE.md`, `docs/commands/ai.md` and `docs/CONFIGURATION.md`.

## Capabilities

### New Capabilities

- `review-pr-comment`: what the pull request comment of `devops review pr --post` holds.

### Modified Capabilities

None.

## Impact

- `devops ai pipeline` is no longer a command: it exits with a usage error.
- A posted review comment no longer names a persona. No setting, manifest or dependency changes.
- The personas stay for `devops ai chat` and the other AI commands that read them.

## Feasibility

- `git grep -n "ai pipeline"` on `origin/main` finds the command only in its module, its tests, the generated references and two lines of `k8s/README.md`. No workflow, job or manifest calls it.
- `git grep -n -P "build_agent|get_llm_client|PERSONAS\[" -- src/devops_cli/ai/review src/devops_cli/review` finds one model client, the group analysis client of `runner.py`, and one persona read, `PERSONAS[Persona.DEVSECOPS]` in `_report_review`. That read only gives the label of the result. No stage calls a persona.
- `git grep -n -P "ScratchpadBuffer|ScratchpadEntry"` finds no reader outside `src/devops_cli/models/`. The review request and result models are built only in `tests/models/test_resource_schemas.py`.

## Existing Tool Considered

A delete. No tool applies. Cost to build: about 60,000 tokens and 1.5 hours, as the issue gives.
