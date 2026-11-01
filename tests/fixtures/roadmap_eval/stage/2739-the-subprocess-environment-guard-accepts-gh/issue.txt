### Problem Description

`GH_TELEMETRY_ENDPOINT_URL` is a key that the `gh` binary reads (`grep` of the installed gh 2.103.3 shows the name next to `GH_TELEMETRY` and `GH_TELEMETRY_SAMPLE_RATE`). It appears to name the URL that gh sends its telemetry to. `build_subprocess_env` in `src/devops_cli/core/process.py` accepts a caller override of it, so a caller can send the telemetry of a gh child to a host that it names. That is egress of command data, not code execution.

I did not probe this key. The name comes from the strings of the gh binary, and `gh help environment` does not list it. The first step of the fix is a probe: run gh with `GH_TELEMETRY=log` or a loopback server, a temporary HOME and a fake token, and see what gh sends and where. #2672 (PR #2732) refuses the gh keys that make gh run a program and does not cover this key.

### Reproduction Steps

1. Run `uv run python -c 'from devops_cli.core.process import build_subprocess_env as b; print(b(env={"GH_TELEMETRY_ENDPOINT_URL": "https://example.com"}))'`.
2. Check that the output holds the key and that no `SecurityError` is raised.
3. Probe gh with a loopback endpoint, to see what a gh command sends. This step is still to do.

### Expected vs Actual Behavior

Expected: the guard refuses the key, or the design of the fix names the reason to accept it, after a probe shows what gh sends. Actual: the guard returns the key unchanged.

### Environment Diagnostics

- DevOps CLI Version: main after #2732
- Execution Environment: DevContainer
- gh 2.103.3

### Logs, Traces, or Terminal Output

```shell
Not probed.
```

### Pre-Submission Checklist

- [x] I have verified that no sensitive credentials, private keys, or internal tokens are contained in this issue report.
- [x] I have checked existing issues and pull requests to ensure this is not a duplicate.

<!-- devops-roadmap-refine:start -->
<!-- checked-at: sha=07fb4c222b09ef6bb9e6fc9cd1d5fbb45f6c9a78 -->
## Proposed design

### Problem statement
The subprocess environment guard in build_subprocess_env accepts a caller override of GH_TELEMETRY_ENDPOINT_URL. This key names the URL that the gh binary sends its telemetry to. A caller can therefore redirect gh telemetry to a host it names, which is egress of command data to an arbitrary destination. The guard already refuses code-loading keys, but it does not refuse data-egress keys that name a network destination.

### Acceptance criteria

### Requirement: Refuse GH_TELEMETRY_ENDPOINT_URL caller override
build_subprocess_env SHALL raise SecurityError when a caller provides GH_TELEMETRY_ENDPOINT_URL in the env parameter.

