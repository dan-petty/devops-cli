## ADDED Requirements

### Requirement: Row 10 keeps each live rule and stricter threshold
Row 10 of `devops repos onboard` SHALL keep each rule of the live ruleset. For a rule that the baseline also holds, it SHALL keep each live parameter whose value is stricter than the baseline value or that its comparison table does not rank, and it SHALL write the baseline value only where the live value is weaker.

#### Scenario: Live coverage rule kept
- **WHEN** the live `main` ruleset holds the `code_coverage` rule with `minimum_coverage` set to 90 and the baseline holds no `code_coverage` rule
- **THEN** the merged ruleset body holds the `code_coverage` rule with `minimum_coverage` set to 90.

#### Scenario: Higher coverage minimum kept
- **WHEN** the live `code_coverage` rule has `minimum_coverage` set to 90 and the baseline has `minimum_coverage` set to 80
- **THEN** the merged ruleset body holds `minimum_coverage` set to 90.

#### Scenario: Warnings kept over errors
- **WHEN** the live `code_quality` rule has `severity` set to `warnings` and the baseline has `errors`
- **THEN** the merged ruleset body holds `severity` set to `warnings`.

#### Scenario: Medium CodeQL threshold kept
- **WHEN** the live `code_scanning` rule holds a CodeQL tool with `security_alerts_threshold` set to `medium_or_higher` and the baseline holds `high_or_higher`
- **THEN** the merged ruleset body holds the CodeQL tool with `security_alerts_threshold` set to `medium_or_higher`.

#### Scenario: Review thread resolution kept
- **WHEN** the live `pull_request` rule has `required_review_thread_resolution` set to `true` and the baseline has `false`
- **THEN** the merged ruleset body holds `required_review_thread_resolution` set to `true`.

### Requirement: Row 10 keeps each live required check
Row 10 SHALL keep each required check entry of the live ruleset. It SHALL add each required check of the baseline, of the settings file of the default branch, and of the checks that reported on the template pull request.

#### Scenario: Live required checks rule kept
- **WHEN** the live `main` ruleset holds a `required_status_checks` rule with the check `Lint` and `strict_required_status_checks_policy` set to `true`, the baseline holds no `required_status_checks` rule, and the settings file of the default branch sets no parameter of that rule
- **THEN** the merged ruleset body holds the `required_status_checks` rule with the check `Lint` and `strict_required_status_checks_policy` set to `true`.

#### Scenario: A live check entry kept
- **WHEN** the live required checks rule requires the check `Lint` and the baseline required checks rule requires the check `Typecheck`
- **THEN** the merged ruleset body requires the checks `Lint` and `Typecheck`.

### Requirement: Row 10 ranks each live parameter of the required checks rule
Row 10 SHALL compare each live parameter of the required checks rule with the baseline value by the same rank table as the parameter of any other rule. It SHALL keep a live parameter that is stricter or that the table does not rank, and it SHALL write the baseline value where the live value is weaker. The required checks rule of the settings file of the default branch SHALL win for each parameter that it sets.

#### Scenario: A weaker live parameter takes the baseline value
- **WHEN** the live required checks rule sets `strict_required_status_checks_policy` to `false`, the baseline sets it to `true`, and the settings file of the default branch sets no parameter of that rule
- **THEN** the merged ruleset body sets `strict_required_status_checks_policy` to `true`.

#### Scenario: The repository file wins a live parameter
- **WHEN** the live required checks rule sets `strict_required_status_checks_policy` to `true` and the required checks rule of the settings file of the default branch sets it to `false`
- **THEN** the merged ruleset body sets `strict_required_status_checks_policy` to `false`, and the row sends one ruleset write.

### Requirement: Row 10 names each live setting that it keeps
Row 10 SHALL write one warning line that names the rule and the parameter of each live rule and each live parameter that it keeps because the baseline does not hold it or holds a weaker value. It SHALL write no warning line for a required check, because its change line names each required check; a kept live parameter of the required checks rule gets a warning line as any other kept parameter. It SHALL exit 0.

#### Scenario: Warning names the coverage rule
- **WHEN** the live `main` ruleset holds the `code_coverage` rule with `minimum_coverage` set to 90 and the baseline holds no `code_coverage` rule
- **THEN** the output holds one warning line that names `code_coverage` and `minimum_coverage`, the row is `present`, and the command exits 0.

#### Scenario: An unranked parameter stays
- **WHEN** the live `main` ruleset holds a rule parameter that the comparison table does not rank and the baseline does not hold it
- **THEN** the merged ruleset body holds the live parameter, and the output holds one warning line that names the rule and the parameter.

#### Scenario: Equal rulesets give no warning
- **WHEN** the live `main` ruleset equals the baseline ruleset
- **THEN** the output holds no warning line, the row is `present`, and the run sends no ruleset write.

#### Scenario: The required checks rule takes no warning
- **WHEN** the live `main` ruleset requires the check `PR title / Semantic PR title` and the baseline does not require it
- **THEN** the merged ruleset body requires that check, no warning line names the required checks rule, and the row is `present`.

### Requirement: Row 10 adds each baseline rule and check that the live ruleset lacks
Row 10 SHALL add each rule of the baseline ruleset, each parameter of a baseline rule, and each required check of the baseline that the live ruleset does not hold.

#### Scenario: Baseline required check added
- **WHEN** the baseline `main` ruleset requires the check `Lint` and the live ruleset does not require it
- **THEN** the merged ruleset body requires the check `Lint`.
