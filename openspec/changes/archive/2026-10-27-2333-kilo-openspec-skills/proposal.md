# Proposal

## Why

Issue #2333: Kilo Code is an onboarded agent (`kilo.jsonc`), but the repository commits no OpenSpec skills for it. The skills exist only in `.claude/skills` and `.agents/skills`. A Kilo Code agent that reads a fresh checkout has no OpenSpec entry point.

## What Changes

- Commit `.kilocode/skills/openspec-*`: the propose, explore, apply and update skills, as `openspec update` writes them under the isolated `custom` profile. They are identical to the other two trees.
- Add the tree to the generated globs, so `devops openspec regenerate` and `devops openspec check` cover it.
- Add the tree to the tool-generated and review-routed path classes and to the pre-commit filter of the OpenSpec gate.
- Update ADR 0010 and the scaffold tests.
- `.kilo/command` stays out: it is gitignored, and ADR 0010 generates no commands.
- The change alters no behavior a consumer observes: it adds generated agent files and widens a development check. It has no spec delta and sets `skip_specs: true`.
- This change fits in one pull request.

## Impact

- `src/devops_cli/config/constants.py`, `.pre-commit-config.yaml`, `docs/adr/0010-openspec-is-the-spec-and-change-proposal-layer.md`.
- `tests/test_openspec_scaffold.py`, `tests/support/fakes/openspec.py`, `.kilocode/skills/`.

## Feasibility

- `openspec init --tools kilocode --no-animation` (OpenSpec 1.14.3) in a scratch repository wrote six skills to `.kilocode/skills/` and six commands to `.kilo/command/`.
- The Kilo Code documents name `.kilocode/skills/` as the project skill path. They do not name `.agents/skills`.
- With a seed copy of the skills in `.kilocode/skills`, `uv run devops openspec regenerate` rewrote the tree under the isolated profile with the same four skills, byte-identical to `.claude/skills`. `uv run devops openspec check` passes.

## Existing Tool Considered

OpenSpec writes the skills (`openspec update`), and the existing gate checks them. No new code is built, and no internal code is deleted.
