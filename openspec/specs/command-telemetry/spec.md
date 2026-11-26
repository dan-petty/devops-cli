# command-telemetry Specification

## Purpose
The telemetry that a devops command sends: the command spans with their attributes and events, and the command counter `devops_cli_command_total`.

## Requirements

### Requirement: A usage error records its class and exit code and no message
When a devops command stops on a usage error of Typer, the command span SHALL record the class of the error in `error.type` and the exit code in `cli.exit_code`. No exported span attribute, span event, span status or resource attribute SHALL hold the message of the error.

#### Scenario: An unexpected extra argument
- **WHEN** a person runs `devops config set <key> <value> <extra>`
- **THEN** the command span records the `error.type` `UsageError` and the `cli.exit_code` `2`
- **AND** no exported payload holds `<extra>`

#### Scenario: A command raises a bad parameter
- **WHEN** a person runs `devops ai gateway tune --concurrency <value>` with a value that is not a list of integers
- **THEN** the command span records the `error.type` `BadParameter` and the `cli.exit_code` `2`
- **AND** no exported payload holds `<value>`

### Requirement: A usage error counts as a failed command
`devops_cli_command_total` SHALL count a command that stops on a usage error of Typer one time, with the status `error`.

#### Scenario: An unexpected extra argument is counted
- **WHEN** a person runs `devops config set <key> <value> <extra>`
- **THEN** `devops_cli_command_total` has one point with the `command` `config` and the `status` `error`

### Requirement: A usage error shows the error box of Typer
A command that stops on a usage error SHALL show the error box of Typer with the message of the error, and SHALL exit with the exit code of the error.

#### Scenario: The person sees the error
- **WHEN** a person runs `devops config set <key> <value> <extra>`
- **THEN** the output shows the error box of Typer with `Got unexpected extra argument`
- **AND** the command exits with the code `2`

### Requirement: A command span holds no process.command_line
Each command span SHALL hold the name of its command in `cli.command`, and SHALL hold no `process.command_line`. The span of the command that runs SHALL hold its command path in `cli.command_path`.

#### Scenario: A person runs a command of a command group
- **WHEN** a person runs `devops <group> set <key> <value>` with telemetry export on
- **THEN** the span `cli.<group>` holds the `cli.command` `<group>`, and the span `cli.set` holds the `cli.command` `set` and the `cli.command_path` `devops <group> set`
- **AND** neither span holds `process.command_line`

### Requirement: The profile span names the profiled command and holds no argument value
The `telemetry.profile` span of `devops telemetry profile` SHALL hold the command path of the profiled command in `cli.command_path` and the number of its words that are not command names in `cli.args_count`. The span SHALL hold no `command.line` and no argument value, also while `telemetry.capture_command_args` is on. While the setting is on, the subprocess span under the profile span SHALL hold the arguments of the profiled command in `process.command_args`.

#### Scenario: A credential in the profiled command line
- **WHEN** a person runs `devops telemetry profile "devops config set cloudflare.tunnel_token <credential>"` with telemetry export on and the default settings
- **THEN** the `telemetry.profile` span holds `cli.command_path` `devops config set` and `cli.args_count` 2
- **AND** the span holds no `command.line`
- **AND** no exported payload holds the credential

#### Scenario: The person turns on the arguments
- **WHEN** `telemetry.capture_command_args` is true and a person profiles the same command line
- **THEN** the `telemetry.profile` span holds no argument value
- **AND** the subprocess span under the profile span holds the arguments of the profiled command in `process.command_args`

### Requirement: Warning and error logs are exported via OTLP with trace correlation
When telemetry is enabled, log records of level WARNING and above SHALL be exported to the collector's `/v1/logs` endpoint carrying the active `trace_id` and `span_id`. No exported log payload SHALL contain prompt or reply text.

#### Scenario: A warning is logged during command execution
- **WHEN** a command executes an active trace span and emits a warning log
- **THEN** the log record is exported to `/v1/logs` with `severityText` `WARN`
- **AND** the log record carries the active `traceId` and `spanId`
- **AND** the payload contains no prompt or reply preview text