#### Scenario: Caller sets the telemetry endpoint key
- **WHEN** build_subprocess_env is called with env={"GH_TELEMETRY_ENDPOINT_URL": "`https://example.com"}`
- **THEN** a SecurityError is raised and the key is not in the returned environment

### Requirement: Ambient path already excludes the key
The ambient environment filter SHALL exclude GH_TELEMETRY_ENDPOINT_URL because it is not in DEFAULT_ALLOWED_ENV_VARS and matches no allowed prefix.

#### Scenario: Ambient environment holds the key
- **WHEN** os.environ contains GH_TELEMETRY_ENDPOINT_URL and isolate_env is True
- **THEN** the key is absent from the returned environment dictionary

### Requirement: Other GH_TELEMETRY keys are not refused
build_subprocess_env SHALL NOT raise SecurityError for a caller override of GH_TELEMETRY or GH_TELEMETRY_SAMPLE_RATE.

#### Scenario: Caller sets the telemetry toggle key
- **WHEN** build_subprocess_env is called with env={"GH_TELEMETRY": "log"}
- **THEN** no SecurityError is raised and the key is present in the returned environment

### Existing Tool Considered
No check has run. The change adds one key to the project's own refused-env-var list in src/devops_cli/core/process.py and src/devops_cli/config/constants.py, plus one test case. The written cost is about 15 lines of code and test, well under one page of tokens to build, keep and fix.

### Key questions
- **What does GH_TELEMETRY_ENDPOINT_URL do in the gh binary?**: It names the URL that gh sends its telemetry to. The name appears in the strings of gh 2.103.3 next to GH_TELEMETRY and GH_TELEMETRY_SAMPLE_RATE. gh help environment does not list it. The project's archived design for #2672 records it as naming a place for data, not a program. [sources: openspec/changes/archive/2026-10-30-2672-refuse-gh-kubectl-code-env-keys/design.md:26]
- **Should the guard refuse GH_TELEMETRY_ENDPOINT_URL as a caller override?**: Yes. A caller must not redirect gh telemetry to a host it names. The key names a network destination, which is egress of command data. The project principle is to give a child only the keys it needs, and no legitimate caller needs to redirect gh telemetry to a custom URL. (best practice) [sources: ARCHITECTURE.md:181, src/devops_cli/core/process.py]
  - Chosen: Refuse the key. A caller naming a telemetry destination is egress of data to an arbitrary host. No legitimate caller needs this.
  - Rejected: Accept the key with a documented reason. Rejected because no caller in this project needs to redirect gh telemetry to a custom URL, and the principle of least privilege applies.
- **Should GH_TELEMETRY and GH_TELEMETRY_SAMPLE_RATE also be refused?**: No. They control whether telemetry is on and the sample rate, but they do not name a destination. Only GH_TELEMETRY_ENDPOINT_URL names a URL that data is sent to, making it the egress vector. (best practice) [sources: openspec/changes/archive/2026-10-30-2672-refuse-gh-kubectl-code-env-keys/design.md:26]
  - Chosen: Refuse only GH_TELEMETRY_ENDPOINT_URL. It is the only one of the three that names a network destination a caller can control.
  - Rejected: Refuse all three GH_TELEMETRY keys. Rejected because the other two do not redirect data to a caller-controlled host; they only toggle or rate-limit telemetry to the default destination.
- **Where in the code should the refusal be added?**: Add GH_TELEMETRY_ENDPOINT_URL to a new constant of data-egress keys in src/devops_cli/config/constants.py, and extend _is_env_override_refused in src/devops_cli/core/process.py to also refuse keys in that set. This follows the existing pattern of named constants per category imported from devops_cli.config.constants. (best practice) [sources: src/devops_cli/core/process.py, src/devops_cli/config/constants.py]
  - Chosen: New data-egress constant in constants.py. Follows the existing pattern of named constants per category (CONST_CODE_LOADING_ENV_PATTERNS, CONST_GH_TOKEN_ENV_VARS, etc.).
  - Rejected: Add to DEFAULT_DENIED_ENV_PATTERNS. Rejected because that list filters the ambient environment path, which already excludes the key via the allowlist. It would also block the key from extra_allowed_keys, which is broader than needed.
  - Rejected: Hardcode in _is_env_override_refused. Rejected because it does not follow the project's pattern of named constants imported from the config module.

### Fit
Fits in one pull request.

### Suspected block
None.

### Dependencies
None.
<!-- devops-roadmap-refine:end -->

<!-- devops-roadmap-record {"Effort": "Low", "Priority": "P1-High", "Status": "In Review", "Value": "High", "implement.branch": "fix/2739-the-subprocess-environment-guard-accepts-gh", "implement.group": "1", "implement.job": "devops-cli-runner-20261031-183805-c36f", "implement.job_state": null, "implement.pr": "2901", "implement.sha": "b73de49f53bc08a1e217437711f2bab7d0a931fd", "implement.spend": "{\"requests\": 44, \"input_tokens\": 1563656, \"output_tokens\": 7086}", "implement.stopped": null, "refine.alternatives_asked": null, "refine.block_paths": null, "refine.blocked_by": null, "refine.body_hash": "7d691501e4cc146bace60f14fb5dd0806300e48a5ad57436fc10227c1aa8dd79", "refine.failed_body_hash": null, "refine.needs_split": "false", "refine.next_step": "ready", "refine.section_hash": "89124d06c8544622725a2928145a3da294a83c6ad71f146c35758443461bdf97", "stage.branch": null, "stage.file_cap": null, "stage.groups": null, "stage.needs_split": null, "stage.pr": null, "stage.ready": null, "stage.sha": null} -->
