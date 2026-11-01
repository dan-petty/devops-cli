### Problem Description

`devops k8s deploy-stack --dry-run` does not list the requests that the real run makes. For each Helm release, it gives only the release name (`details.helm_releases`). It does not give the repository that `helm repo add` adds, or the chart, the version and the values file that `helm upgrade --install` uses.

The dry-run rule (#412) says that a dry run makes no request and returns the requests that the real run would make. #2239 puts `k8s deploy-stack` out of its scope as "already done" with a request plan (#741). But `deploy_stack` in `src/devops_cli/commands/k8s/stack_lifecycle.py` calls `render_dry_run_result` with `"helm_releases": [r["name"] for r in all_releases]`, and it calls no `render_request_plan`. Only the Secret push has a request plan.

Effects:

- A person cannot use the dry run to check which chart and version deploy-stack installs. Issue #1632 gives the check "Run `devops k8s deploy-stack --stack logging --dry-run` and confirm the chart is `grafana-community/loki`". The output cannot show that.
- A test of the chart, the version and the repository that deploy-stack installs must read the private tables `_HELM_RELEASES_BY_STACK` and `_HELM_REPOS_BY_STACK`. docs/TESTING.md says that no test uses a private name, and that a test reaches private code through its public interface. 13 test files under `tests/` read these tables, for example `tests/test_k8s_logging_stack.py`, `tests/test_k8s_argocd_apps.py`, `tests/test_k8s_monitoring_integration.py` and `tests/test_k8s_tempo.py`.

### Reproduction Steps

1. Check out `main` (commit 8b650a64).
2. Run `uv run devops k8s deploy-stack --stack logging --dry-run`.
3. Look at `details.helm_releases` in the output.

### Expected vs Actual Behavior

Expected: the dry run lists each request that the real run makes, in order, built by the same argument builders that the real run uses (`_deploy_helm_repos`, `_build_helm_upgrade_cmd`). For the `logging` stack, this includes `helm repo add grafana-community https://grafana-community.github.io/helm-charts` and `helm upgrade --install ... loki grafana-community/loki --version <version> --namespace logging --values k8s/logging/loki-values.yaml ...`. A test can then read the chart, the version and the repository from the dry run of the command, through the `cli` fixture.

Actual: the dry run gives `"helm_releases": ["loki"]` and no helm request.

### Environment Diagnostics

devops-cli from a checkout of `main` (commit 8b650a64), run with `uv run`. Linux on WSL2, Python 3.14.

### Logs, Traces, or Terminal Output

Part of the output of `uv run devops k8s deploy-stack --stack logging --dry-run` (the context and the Secret rows are left out):

```json
{
  "command": "devops k8s deploy-stack",
  "status": "DRY_RUN",
  "action": "deploy_k8s_stack",
  "details": {
    "stack": "logging",
    "helm_releases": [
      "loki"
    ],
    "manifests": [
      "k8s/logging/networkpolicy.yaml"
    ]
  }
}
```

### Pre-Submission Checklist

- [x] I have verified that no sensitive credentials, private keys, or internal tokens are contained in this issue report.
- [x] I have checked existing issues and pull requests to ensure this is not a duplicate. #2239 is about the dry runs of the other k8s commands, and it names deploy-stack as done. #1323 is about the k8s command tests over edge fakes.


Source: https://github.com/dan-petty/devops-cli/issues/1632

<!-- devops-roadmap-refine:start -->
<!-- checked-at: sha=0f7bc266fd52ad4b6ad23bf65b710cd20c398b18 -->
## Proposed design

### Problem statement
The dry run of `devops k8s deploy-stack` lists only release names in `details.helm_releases`. It does not list the `helm repo add` and `helm upgrade --install` commands that the real run makes. A person cannot verify the chart, version, and repository from the dry-run output. Tests must read the private tables `_HELM_RELEASES_BY_STACK` and `_HELM_REPOS_BY_STACK` to check these values, which violates the rule in docs/TESTING.md that no test imports a private name.

### Acceptance criteria

### Requirement: Dry run lists helm repo commands
The dry run of `deploy-stack` SHALL list each `helm repo add` command and the `helm repo update` command that the real run makes, in order, with the repository name and URL.

#### Scenario: logging stack dry run shows repo add
- **WHEN** A test runs `deploy-stack --stack logging --dry-run` through the `cli` fixture
- **THEN** The output contains a command with arguments `helm repo add grafana-community https://grafana-community.github.io/helm-charts` and a command with arguments `helm repo update`

### Requirement: Dry run lists helm upgrade commands
The dry run of `deploy-stack` SHALL list each `helm upgrade --install` command that the real run makes, in order, with the release name, chart, version, namespace, and values file.

#### Scenario: logging stack dry run shows upgrade with chart and version
- **WHEN** A test runs `deploy-stack --stack logging --dry-run` through the `cli` fixture
- **THEN** The output contains a command with arguments including `loki`, `grafana-community/loki`, `--version`, `20.0.2`, `--namespace`, `logging`, `--values`, and the path to `loki-values.yaml`

### Requirement: Tests read commands from dry-run output
A test SHALL be able to read the chart, version, and repository from the dry-run output of `deploy-stack` without importing a private name from `devops_cli`.

#### Scenario: test reads chart from dry-run JSON
- **WHEN** A test invokes `deploy-stack --stack logging --dry-run` and parses the JSON output
- **THEN** The test finds the chart `grafana-community/loki`, version `20.0.2`, and repository URL in the command list, and the test imports no name starting with `_` from `devops_cli`

### Requirement: Commands match the real-run builders
The commands in the dry-run output SHALL be built by the same argument builders that the real run uses, so that a change to a builder changes both the dry-run output and the real run.

#### Scenario: builder change reflects in dry run
- **WHEN** A test calls `_build_helm_upgrade_cmd` with a release dict and compares its result to the corresponding command in the dry-run output
- **THEN** The two command lists are equal

### Existing Tool Considered
No open, maintained library covers this need. The dry-run mechanism (`render_dry_run_result` in `src/devops_cli/dry_run.py`) and the argument builders (`_deploy_helm_repos`, `_build_helm_upgrade_cmd` in `src/devops_cli/commands/k8s/stack_lifecycle.py`) are project-specific code. The fix calls the existing builders in the dry-run path and adds their output to the `details` dict. The written cost is the tokens to edit the dry-run branch of `deploy_stack`, add the command list to `details`, and update the tests that read the private tables to read the dry-run output instead. The elapsed time is under one hour of focused work.

### Key questions
- **What format holds the helm commands in the dry-run `details` dict?**: A list of argument lists (each element is a `list[str]`), matching the format that `runtime._run_cmd` receives and that `_build_helm_upgrade_cmd` returns. The key is `helm_commands`. The existing `helm_releases` key stays for backward compatibility. (best practice) [sources: src/devops_cli/commands/k8s/stack_lifecycle.py:571, src/devops_cli/commands/k8s/stack_lifecycle.py:615]
  - Chosen: List of argument lists (list[str] per command). Matches the return type of `_build_helm_upgrade_cmd` and the argument to `runtime._run_cmd`. A test can compare exact arguments. No parsing needed.
  - Rejected: List of joined command strings. Human-readable but loses the argument boundaries. A test must re-split to check individual flags. Rejected.
  - Rejected: Structured objects with type and fields. More verbose than needed. The command list already carries all fields. Adds a schema to maintain. Rejected.
- **Does the dry run keep the existing `helm_releases` list of names?**: Yes. The key stays so that existing consumers and tests that read it do not break. The new `helm_commands` key carries the full commands. (best practice) [sources: src/devops_cli/commands/k8s/stack_lifecycle.py:1319]
  - Chosen: Keep `helm_releases` and add `helm_commands`. Backward compatible. Existing tests and scripts that read `helm_releases` still work. The new key adds the detail the issue asks for.
  - Rejected: Replace `helm_releases` with `helm_commands`. Cleaner but breaks every consumer that reads the old key. The 13 test files that read the private tables would all need updating in the same PR. Rejected for scope.
- **Does the dry run include the `helm repo update` command?**: Yes. The real run calls `helm repo update` after all `helm repo add` calls. The dry run lists it in the same position. (best practice) [sources: src/devops_cli/commands/k8s/stack_lifecycle.py:622]
  - Chosen: Include `helm repo update` in the command list. The real run makes this request. The dry-run rule says the dry run returns the requests the real run would make.
  - Rejected: Omit `helm repo update`. It is a no-op if the repos are already added. But the dry-run rule does not allow omitting a request the real run makes. Rejected.
- **Does the dry run include the `--wait` and `--timeout` flags in the upgrade command?**: Yes. The real run passes `wait` and `timeout` to `_build_helm_upgrade_cmd`. The dry run uses the same values from the command-line options. (best practice) [sources: src/devops_cli/commands/k8s/stack_lifecycle.py:571, src/devops_cli/commands/k8s/stack_lifecycle.py:1355]
  - Chosen: Include `--wait` and `--timeout` when `wait` is true. The real run includes them. The dry run must match the real run's requests.
  - Rejected: Omit them for brevity. The dry-run rule requires the full request. Omitting flags makes the dry run differ from the real run. Rejected.
- **Does the dry run include the `--kube-context` flag?**: Yes, when a context is resolved. The real run appends `--kube-context ` to every helm command. The dry run includes it in the same position. (best practice) [sources: src/devops_cli/commands/k8s/stack_lifecycle.py:1340]
  - Chosen: Include `--kube-context` when a context is set. The real run includes it. The dry run must match.
  - Rejected: Omit it. The dry-run rule requires the full request. Rejected.

### Fit
Fits in one pull request.

### Suspected block
None.

### Dependencies
None.
<!-- devops-roadmap-refine:end -->

<!-- devops-roadmap-record {"Effort": "Low", "Owner": "Service", "Priority": "P2-Medium", "Status": "Blocked", "Value": "Medium", "implement.branch": "fix/2469-deploy-stack-dry-run-lists-the", "implement.job": "devops-cli-runner-20261101-143830-72d1", "implement.job_digest": "sha256:04d655904252706a7321aed38fa5cafd293625c5db469f252f57163a7c463f16", "implement.job_state": null, "implement.pr": "2991", "implement.spend": "{\"requests\": 62, \"input_tokens\": 3443348, \"output_tokens\": 23789}", "implement.stopped": "group 1", "refine.block_paths": null, "refine.blocked_by": null, "refine.body_hash": "bee99f203d9ab13caafac5351301230f0e62bd4f8eeff4ff48cdf75adbe8e248", "refine.failed_body_hash": null, "refine.needs_split": "false", "refine.next_step": "ready", "refine.section_hash": "faadd81fa60db490c96a4677fa9a815fe940d1e5b6617836282e877b0cb3840d", "stage.branch": "fix/2469-deploy-stack-dry-run-lists-the", "stage.file_cap": null, "stage.groups": "[[\"Add helm_commands to the dry-run output\", 5688], [\"Update test to read from dry-run output\", 5483]]", "stage.needs_split": null, "stage.pr": "2991", "stage.sha": "2402b85c9d945b5cb2ca5eabbeae2b6b4d30e224"} -->
