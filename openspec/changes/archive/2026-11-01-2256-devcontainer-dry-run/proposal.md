# Proposal

## Why
Issue #2256 addresses the dry-run rule (#412) for devcontainer and install-tools commands. The rule states that a dry run makes no external requests and returns the planned requests that the real run makes. Currently, 6 commands make external requests or run subprocesses without a request plan, 2 commands mutate local state without `--dry-run` previews, and 3 commands make no external requests and need the `no-external-request` classification (removing legacy echo-only previews).

## What Changes
- Classify 6 commands with `@dry_run_class("request-plan")`, adding `--dry-run` and `--json` support to preview external requests without executing subprocesses, network calls, or interactive prompts:
  - `devcontainer bootstrap-k8s`
  - `devcontainer post-create`
  - `devcontainer post-start`
  - `devcontainer run-lifecycle`
  - `devcontainer unlock-keyring`
  - `install-tools`
- Classify 2 local mutating commands with `@dry_run_class("no-external-request")`, adding `--dry-run` to print local previews without modifying files:
  - `devcontainer init`
  - `devcontainer update`
- Classify 3 commands with `@dry_run_class("no-external-request")`:
  - `devcontainer list` (remove `--dry-run` and echo-only preview)
  - `devcontainer validate` (remove `--dry-run` and echo-only preview)
  - `install-tools status`
- Remove all 11 commands from `tests/fixtures/dry_run_gaps.json`.
- Add test coverage across all 11 commands verifying dry run behavior and zero external calls.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `command-dry-run-class`: Add requirements and scenarios specifying request-plan behavior for `devcontainer bootstrap-k8s`, `devcontainer post-create`, `devcontainer post-start`, `devcontainer run-lifecycle`, `devcontainer unlock-keyring`, and `install-tools`; local previews for `devcontainer init` and `devcontainer update`; and no-external-request execution for `devcontainer list`, `devcontainer validate`, and `install-tools status`.

## Impact
- Command interfaces: Request-plan commands gain `--dry-run` and `--json` previews; local mutating commands gain `--dry-run` previews; legacy echo-only `--dry-run` options are removed from read-only commands.
- Test suite: `tests/fixtures/dry_run_gaps.json` gap count decreases by 11.
- Documentation: CLI documentation synchronized.

## Feasibility
Confirmed against repository code and upstream rules:
- `devcontainer bootstrap-k8s` plans `minikube status`, `minikube start`, and `minikube update-context` with zero subprocess calls.
- `devcontainer post-create` plans tool installations (`curl -LsSf https://astral.sh/uv/install.sh | sh`, `uv tool install pre-commit`, `curl -fsSL https://claude.ai/install.sh | bash`, and managed tools downloads).
- `devcontainer post-start` plans `git config` and `kubectl config` updates.
- `devcontainer run-lifecycle` plans post-create and post-start lifecycle requests according to passed flags.
- `devcontainer unlock-keyring` plans `gnome-keyring-daemon --replace --unlock`, `gh auth token`, and `gh auth login`.
- `install-tools` plans HTTP downloads and installer executions for locked tools.
- `devcontainer init` and `devcontainer update` print preview actions and skip filesystem writes under `--dry-run`.
- The 3 mark-only commands execute locally with zero external network or cluster requests.
- All 11 commands are currently listed in `tests/fixtures/dry_run_gaps.json`.
- Fits in one pull request.

## Existing Tool Considered
The change uses internal mechanisms `PlannedRequest`, `render_request_plan`, and `@dry_run_class` introduced in #741 and sub-issue 00 (#886). It removes legacy echo-only previews with no backward-compatibility shim.
