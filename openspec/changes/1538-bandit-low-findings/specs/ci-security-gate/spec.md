## Purpose

What the security row of `devops ci` scans with Bandit, at which severity for each target, which rules the shared `.bandit` skips, and the form that a `# nosec` marker in `src/` takes.

## ADDED Requirements

### Requirement: The security row scans src at low and tests at the chosen threshold
The security row of `devops ci` SHALL run Bandit with `--ini .bandit` over `src/` at low severity and above, and then over `tests/` at the threshold of `devops ci security --severity`, medium by default. The two targets SHALL be the targets that `.bandit` names.

#### Scenario: The gate's Bandit runs
- **WHEN** the security row runs
- **THEN** it starts Bandit over `src` with `--severity-level low`, then over `tests` with `--severity-level medium`, each under `nice` with `--ini .bandit`

#### Scenario: A looser threshold for tests
- **WHEN** a person runs `devops ci security --severity high`
- **THEN** Bandit scans `src` at low and `tests` at high

#### Scenario: The targets follow the config
- **WHEN** `.bandit` is read
- **THEN** its `targets` are the two targets of the security row

### Requirement: The shared config skips the low rules that need no decision
`.bandit` SHALL skip B404, B603, B110 and B112, and no other rule.

#### Scenario: The skipped rules
- **WHEN** `.bandit` is read
- **THEN** its `skips` are B404, B603, B110 and B112

### Requirement: A nosec marker in src names its rule and a reason
Each `# nosec` marker in a Python file under `src/` SHALL name one or more Bandit rule ids and, after a second `#`, a reason.

#### Scenario: A bare marker
- **WHEN** a file under `src/` holds `x = "a"  # nosec`
- **THEN** the marker check reports that line

#### Scenario: A marker with a rule and a reason
- **WHEN** a file under `src/` holds `x = "a"  # nosec B105 # a label, not a credential`
- **THEN** the marker check reports nothing
