# Design

## Decisions

### Protect only the two POST deployment review routes under `deployment review`

Add `("deployment review", frozenset({"POST"}), "repos/{owner}/{repo}/actions/runs/{run_id}/pending_deployments")` and `("deployment review", frozenset({"POST"}), "repos/{owner}/{repo}/actions/runs/{run_id}/deployment_protection_rule")` to `CONST_GH_API_PROTECTED_ROUTES` (`src/devops_cli/config/constants.py:3184`), leaving `GET` reads and person callers allowed through `require_gh_api_access` (`src/devops_cli/github/api_guard.py:84-100`).

### Document `deployment review` in help text, generated docs, and `SECURITY.md`

Update `GHCommandHelp.api` (`src/devops_cli/lang/en/help.py:1473`) and `SECURITY.md:58` to list `deployment review` (`pending_deployments`, `deployment_protection_rule`) and regenerate `docs/commands/gh.md` and `docs/CLI_REFERENCE.md` via `devops docs generate`.

## Rejected alternatives

- **Block every `POST` under `repos/{owner}/{repo}/actions/runs/{run_id}/**`**: Refuses legitimate agent actions such as `rerun`, `rerun-failed-jobs`, and `cancel`, violating the narrowest-area rule (`src/devops_cli/config/constants.py:3182`).
- **Reuse `repository settings`**: A deployment review approves a pending environment deployment rather than modifying repository settings, so reusing `repository settings` would misreport the route class.
- **Wait for ADR 0041 or `#7497`**: The guard table change is independent of `#7497` (`openspec/changes/7497-onboard-settings-opentofu/`) and prevents agent self-approval before environment apply gates go live.
