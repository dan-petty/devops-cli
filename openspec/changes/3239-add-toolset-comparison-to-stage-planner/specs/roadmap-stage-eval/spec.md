## ADDED Requirements

### Requirement: The eval stage command takes a toolset
`devops roadmap eval stage` SHALL accept `--toolset <name>` with a value of the stage toolset setting, SHALL plan each case with that toolset, and SHALL name the toolset in its report.

#### Scenario: One toolset named in the report
- **WHEN** A test scores one case with `--toolset base` and a fake stage client.
- **THEN** The command exits 0 and its report names `base`.

### Requirement: The compare form runs each toolset on the same cases
`devops roadmap eval stage compare <toolset>...` SHALL run every named toolset on the same cases and SHALL print one table with one row for each toolset.

#### Scenario: Two toolsets in one table
- **WHEN** A test runs `devops roadmap eval stage compare base extended` with a fake stage client.
- **THEN** The output holds one row for `base` and one for `extended`, with the columns for gate defects, verification defects, tool calls, requests, input tokens, output tokens, elapsed time and cost.

### Requirement: The comparison states the runs and the spread
The comparison SHALL run each case `--runs` times, three by default, and SHALL state the number of runs and the minimum and the maximum of each measured value.

#### Scenario: Three runs with different replies
- **WHEN** A test compares toolsets with `--runs 3` and a fake client that returns different token counts on each run.
- **THEN** The report states three runs for each case and the minimum and the maximum of its input and output tokens.

### Requirement: The comparison reports the verification pass
The comparison SHALL report the defects that the verification pass catches for each toolset when `--verify` is given, and SHALL report `not run` in that column when it is not.

#### Scenario: No verification pass
- **WHEN** A test compares toolsets with no `--verify`.
- **THEN** The verification column of each row holds `not run` and the command exits 0.

### Requirement: The comparison prints one delta line for each measured column
The comparison SHALL print one delta line for each measured column as the value of the toolset less the value of the first toolset, and SHALL keep the raw values in the table.

#### Scenario: Delta to the first toolset
- **WHEN** A test compares the first toolset and a second one with known values.
- **THEN** The delta line of each column holds the value of the second toolset less the value of the first, and the table keeps the raw values.

### Requirement: The comparison prices a row from the pricing registry
The comparison SHALL price the input and output tokens of each row with the pricing registry of the AI spend data and SHALL print `unpriced` for a model that the registry holds no price for.

#### Scenario: Known token counts
- **WHEN** A test compares toolsets with known token counts and a known price for the model.
- **THEN** The cost of each row is the price of its input and output tokens.

### Requirement: The compare dry run states the cases, the runs and the cost
`devops roadmap eval stage compare` SHALL state the cases, the runs, the toolsets and the estimated cost on `--dry-run` and SHALL make no model call.

#### Scenario: Dry run with no model call
- **WHEN** A test runs the comparison with `--dry-run` and a fake client that fails on any call.
- **THEN** The command exits 0, prints the case count, the run count, both toolset names and an estimated cost, and makes no call.

### Requirement: The comparison loads the staged-item replay cases
The comparison SHALL load the golden cases and the staged-item replay cases in the same case format and SHALL run each of them.

#### Scenario: One golden case and one staged-item case
- **WHEN** A test compares toolsets over a golden directory and a staged-item directory that hold one case each.
- **THEN** The report names both cases.

### Requirement: The MCP server publishes no tool for the eval stage command
The MCP exposure table SHALL hold no entry for `devops roadmap eval stage`, so the MCP server publishes no tool for it, and a test SHALL pin that the command path resolves in the command tree and that the server publishes no tool for it.

#### Scenario: The eval stage command stays excluded
- **WHEN** A test resolves the path of `devops roadmap eval stage` in the command tree and asks the MCP server for its tool.
- **THEN** The path resolves to a command, and the server returns no tool for it.
