# agent-scan-tools Specification

## Purpose
How the scan tools that devops-cli gives to its agents and MCP clients run the scanner adapters, and how each reply reports the outcome of the scan, so that a missing or failed scan never reads as a clean scan.

## Requirements

### Requirement: An agent scan tool runs the scanner adapter over the workspace path
The agent tools `scan_trivy`, `scan_kubelinter`, `scan_pluto`, `scan_bandit`, `scan_gitleaks` and `scan_semgrep` SHALL run the scanner adapter of `devops_cli.security` over their target, a path inside the workspace, and SHALL keep no command line of their own.

#### Scenario: The Semgrep tool runs the scan of the adapter
- **WHEN** the agent calls `scan_semgrep` over a directory with the config `./local-rules`
- **THEN** Semgrep starts in that directory with `./local-rules` and the rule pack, sends no metrics, checks no version, and leaves out the directories of dependencies and data

#### Scenario: The Semgrep tool reads the cached registry ruleset
- **WHEN** the cached `p/default` exists, and the agent calls `scan_semgrep` over a directory with no config
- **THEN** Semgrep starts in the cache directory with the cached file named there, and the reply is `Semgrep scan status: ok`, then `No findings.`

### Requirement: The reply gives the status of the scan first
The reply of an agent scan tool SHALL start with the line `<scanner> scan status: <status>`. The status SHALL be `ok` for a scan that ran, `not installed` for a scanner that no directory of PATH holds, and the name of the outcome status for every other outcome, such as `failed`, `not_applicable` or `coverage_gap`. When the outcome has a reason, the next line SHALL be `Reason: <reason>`.

#### Scenario: Semgrep with no cached registry ruleset
- **WHEN** no cached `p/default` exists, and the agent calls `scan_semgrep` over a directory with no config
- **THEN** Semgrep runs the rule pack alone, and the reply is `Semgrep scan status: coverage_gap`, then a reason that names `devops review rules fetch --ruleset p/default`, then `No findings.`

### Requirement: The reply of a scan that gave no result says so
When the outcome status is in `CONST_SCAN_NO_RESULT_STATUSES`, the last line of the reply SHALL be `The scan gave no result. Do not report the target as clean.`, and the reply SHALL list no findings.

#### Scenario: A scanner that is not installed
- **WHEN** no directory of PATH holds the scanner of the tool, and the agent calls the tool
- **THEN** the reply is `<scanner> scan status: not installed`, then `Reason: Binary '<program>' not found on PATH`, then `The scan gave no result. Do not report the target as clean.`

#### Scenario: A scanner that fails with no output
- **WHEN** the scanner exits with code 2, writes nothing on stdout, and writes `fatal: the target cannot be read` on stderr
- **THEN** the reply is `<scanner> scan status: failed`, then `Reason: Scanner exited with code 2: fatal: the target cannot be read`, then `The scan gave no result. Do not report the target as clean.`

### Requirement: The reply lists the findings of a scan that ran, masked and cut
After the status, the reply of a scan that ran SHALL give the line `Findings (<count>):` and then one line `- [<severity>] <location>: <title> (<fix>)` for each finding, or SHALL give the line `No findings.` The tool SHALL mask the whole reply with `mask_secrets`, and SHALL then cut it at `DEFAULT_TOOL_DIFF_MAX_CHARS` characters, with a last line that gives the limit.

#### Scenario: A scan that finds nothing
- **WHEN** Bandit or Gitleaks runs and reports no finding
- **THEN** the reply is `<scanner> scan status: ok`, then `No findings.`

#### Scenario: A finding that holds a secret
- **WHEN** Trivy reports a vulnerability and a secret whose title holds a GitHub token
- **THEN** the reply is `Trivy scan status: ok`, then `Findings (2):`, then one line for each finding, and the token reads `<masked-github-token>`

#### Scenario: A long reply
- **WHEN** Trivy reports 200 vulnerabilities
- **THEN** the reply is the first `DEFAULT_TOOL_DIFF_MAX_CHARS` characters of the whole reply, then the line `... [truncated at <limit> chars]`

### Requirement: A scan command reports a scan that gave no result as not run
`devops scan trivy`, `devops scan sast` and `devops scan secrets` SHALL report a scan whose outcome status is in `CONST_SCAN_NO_RESULT_STATUSES` as not run, with its reason, and SHALL NOT say that the scan passed. The MCP tools `scan_trivy`, `scan_sast` and `scan_secrets` run these commands. The JSON and YAML output of these commands SHALL hold the status and the reason of the scan next to the findings, and a scan that gave no result SHALL NOT print only an empty findings list.

#### Scenario: Gitleaks is not installed
- **WHEN** no directory of PATH holds Gitleaks, and `devops scan secrets <directory>` runs
- **THEN** the command exits 0, and its last line is `! Gitleaks was not run (Binary 'gitleaks' not found on PATH).`

#### Scenario: Gitleaks is not installed with JSON output
- **WHEN** no directory of PATH holds Gitleaks, and `devops scan secrets <directory> --json` runs
- **THEN** the command exits 0, and the JSON output is a dictionary with `status` `"not installed"`, `reason` `"Binary 'gitleaks' not found on PATH"`, and `findings` `[]`