#### Scenario: A failed command logs an error with trace context
- **WHEN** a command fails with an unhandled exception
- **THEN** an error log is exported to `/v1/logs` with `severityText` `ERROR`
- **AND** the log record carries the active `traceId` and `spanId`

### Requirement: devops-cli dashboard includes an error stream panel
The `k8s/devops/dashboards/devops-cli.json` dashboard SHALL include a logs panel that shows the log records of `devops-cli` in Loki at the levels error, critical and fatal, and no warnings.

#### Scenario: Error stream panel is present in the dashboard
- **WHEN** the panels of `devops-cli.json` are read
- **THEN** one panel of type `logs` has the title "Errors: error logs of devops-cli"
- **AND** the panel targets the `loki` datasource with the query `{service_name="devops-cli"} | detected_level=~"error|critical|fatal"`

### Requirement: A command that reports its own failure counts once and records its exit code
When a delegated devops command reports its own failure and exits with a non-zero code, `devops_cli_command_total` SHALL count the command one time with the status `error`. The command span SHALL record that code in `cli.exit_code` and the status `error` in `cli.status`. `devops` SHALL exit with that code and SHALL log no record for the exit.

#### Scenario: A command prints its error and exits 2
- **WHEN** a delegated command prints its error and exits with the code 2
- **THEN** `devops_cli_command_total` has one point with the `command` of the command and the `status` `error`
- **AND** the command span records the `cli.exit_code` `2` and the `cli.status` `error`
- **AND** `devops` exits with the code 2, and logs no record for the exit

### Requirement: The sub-command histogram names the command group and the sub-command
`devops_cli_subcommand_duration_seconds` SHALL hold the command group in the label `command`, the command path below `devops` in the label `sub_command`, and `ok` or `error` in the label `status`. A command with no command group above it SHALL name itself in `command` and `sub_command`.

#### Scenario: A sub-command of a command group
- **WHEN** a person runs `devops <group> set <key> <value>` with telemetry export on
- **THEN** `devops_cli_subcommand_duration_seconds` has one point with the `command` `<group>`, the `sub_command` `<group> set` and the `status` `ok`

#### Scenario: A command with no group
- **WHEN** a command `alone` runs with no command group above it
- **THEN** `devops_cli_subcommand_duration_seconds` has one point with the `command` `alone` and the `sub_command` `alone`

### Requirement: A span starts without VCS attributes when the working directory is gone
The telemetry client SHALL start a span, with no `vcs.*` attribute and no exception, when the working directory of the process no longer exists. When the working directory exists and lies inside a git repository, the span SHALL hold the branch and the revision of that repository in its `vcs.*` attributes.

#### Scenario: The working directory was removed
- **WHEN** the working directory of the process is removed and a client starts a span
- **THEN** the span starts and holds no `vcs.ref.name`, `vcs.branch`, `vcs.revision_id` and `vcs.commit` attribute

#### Scenario: The working directory is inside a git repository
- **WHEN** the working directory holds a `.git` directory whose `HEAD` names a branch and whose branch file holds a revision, and a client starts a span
- **THEN** the span holds that branch in `vcs.ref.name` and `vcs.branch`, and that revision in `vcs.revision_id` and `vcs.commit`

### Requirement: The devops-cli dashboard filters by job
The dashboard `k8s/devops/dashboards/devops-cli.json` SHALL have the multi-value query variable `job`, with All, as its first variable. It SHALL read its values with `label_values({__name__=~"devops_cli_command_total|devops_cli_github_requests_total"}, job)`. Each Prometheus query of the dashboard SHALL filter each `devops_cli_*` series with the matcher `job=~"$job"` first in its selector.

#### Scenario: The job variable is a query
- **WHEN** the dashboard file is read
- **THEN** the first variable is `job`, a query variable of the Prometheus datasource with Multi-value and All, and it holds no fixed options

