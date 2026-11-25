# Proposal

## Why

Issue #2292: the project has no complete branch-name rule, and nothing checks one.

- `CONTRIBUTING.md` lists four branch prefixes with `<short-description>`. `docs/SDLC.md` states the rule twice more, and `docs/ROUTINE_TASKS.md` three times more, once with `feature/<name>` and `chore/<name>`. Three documents give different forms.
- Branches that agents push name their issue, as in `fix/2273-wait-otel-exporter-threads`, like the change folder `openspec/changes/<issue>-<slug>`. No document says so.
- Seven of the eleven Conventional Commit types that a pull request title can have (`perf`, `test`, `build`, `ci`, `style`, `chore`, `revert`) have no branch prefix in the guide.
- Eight branches named `implement_issue_*` are on `origin`, and a local branch has no issue number. The pre-commit hook refuses a commit only on `main`.
- No document lists the other naming rules in one place, so an agent cannot tell which are checked.

## What Changes

- A branch is `<type>/<issue>-<slug>`. The types are the 11 types of `release-please-config.json`, which are the types of the pull request title.
- `CONTRIBUTING.md` gets a section "Naming": one table of each artifact, its form, and the check that enforces it, or "None". The section states the branch form once.
- A second `no-commit-to-branch` entry in `.pre-commit-config.yaml` refuses a commit on a branch that does not match.
- `docs/SDLC.md`, `docs/ROUTINE_TASKS.md` and `docs/DEVCONTAINER_USAGE.md` link the section and no longer state a branch form.
- Tests check the pattern of the hook against accepted and refused names, check the Naming table, and retire the old forms from the agent instructions.
- The change alters no behavior that a consumer of `devops` observes: it is a development hook, documents and tests. It has no spec delta and sets `skip_specs: true` in `.openspec.yaml`. It fits in one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- Hook: `.pre-commit-config.yaml`.
- Documentation: `CONTRIBUTING.md`, `docs/SDLC.md`, `docs/ROUTINE_TASKS.md`, `docs/DEVCONTAINER_USAGE.md`.
- Tests: `tests/test_workflow_contracts.py`, `tests/test_agents_md_claims.py`.
- `AGENTS.md` does not change. Its first row already sends "name a branch" to `CONTRIBUTING.md`.

## Feasibility

- The hook supports the pattern. In `pre-commit-hooks` v5.0.0, `no_commit_to_branch.py` takes `--pattern` and fails when `re.match(pattern, branch_name)` matches. A pattern that is a negative lookahead matches each name that does not conform.
- `pre-commit run branch-name --all-files` passes on `docs/2292-naming-section-and-branch-hook` and fails on `implement_issue_1`, and `pre-commit validate-config` accepts the file.
- `release-please-config.json` lists all 11 types in `changelog-sections`, so one list serves the title, the branch, the hook and the guide.
- Each row of the table was read from the repository before it was written: Ruff selects `N`; the 507 command headings and 490 options of `docs/CLI_REFERENCE.md` are lowercase and hyphenated; the 75 variables of `docs/ENV_VARS.md` start with `DEVOPS_CLI_`; `CONST_OPENSPEC_CHANGE_NAME_RE` and `tests/test_change_folders.py` check the change folder; the labels are in `.github/labels.yml`.

## Existing Tool Considered

The `no-commit-to-branch` hook of `pre-commit-hooks`, already in use for `main`, covers the check with a pattern. This change builds no check of its own.
The change deletes the four-prefix list in `CONTRIBUTING.md`, the two statements of the rule in `docs/SDLC.md` and the three in `docs/ROUTINE_TASKS.md`.
