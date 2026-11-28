## MODIFIED Requirements

### Requirement: Protected route table
The `gh api` guard SHALL classify POST, PATCH, PUT and DELETE endpoints under repository settings, rulesets, secrets, organization settings and repository transfer, and POST endpoints under deployment review (`pending_deployments` and `deployment_protection_rule`), as protected.

#### Scenario: Protected route classes
- **WHEN** a test passes one representative endpoint from each protected class (`PATCH repos/o/r`, `PUT repos/o/r/branches/main/protection`, `POST repos/o/r/rulesets`, `PUT repos/o/r/actions/secrets/KEY`, `PATCH orgs/o`, `POST repos/o/r/transfer`, `POST repos/o/r/actions/runs/241/pending_deployments`, `POST repos/o/r/actions/runs/241/deployment_protection_rule`) to the route table
- **THEN** the table classifies each endpoint under its matching protected class

### Requirement: Documentation states refusal
The documentation SHALL name the protected route classes and the refusal behavior, including `deployment review` (`pending_deployments` and `deployment_protection_rule`).

#### Scenario: Documentation update
- **WHEN** `uv run devops ci docs` validates `docs/commands/gh.md`, `docs/CLI_REFERENCE.md`, and `SECURITY.md`
- **THEN** the check exits 0 and each file names `deployment review`, `pending_deployments`, and `deployment_protection_rule` and states that agent writes on those routes are refused

## ADDED Requirements

### Requirement: Agent deployment review write refused
The guard and `devops gh api` SHALL refuse `POST repos/{owner}/{repo}/actions/runs/{run_id}/pending_deployments` and `POST repos/{owner}/{repo}/actions/runs/{run_id}/deployment_protection_rule` for any `{run_id}` when `core.caller.is_agent_caller` is true, while allowing person callers and `GET` reads.

#### Scenario: Agent reviews a pending deployment or custom protection rule
- **WHEN** an agent caller invokes `require_gh_api_access` or `devops gh api -X POST` with `repos/dan-petty/infra/actions/runs/241/pending_deployments`, `repos/dan-petty/infra/actions/runs/999999/pending_deployments`, or `repos/dan-petty/infra/actions/runs/241/deployment_protection_rule`
- **THEN** the call raises `GitHubApiAccessRefusedError` (or exits 1) with `details["route_class"] == "deployment review"` and sends no request, while a person caller succeeds