#### Scenario: The job variable reads a series that the Service sends as it works
- **WHEN** the query of the variable `job` is read
- **THEN** its selector holds `devops_cli_command_total` and `devops_cli_github_requests_total`

#### Scenario: Each query filters by job
- **WHEN** each Prometheus query of the dashboard file is read
- **THEN** each `devops_cli_*` series in the query has a selector that starts with `job=~"$job"`

### Requirement: A devops-cli pod names its cluster and its namespace
Each devops-cli container in the render of `k8s/devops` SHALL set `K8S_CONTEXT` to one cluster name, the same in each container, and `POD_NAMESPACE` to the namespace of its object. The tracer SHALL put the value of `K8S_CONTEXT` in the resource attribute `k8s.cluster.name` and the value of `POD_NAMESPACE` in the span attribute `k8s.namespace.name`.

#### Scenario: The manifests are rendered
- **WHEN** `kubectl kustomize k8s/devops` renders the Deployments, the CronJobs and the WorkflowTemplates
- **THEN** each devops-cli container sets `K8S_CONTEXT` to the same cluster name, and `POD_NAMESPACE` from the Downward API, or as the plain value `devops` in the runner template

#### Scenario: A pod starts a span
- **WHEN** `K8S_CONTEXT` and `POD_NAMESPACE` are set and a span starts
- **THEN** the resource holds `k8s.cluster.name` with the value of `K8S_CONTEXT`, and the span holds `k8s.namespace.name` with the value of `POD_NAMESPACE`

### Requirement: Each usage error leaves one record of its kind and names
The root group of the CLI SHALL record each usage error, also of a help query, a dry run and an MCP tool call, as one line of `usage-errors.jsonl` under the user data root, one `cli_usage_error` log record and one point of `devops_cli_usage_error_total`. The record SHALL hold the kind, the command path below `devops`, the typed name, Click's suggestion, the caller, the agent tool and the version.

#### Scenario: An unknown command word
- **WHEN** a person runs `devops gh prr list`
- **THEN** the ledger has one line with the kind `unknown_command`, the command path `gh`, the name `prr` and the suggestion `pr`

#### Scenario: An unknown option
- **WHEN** a person runs `devops pr view 1 --repoo`
- **THEN** the ledger has one line with the kind `unknown_option`, the command path `pr view`, the name `--repoo` and the suggestion `--repo`

#### Scenario: A help query and a dry run
- **WHEN** a person runs `devops gh prr --help` or `devops --dry-run gh prr list`
- **THEN** the ledger has one line with the kind `unknown_command`

#### Scenario: An MCP tool call
- **WHEN** the MCP dispatcher runs `devops gh prr list`
- **THEN** the ledger line has the caller `mcp`

### Requirement: A usage-error record holds no argument value
A usage-error record SHALL hold names only. A word that is not in the form of a CLI name SHALL be recorded as `<value>`. No ledger line, log record or counter label SHALL hold the message of the error, an argument value or the command line. The counter SHALL have the labels `kind`, `command_path` and `caller` only.

#### Scenario: A token in the place of a command word
- **WHEN** a person runs `devops gh <token> list`
- **THEN** the ledger line has the name `<value>`
- **AND** no ledger line, log record or counter label holds the token

#### Scenario: A value of an option that is not a number
- **WHEN** a person runs `devops pr list --limit <value>`
- **THEN** the ledger line has the kind `bad_value` and the name `limit`
- **AND** no sink holds `<value>`

### Requirement: The record does not change the error that the caller sees
A command that stops on a usage error SHALL show the same error box of Typer and exit with code 2, with no text of the record. When the ledger cannot be written, the command SHALL show one warning and still exit with code 2. The setting `telemetry.usage_ledger` set to false SHALL stop the ledger.

#### Scenario: The error box stays the same
- **WHEN** a person runs `devops gh prr list`
- **THEN** the output is the error box of Typer that names `pr`, and the exit code is 2

#### Scenario: The ledger cannot be written
- **WHEN** the user data root is a file and a person runs `devops gh prr list`
- **THEN** the output holds one warning about the ledger, and the exit code is 2

