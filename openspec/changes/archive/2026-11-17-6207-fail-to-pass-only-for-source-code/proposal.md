# Proposal: #6207

## Why
Owner, 2026-11-17: "make sure you aren't writing tests for changes that aren't to src and fix fail to pass accordingly". A test that fails on base proves a change of code, but the fail-to-pass workflow, `devops ci fail-to-pass` and the stage `behavior` rule took any path under `src/` as code. A fix that changes only a prompt, a tool pin, a lockfile, a template or other data under `src/` then had to bring a test of a value. Closes #6207.

## What Changes
- `is_source_code` in `devops_cli.ci.fail_to_pass` is the one definition of source code: a `.py` file under `src/` outside `src/devops_cli/ai/knowledge_base/`.
- `devops ci fail-to-pass` passes with no replay, and says why, when the diff changes no source code and no gate check module.
- `.github/workflows/fail-to-pass.yml` starts only for a change of `src/**/*.py` outside the knowledge base, or of a gate check module.
- `changes_source` in the stage reads `is_source_code`: a `behavior` group changes a Python file under `src/`. The plan reader and the tuicr follow-up section read the same rule. The stage prompts and docs/TESTING.md say so.

## Capabilities
- Modified: `ci-fail-to-pass`, `roadmap-plan-check`.

## Impact
- A fix of a prompt, a pin or other data under `src/` gets no Fail-to-Pass check run and no request for a test; its proof is a validator or a check command. #5585 (a `tools.lock` pin bump) is one such case.
- A stage group that changes only a prompt or data under `src/` must be `other` (or `manifest`), so the implement step asks it for no test that fails on base.

## Feasibility
- `git ls-files src` holds 120 files that are no `.py` outside the knowledge base: 54 prompts in `src/devops_cli/ai/tasks`, the tools lock and its npm and pip-compile files, templates, design tokens, persona files and review rules.
- GitHub path filters take `**/*.py` with a later `!` pattern, as the workflow already does for the knowledge base.

## Existing Tool Considered
- No tool decides this; it is a rule of the project. The change reuses the changed-file listing that the replay already reads (`list_changed_files`) and adds one predicate, about 15 lines.