#### Scenario: Clean scan with JSON output
- **WHEN** Semgrep runs and finds no flaws, and `devops scan sast <directory> --json` runs
- **THEN** the command exits 0, and the JSON output is a dictionary with `status` `"ran"`, `reason` `""`, and `findings` `[]`

### Requirement: The MCP Semgrep tool uses the default ruleset unless the caller names one
The MCP tool `scan_sast` SHALL scan with `DEFAULT_SEMGREP_CONFIG` when the caller names no config, and with the config that the caller names otherwise.

#### Scenario: The default ruleset and a named ruleset
- **WHEN** the cached `p/default` exists, and an MCP client calls `scan_sast` once with no config and once with the config `./rules`
- **THEN** the first Semgrep run names the cached file of `p/default` as its config, and the second run names `./rules`

### Requirement: The Popeye tool runs the Popeye adapter over the namespace
The agent tool `scan_popeye` SHALL run the Popeye adapter of `devops_cli.security` over the namespace that the agent names, or over every namespace when the agent names none. Popeye SHALL start in a new empty directory, in the sandbox with the network profile `kube-api`. The tool SHALL keep no command line of its own, and SHALL reply as the other agent scan tools reply.

#### Scenario: Popeye finds issues in a namespace
- **WHEN** the agent calls `scan_popeye("argocd")`, and Popeye reports six issues at warn and error level
- **THEN** Popeye starts in an empty directory with `popeye -o json -l warn -n argocd`, and the reply is `Popeye scan status: ok`, then `Findings (6):`, then one line for each finding

### Requirement: The uv audit tool runs the uv audit adapter over a directory
The agent tool `scan_uv_audit` and the MCP tool `scan_uv_audit` SHALL take only `directory`, a path inside the workspace, and SHALL run the uv audit adapter of `devops_cli.security` there. They SHALL keep no command line of their own, and SHALL reply as the other agent scan tools reply, with the scanner named `uv audit`.

#### Scenario: uv audit finds vulnerabilities
- **WHEN** an agent or an MCP client calls `scan_uv_audit` over a directory, and uv audit reports four vulnerabilities of idna 3.6
- **THEN** uv starts in that directory with `uv audit --frozen --quiet --output-format json`, and the reply is `uv audit scan status: ok`, then `Findings (4):`, then one line for each finding

#### Scenario: uv is not installed
- **WHEN** no directory of PATH holds uv, and the agent calls `scan_uv_audit`
- **THEN** the reply is `uv audit scan status: not installed`, then `Reason: Binary 'uv' not found on PATH`, then `The scan gave no result. Do not report the target as clean.`

#### Scenario: The MCP tool takes only a directory
- **WHEN** an MCP client reads the input schema of `scan_uv_audit`
- **THEN** its only property is `directory`, with the default `.`

#### Scenario: The directory does not exist
- **WHEN** the workspace holds a uv project, and an agent calls `scan_uv_audit` over a path of the workspace where no directory is
- **THEN** uv does not start, and the reply is `uv audit scan status: not_applicable`, then `Reason: <path> is not a directory. uv audit audits the project of a directory.`, then `The scan gave no result. Do not report the target as clean.`

### Requirement: The manifest validation and IaC tools run the pinned adapters
The agent tool `k8s_validate_manifests` SHALL run the kubeconform adapter over its target, a path inside the workspace. The agent tool `scan_iac` SHALL run the Trivy adapter with the scan type `config` over its target. Each SHALL keep no command line of its own, and SHALL reply as the other agent scan tools reply.

#### Scenario: kubeconform is not installed
- **WHEN** no directory of PATH holds kubeconform, and the agent calls `k8s_validate_manifests` over a manifest
- **THEN** the reply is `Kubeconform scan status: not installed`, then `Reason: Binary 'kubeconform' not found on PATH`, then `The scan gave no result. Do not report the target as clean.`

#### Scenario: kubeconform finds invalid resources
- **WHEN** the agent calls `k8s_validate_manifests` over a manifest directory in which kubeconform reports three resources
- **THEN** the reply is `Kubeconform scan status: ok`, then `Findings (3):`, then one line for each finding

#### Scenario: The IaC tool runs Trivy's misconfiguration scan
- **WHEN** the agent calls `scan_iac` over a directory
- **THEN** Trivy starts with `config` over that directory, and the reply starts with `Trivy scan status:`

### Requirement: The Terraform lint tool runs the tflint adapter
The agent tool `tf_lint` SHALL run the tflint adapter over its target, a path inside the workspace. It SHALL keep no command line of its own, and SHALL reply as the other agent scan tools reply. No agent tool SHALL analyze the layers of an image.

#### Scenario: tflint is not installed
- **WHEN** no directory of PATH holds tflint, and the agent calls `tf_lint` over a directory of the workspace
- **THEN** the reply is `TFLint scan status: not installed`, then `Reason: Binary 'tflint' not found on PATH`, then `The scan gave no result. Do not report the target as clean.`

#### Scenario: tflint finds an issue
- **WHEN** the agent calls `tf_lint` over a directory in which tflint reports one issue
- **THEN** the reply is `TFLint scan status: ok`, then `Findings (1):`, then one line for the finding

#### Scenario: The agent tools are listed
- **WHEN** a test lists the names of the agent tools
- **THEN** no name is `docker_analyze_layers`