### Requirement: The environment names the caller of a usage error
The caller of a usage-error record SHALL be `mcp` for an MCP tool call, else `agent` when `detect_agent` finds an agent marker such as `AI_AGENT`, else `ci` when `CI` or `GITHUB_ACTIONS` is set, else `person`. The agent tool SHALL come from the agent name, and the implement job SHALL set `AI_AGENT=devops-implement`.

#### Scenario: An agent runs the command
- **WHEN** `AI_AGENT` is `claude-code_2-1-322_agent` and the command stops on a usage error
- **THEN** the ledger line has the caller `agent` and the agent tool `claude_code`

#### Scenario: A person runs the command
- **WHEN** no agent, CI or MCP marker is set
- **THEN** the ledger line has the caller `person` and no agent tool

### Requirement: The devops-cli dashboard lists each sub-command of its series in one table
The `command` variable of `k8s/devops/dashboards/devops-cli.json` SHALL read its values with `label_values(devops_cli_command_total{job=~"$job"}, command)`. The multi-value variable `sub_command`, with All, SHALL read its values with `label_values(devops_cli_subcommand_duration_seconds{job=~"$job",command=~"$command"}, sub_command)`. The row "Sub-commands" SHALL hold one table and no panel that repeats.

#### Scenario: The variables are queries
- **WHEN** the dashboard file is read
- **THEN** `command` and `sub_command` are query variables of the Prometheus datasource with Multi-value and All, and hold no fixed options

#### Scenario: The sub-command row is one table
- **WHEN** the dashboard file is read
- **THEN** the row "Sub-commands" holds one panel of type `table` with no repeat
- **AND** each query of the table is instant and filters `devops_cli_subcommand_duration_seconds` by `$job`, `$command` and `$sub_command`

### Requirement: The metric Resource holds only stable attributes
The metric Resource SHALL hold only service.name, service.namespace, service.instance.id, os.type and the attributes under telemetry.sdk, and SHALL hold no host.name, also when OTEL_RESOURCE_ATTRIBUTES sets other keys.

#### Scenario: Two tracers with one instance send equal metric Resources
- **WHEN** Two tracers start with different platform.node() values, and OTEL_RESOURCE_ATTRIBUTES sets the same service.instance.id and the host.name and k8s.pod.name of each pod.
- **THEN** Their metric Resources are equal, and no key of a metric Resource lies outside the allowed set.

#### Scenario: A span still names its host
- **WHEN** A tracer with a host name starts a span and records a counter.
- **THEN** The span Resource holds host.name, and the metric Resource holds no host.name.

### Requirement: The metric Resource reads the configured instance
The metric Resource SHALL take service.instance.id from OTEL_RESOURCE_ATTRIBUTES when that variable sets it, and from the host name when it does not.

#### Scenario: A Job pod sets one instance for its workload
- **WHEN** A tracer starts with OTEL_RESOURCE_ATTRIBUTES set to service.instance.id=devops-cli-job.
- **THEN** The metric Resource holds service.instance.id=devops-cli-job.

#### Scenario: A workstation names its host as the instance
- **WHEN** A tracer starts with no OTEL_RESOURCE_ATTRIBUTES on a host with a known name.
- **THEN** The metric Resource equals service.name, service.instance.id with the host name, os.type, telemetry.sdk.name and telemetry.sdk.language, and holds no host.name.

### Requirement: Both CronJob templates name one runner instance
Both CronJob templates SHALL set OTEL_RESOURCE_ATTRIBUTES to service.instance.id=devops-cli-job.

#### Scenario: Each CronJob container names the runner instance
- **WHEN** The runtime test reads the container environment of the two CronJob templates.
- **THEN** Each container sets OTEL_RESOURCE_ATTRIBUTES to service.instance.id=devops-cli-job.

