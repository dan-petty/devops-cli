# Proposal

## Why

Issue #1376: GitHub Projects v2 board lookup and field provisioning must fail closed on a failed read.
The `devops gh project sync` command reads board fields with `_fetch_existing_fields_by_name`.
The function returns an empty dictionary when `gh project field-list` fails or prints nothing.
Sync then treats every template field as missing and runs `field-create`.
Failed link requests and failed board lookup reads also drop errors and create duplicate boards.

## What Changes

- Board field reads use `field_list_args` and `FieldListingPayload` with whole-listing checks.
- Board lookup functions raise when GitHub reads fail, distinguishing missing boards from read failures.
- Non-zero CLI exits in field creation and repository linking route through `classify_gh_failure`.
- Scope errors raise `GitHubScopeError` with the missing scope name.
- Project listing commands raise typed errors instead of hiding failures.
- CLI fallback caches `@me` only when the owner matches the authenticated viewer.
- This change alters observable CLI failure reporting and exit codes on failed reads.
- This change fits in one pull request.

## Capabilities

### New Capabilities

- `github-project-sync`: GitHub Projects v2 board lookup, field provisioning, and repository linking fail closed on failed reads.

### Modified Capabilities

None.

## Impact

- Code: `src/devops_cli/github/projects.py`.
- Tests: `tests/test_github_projects.py`.
- Documentation: `src/devops_cli/ai/knowledge_base/devops_cli/subsystems/github.md`.

## Feasibility

- Premise confirmed at commit 6cf8ff0c (`origin/main`).
- `src/devops_cli/github/projects.py:507-535` returns `{}` on non-zero exit or empty stdout.
- `src/devops_cli/github/projects.py:485-505` returns `False` on non-zero exit in `_provision_single_field`.
- `src/devops_cli/github/projects.py:398-421` returns `False` on non-zero exit in `link_project_to_repository`.
- `src/devops_cli/github/projects.py:234-346` returns `None` on failed reads in board lookups.
- `src/devops_cli/github/projects.py:1326-1375` returns empty lists on failed reads in project listings.
- `src/devops_cli/github/projects.py:284-301` caches `@me` for arbitrary owner strings.
- `src/devops_cli/exceptions/git.py` defines `GitHubNotFoundError`, `GitHubUnreadError`, and `GitHubScopeError`.

## Existing Tool Considered

Standard GitHub CLI commands (`gh project`) and GraphQL APIs handle project mutations.
`devops_cli.github.error_classifier.classify_gh_failure` classifies CLI failures.
No new third-party dependency is required.
Internal helper `_fetch_existing_fields_by_name` is replaced with fail-closed schema reading.
