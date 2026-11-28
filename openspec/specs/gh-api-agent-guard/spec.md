# gh-api-agent-guard Specification

## Purpose

Refuse agent callers from performing mutating `devops gh api` requests targeting repository settings, rulesets, secrets, organization settings, or repository transfer while allowing reads, `--dry-run` previews, person sessions, and open collaboration routes.

## Requirements

### Requirement: Protected route table
The `gh api` guard SHALL classify POST, PATCH, PUT and DELETE endpoints under repository settings, rulesets, secrets, organization settings and repository transfer, and POST endpoints under deployment review (`pending_deployments` and `deployment_protection_rule`), as protected.

#### Scenario: Protected route classes
- **WHEN** a test passes one representative endpoint from each protected class (`PATCH repos/o/r`, `PUT repos/o/r/branches/main/protection`, `POST repos/o/r/rulesets`, `PUT repos/o/r/actions/secrets/KEY`, `PATCH orgs/o`, `POST repos/o/r/transfer`, `POST repos/o/r/actions/runs/241/pending_deployments`, `POST repos/o/r/actions/runs/241/deployment_protection_rule`) to the route table
- **THEN** the table classifies each endpoint under its matching protected class

### Requirement: Open routes
The `gh api` guard SHALL classify issue, pull request, label and workflow dispatch endpoints as open for agent callers.

#### Scenario: Agent open route
- **WHEN** a test checks an agent write to `POST /repos/o/r/issues`, `POST /repos/o/r/pulls`, `POST /repos/o/r/labels` and `POST /repos/o/r/actions/workflows/1/dispatches`
- **THEN** the guard allows each request

### Requirement: Agent protected write refused
The `gh api` command SHALL refuse a protected write when `core.caller.is_agent_caller` is true.

#### Scenario: Agent protected write
- **WHEN** a test invokes the guard or `devops gh api` with an agent caller and a protected method and endpoint
- **THEN** it raises a refusal or exits non-zero with a message naming the matched route and the owner step, and the request sender is not called

### Requirement: Person protected write allowed
The `gh api` command SHALL allow a protected write when `core.caller.is_agent_caller` is false.

#### Scenario: Person protected write
- **WHEN** a test invokes the guard or `devops gh api` with a person caller and a protected method and endpoint
- **THEN** the guard allows the request and the request sender runs once

### Requirement: Dry run prints protected request
The `gh api` command SHALL print the request and send no request for a protected route when `--dry-run` is set.

#### Scenario: Agent dry run protected write
- **WHEN** a test invokes `devops gh api` with an agent caller, a protected method and endpoint, and `--dry-run`
- **THEN** stdout shows the method and endpoint, and the request sender is not called

### Requirement: Route normalization
The route table SHALL match a protected endpoint after it strips a leading slash and a query string.

#### Scenario: Protected endpoint with query string
- **WHEN** a test passes `PUT /repos/o/r/rulesets/1?force=true` to the route table
- **THEN** the table returns the `rulesets` protected classification

### Requirement: Documentation states refusal
The documentation SHALL name the protected route classes and the refusal behavior, including `deployment review` (`pending_deployments` and `deployment_protection_rule`).

#### Scenario: Documentation update
- **WHEN** `uv run devops ci docs` validates `docs/commands/gh.md`, `docs/CLI_REFERENCE.md`, and `SECURITY.md`
- **THEN** the check exits 0 and each file names `deployment review`, `pending_deployments`, and `deployment_protection_rule` and states that agent writes on those routes are refused

### Requirement: Agent deployment review write refused
The guard and `devops gh api` SHALL refuse `POST repos/{owner}/{repo}/actions/runs/{run_id}/pending_deployments` and `POST repos/{owner}/{repo}/actions/runs/{run_id}/deployment_protection_rule` for any `{run_id}` when `core.caller.is_agent_caller` is true, while allowing person callers and `GET` reads.

#### Scenario: Agent reviews a pending deployment or custom protection rule
- **WHEN** an agent caller invokes `require_gh_api_access` or `devops gh api -X POST` with `repos/dan-petty/infra/actions/runs/241/pending_deployments`, `repos/dan-petty/infra/actions/runs/999999/pending_deployments`, or `repos/dan-petty/infra/actions/runs/241/deployment_protection_rule`
- **THEN** the call raises `GitHubApiAccessRefusedError` (or exits 1) with `details["route_class"] == "deployment review"` and sends no request, while a person caller succeeds