### Requirement: A group body sends the sub-command histogram point
A command group that runs its own body with no sub-command SHALL send one point to `devops_cli_subcommand_duration_seconds`, with the group in `command` and in `sub_command` and `ok` or `error` in `status`. A run with a sub-command SHALL send one point from that sub-command, and the group body SHALL send none.

#### Scenario: A group with no sub-command
- **WHEN** `devops ci` runs its body
- **THEN** the histogram has one point with `command` `ci`, `sub_command` `ci` and `status` `ok`

#### Scenario: A group with a sub-command
- **WHEN** `devops ci test path` runs
- **THEN** the histogram has one point with `command` `ci` and `sub_command` `ci test path`

#### Scenario: A group body that fails
- **WHEN** the body of `devops gh` exits 1
- **THEN** its point holds `status` `error`

### Requirement: Usage errors print one hint line for known wrong commands and flags
When a CLI command fails with a Click usage error that matches an entry in `usage_hints.yaml`, asks to list CI rows (`devops ci list` or `devops ci --list`), or matches another command path by exact word or hyphen/underscore split across the command tree, the CLI SHALL print one hint line after Click's error box, run no command, and still exit with code 2.

#### Scenario: By-design command removal shows policy hint
- **WHEN** a user runs `devops pr merge 1` or `devops gh pr merge 1`
- **THEN** the CLI exits with code 2, prints Click's error box, and prints one hint line stating that only a person merges a pull request

#### Scenario: Known command synonyms suggest the real command
- **WHEN** a user runs `devops roadmap show 1` or `devops pr show 1`
- **THEN** the CLI exits with code 2 and prints a hint naming `devops roadmap explain <n>` or `devops pr view <n>` respectively

#### Scenario: External tool commands point to both tools
- **WHEN** a user runs `devops openspec validate` or `devops openspec list`
- **THEN** the CLI exits with code 2 and prints a hint naming both the OpenSpec CLI command and `devops openspec check`

#### Scenario: Listing CI gate rows prints CHECK_ROW_NAMES
- **WHEN** a user runs `devops ci list` or `devops ci --list`
- **THEN** the CLI exits with code 2 and prints every row name from `CHECK_ROW_NAMES` on one line

#### Scenario: Interim gh flags point to devops gh api endpoints
- **WHEN** a user runs `devops gh issue view 1 --json number` or `devops pr comment 1`
- **THEN** the CLI exits with code 2 and prints the corresponding `devops gh api` command hint

#### Scenario: Cross-group lookup resolves split words without prefix matching
- **WHEN** a user runs `devops ai cost-report`
- **THEN** the CLI prints `Did you mean: devops ai cost report` and exits with code 2
- **AND** a partial prefix such as `devops ai repo` does not emit a cross-group hint

### Requirement: Option errors omit help options, list small option sets, and show missing-option help
An unknown-option error SHALL exclude `--help` and `-h` from `Possible options`. When no close match remains after exclusion and the command defines at most 6 non-help options, Click's error line SHALL list every non-help option of that command. A `Missing option` error SHALL include the option's help string on the error line.

#### Scenario: Unknown option omits --help and lists small command option sets
- **WHEN** a user runs `devops gh issue view 1 --hel` or `devops gh issue view 1 --bogus`
- **THEN** `--help` and `-h` are absent from `Possible options`
- **AND** `--repo` appears in `Possible options` because `gh issue view` defines at most 6 options

#### Scenario: Missing option includes its help text
- **WHEN** a user runs `devops pr describe 1` without `--summary`
- **THEN** Click's `Missing option` error line includes the help string of `--summary`

### Requirement: Usage error telemetry records whether a hint was shown
`UsageErrorRecord`, the usage ledger JSONL entry, and the `cli_usage_error` log record (`usage.hinted`) SHALL include a boolean `hinted` field that is `true` when an extra hint line matched and `false` otherwise.

#### Scenario: Telemetry records hinted status accurately
- **WHEN** `devops pr merge 1` fails with a hint and `devops gh prr list` fails without an extra hint
- **THEN** the ledger record and `usage.hinted` log attribute are `true` for `pr merge` and `false` for `gh prr`
