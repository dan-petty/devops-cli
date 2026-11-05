## ADDED Requirements

### Requirement: A read-only tool publishes no option that writes
A tool that the exposure table marks read-only SHALL publish no option whose description holds `resolve`, `write`, `delete` or `create`. The word SHALL count as a whole word in its base, `-s` or `-ing` form and in any letter case. A past form such as `resolved` SHALL NOT count.

#### Scenario: A read-only tool with a writing option
- **WHEN** A test reads the published schema of a read-only tool, and one option description is `Write findings to this path.`
- **THEN** The test reports the tool and the option.

#### Scenario: A tool that is not read-only
- **WHEN** A test reads the published schema of a tool that is not read-only, and one option description is `Automatically resolve review threads.`
- **THEN** The test reports nothing.

#### Scenario: A past form of a write verb
- **WHEN** A test reads the published schema of a read-only tool, and one option description is `Inherited policies are resolved via 'extends'.`
- **THEN** The test reports nothing.

#### Scenario: The published tools
- **WHEN** A test reads the published schema of every tool that the server registers
- **THEN** No read-only tool has an option that the rule reports.

### Requirement: A tool that keeps a writing option is not read-only
The tools `pr_check_readiness`, `roadmap_refine`, `roadmap_run` and `ci` SHALL be marked not read-only. They SHALL publish the options `auto_resolve`, `confirm`, `confirm` and `fix` respectively. The command `devops pr check-readiness` SHALL keep the option `--auto-resolve`.

#### Scenario: The readiness tool
- **WHEN** A test reads the published tool `pr_check_readiness`
- **THEN** Its read-only flag is false, and its schema holds `auto_resolve`.

#### Scenario: The refine, run and ci tools
- **WHEN** A test reads the published tools `roadmap_refine`, `roadmap_run` and `ci`
- **THEN** All three read-only flags are false, and the schemas hold `confirm`, `confirm` and `fix`.

#### Scenario: The readiness command
- **WHEN** A test reads the options of `devops pr check-readiness`
- **THEN** The options include `--auto-resolve`.

### Requirement: A read-only tool publishes no option for a file that its command writes
The tools `scan_injection` and `tf_plan` SHALL be marked read-only. They SHALL publish no `sarif` option and no `out` option. The commands `devops scan injection` and `devops tf plan` SHALL keep the options `--sarif` and `--out`.

#### Scenario: The published injection scan and plan tools
- **WHEN** A test reads the published tools `scan_injection` and `tf_plan`
- **THEN** Both read-only flags are true, and the schemas hold no `sarif` property and no `out` property.

#### Scenario: The injection scan and plan commands
- **WHEN** A test reads the options of `devops scan injection` and `devops tf plan`
- **THEN** The options include `--sarif` and `--out`.
