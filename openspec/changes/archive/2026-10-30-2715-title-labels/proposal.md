# Proposal

## Why

Issue #2715. The title of an item is a Conventional Commit, `<type>(<scope>): <summary>`. The labels of the item come from a second source, and they disagree with the title.

- Intake asks the model for the `type/*` label. The model returns `type/security` for `fix(rag): ...` (#2709), `type/infra` for `fix(ci): ...` (#2694) and `type/test` for `fix(telemetry): ...` (#2690).
- Intake sets no `scope/*` label. `devops gh issues triage` reports about 200 open issues without one, and the audit of pull requests expects one.
- `.github/labels.yml` lacks nine scopes and `type/epic`, which the repository and the code use.

## What Changes

- The title is the only source of the type label and the scope label of an item. `fix(security): ...` gets `type/bug` and `scope/security`. `CONST_ROADMAP_COMMIT_TYPE_LABELS` maps each Conventional Commit type to its `type/*` label, and it replaces `CONST_ROADMAP_CONVENTIONAL_COMMIT_TYPE_MAPPINGS`.
- The model picks the type only for a title with no Conventional Commit type, and the prompt says so. The proposal schema is unchanged.
- A scope that `.github/labels.yml` does not declare gets no label. The reason comment names the label to add to the file.
- A `type/*` or `scope/*` label that the issue already holds stays.
- `commit_type` moves from `roadmap/stage.py` to the new module `roadmap/commit_title.py`, with the new `commit_scope`.
- `.github/labels.yml` declares `type/epic` and the scopes `roadmap`, `docs`, `agent`, `terraform`, `monitoring`, `deps`, `service`, `devcontainer` and `valkey`.
- A consumer observes the labels and the comment of intake, so the change carries one spec delta, the new capability `roadmap-intake-title-labels`.
- This change fits one pull request.

## Capabilities

### New Capabilities

- `roadmap-intake-title-labels`: the type and scope labels that intake derives from the title.

### Modified Capabilities

None.

## Impact

- `src/devops_cli/roadmap/commit_title.py` (new), `intake.py`, `intake_model.py`, `stage.py`, `implement.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/lang/en/help.py`, `src/devops_cli/ai/tasks/roadmap_intake_system.md`, `.github/labels.yml`.
- The documents that `devops docs generate --sync-readme` writes.

## Feasibility

- The fault is real. `devops gh api 'repos/{owner}/{repo}/issues?state=all'` on 2026-10-30 lists the pairs of title and label named in Why. `devops gh issues triage` lists the issues without a `scope/*` label. On the base, the new tests fail: the model's `type/security` wins, and no scope label is written.
- `ModelProposal.type` is a required enum of the `type/*` labels of `.github/labels.yml`, so the model needs no change to its schema. Intake already takes a label that an issue holds before the model's.
- release-please and the `Semantic PR title` check already require the Conventional Commit form for a pull request, so the title is a form that the project already enforces. Issue titles follow it by convention (`AGENTS.md`, rule 11).

## Existing Tool Considered

No maintained Python package parses a Conventional Commit title. PyPI lists `conventional-commit` 0.4.2, a tool that writes commits, and no parser. The Node action `amannn/action-semantic-pull-request` checks the pull request title in CI and cannot run in intake. The parse is a split on the first colon and the first parenthesis (the existing `commit_type`, plus `commit_scope`). Cost of the build: about 40 lines of code and 150k tokens of agent work, in one session.

The change deletes the type mapping for the prompt (`CONST_ROADMAP_CONVENTIONAL_COMMIT_TYPE_MAPPINGS` and the `{conventional_types}` placeholder), because code now applies the mapping.
