## ADDED Requirements

### Requirement: A read-only tool publishes no option that writes
A tool that the exposure table marks read-only SHALL publish no option whose description holds `resolve`, `write`, `delete` or `create` as a whole word, in its base, `-s` or `-ing` form and in any letter case. A past form such as `resolved` SHALL NOT count.

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
The tools `pr_check_readiness`, `roadmap_refine` and `tf_plan` SHALL be marked not read-only, and SHALL publish the option `auto_resolve`, `confirm` and `out` respectively. The command `devops pr check-readiness` SHALL keep the option `--auto-resolve`.

#### Scenario: The readiness tool
- **WHEN** A test reads the published tool `pr_check_readiness`
- **THEN** Its read-only flag is false, and its schema holds `auto_resolve`.

#### Scenario: The refine and plan tools
- **WHEN** A test reads the published tools `roadmap_refine` and `tf_plan`
- **THEN** Both read-only flags are false, and the schemas hold `confirm` and `out`.

#### Scenario: The readiness command
- **WHEN** A test reads the options of `devops pr check-readiness`
- **THEN** The options include `--auto-resolve`.

### Requirement: The injection scan tool publishes no SARIF option
The tool `scan_injection` SHALL be marked read-only and SHALL publish no `sarif` option. The command `devops scan injection` SHALL keep the option `--sarif`.

#### Scenario: The published injection scan tool
- **WHEN** A test reads the published tool `scan_injection`
- **THEN** Its read-only flag is true, and its schema holds no `sarif` property.

#### Scenario: The injection scan command
- **WHEN** A test reads the options of `devops scan injection`
- **THEN** The options include `--sarif`.
