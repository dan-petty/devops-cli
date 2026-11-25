# openspec-check Specification

## Purpose
`devops openspec check` runs the OpenSpec gate over a checkout and reports each problem that it finds. In a dry run it lists the `openspec` commands of the gate and runs none of them.

## Requirements

### Requirement: Dry run lists the gate commands

In a dry run, `devops openspec check` SHALL start no process and read no output of a planned process. It SHALL print the `openspec` commands of the gate in the order that the gate runs them, each with the variables that the run sets, and a scratch directory as a named placeholder. It SHALL name the command that runs once for each active change. It SHALL then say that it would run the gate, and exit 0.

#### Scenario: check_in_dry_run_lists_the_commands

- **WHEN** `devops openspec check` runs with `DEVOPS_CLI_DRY_RUN=1` on a tree with no change and no spec
- **THEN** the exit code is 0, the output lists the planned `openspec` commands and then says that the gate would run, the output holds no `not JSON` text, and the process runner starts no process

#### Scenario: the_plan_is_the_commands_the_gate_runs

- **WHEN** the plan is compared with the commands that the gate runs over a tree with no change and no spec
- **THEN** the plan lists the same commands in the same order, and then the `show` command that runs once for each active change

### Requirement: The gate reads the version of the binary that it runs
`devops openspec check` SHALL run `openspec --version` before its other checks and SHALL report one problem naming the printed version, the locked version, the command path and `npm ci --ignore-scripts` when the printed version differs from the `@fission-ai/openspec` version of the `package-lock.json` at the root of the checkout. When that lockfile is absent or pins no `@fission-ai/openspec`, the gate SHALL report one problem naming the lockfile and the package, and SHALL run no other check.

#### Scenario: An older command replaces the skill advice
- **WHEN** the `openspec` command prints `1.14.3`, the `package-lock.json` of the checkout pins another version, and a committed skill differs from a regeneration
- **THEN** the output holds `1.14.3`, the locked version and `npm ci --ignore-scripts`, holds no `regenerate`, and the gate ran no `openspec update --force`

#### Scenario: The locked command keeps the skill check
- **WHEN** the `openspec` command prints the version that the `package-lock.json` of the checkout pins and a committed skill differs from a regeneration
- **THEN** the output holds the skill path and `uv run devops openspec regenerate`

#### Scenario: The lockfile of the checkout moves the pin
- **WHEN** the `openspec` command prints the version of the old pin and the `package-lock.json` of the checkout pins `9.9.9`
- **THEN** the gate reports one `version` problem that names both versions and `package-lock.json`, and runs no `openspec update --force`

#### Scenario: A checkout with no lockfile
- **WHEN** the checkout has no `package-lock.json`
- **THEN** the gate reports one `version` problem that names `package-lock.json` and `@fission-ai/openspec`, and runs no `openspec update --force`

### Requirement: Each run takes a scratch home
Each `openspec` run of `devops openspec check` SHALL set `XDG_CONFIG_HOME` and `HOME` to the one scratch directory of the gate, so that OpenSpec reads no profile of the person and writes no file under the home of the person.

#### Scenario: every_run_takes_its_configuration_directory_as_its_home
- **WHEN** the gate runs over a tree with no change and no spec, and `HOME` names the home of the person
- **THEN** every `openspec` run has one `HOME`, which is its `XDG_CONFIG_HOME` and not the home of the person

### Requirement: The skill check reads the layout of OpenSpec 2
The skill check of `devops openspec check` SHALL read the skills in `.agents/skills/openspec-*` and through each link `.claude/skills/openspec-*`, and SHALL require no skill in `.kilocode/skills`.

#### Scenario: a_tree_whose_claude_skills_link_to_the_shared_copy_passes_the_gate
- **WHEN** each `.claude/skills/openspec-*` folder of a tree with no change is a link to its folder in `.agents/skills`, and the tree has no `.kilocode/skills`
- **THEN** the gate reports no problem

### Requirement: The gate runs the OpenSpec that npm installed in the checkout
`devops openspec check`, `devops openspec regenerate`, `devops openspec archive`, `devops openspec new` and `devops roadmap plan-check` SHALL run `node_modules/.bin/openspec` of the checkout when that file exists, in place of the `openspec` on PATH, and the version problem SHALL name its path. With no such file, they SHALL run the `openspec` on PATH.

#### Scenario: The project install runs with no openspec on PATH
- **WHEN** the checkout holds `node_modules/.bin/openspec` and PATH resolves no `openspec`
- **THEN** `check_openspec` passes the tree, and each `openspec` run started `node_modules/.bin/openspec` of the checkout

#### Scenario: The version problem names the project install
- **WHEN** the checkout holds `node_modules/.bin/openspec`, PATH resolves another `openspec`, and the binary prints `1.14.3`
- **THEN** the version problem names the path of `node_modules/.bin/openspec` of the checkout and not the path on PATH

### Requirement: Modified requirement length
`devops openspec check` SHALL refuse each `MODIFIED` requirement of an active change whose text has more than `REQUIREMENT_MAX_CHARS` characters, reporting the requirement name, length, and limit before CLI validation runs.

#### Scenario: Long modified requirement
- **WHEN** the test scripts an active change with a `MODIFIED` requirement of 523 characters and runs `uv run devops openspec check`
- **THEN** the command exits 1 and prints the requirement name, its length `523`, and the limit `500`

### Requirement: Added requirement length
`devops openspec check` SHALL refuse each `ADDED` requirement of an active change whose text has more than `REQUIREMENT_MAX_CHARS` characters, reporting the requirement name, length, and limit before CLI validation runs.

#### Scenario: Long added requirement
- **WHEN** the test scripts an active change with an `ADDED` requirement of 523 characters and runs `uv run devops openspec check`
- **THEN** the command exits 1 and prints the requirement name, its length `523`, and the limit `500`

### Requirement: One copy of the rule
The OpenSpec gate MUST use `REQUIREMENT_MAX_CHARS` and the requirement length helper from `src/devops_cli/roadmap/stage/stage_change.py`, with no second copy of either definition.

#### Scenario: Shared definition
- **WHEN** a test imports `REQUIREMENT_MAX_CHARS` and `requirement_length_problem` from `devops_cli.openspec.gate` and from `devops_cli.roadmap.stage.stage_change`
- **THEN** both names refer to the exact same objects and `devops_cli.openspec.gate` defines no requirement limit constant of its own

### Requirement: UTF-16 count
The OpenSpec gate SHALL measure requirement text length in UTF-16 code units, so each character outside the Basic Multilingual Plane counts as two code units.

#### Scenario: Surrogate pair
- **WHEN** an active change holds a `MODIFIED` requirement with 500 UTF-16 code units plus one astral character (encoded as a surrogate pair) and `uv run devops openspec check` runs
- **THEN** the command exits 1 and prints its UTF-16 length `502`

### Requirement: Openspec CI row
The `openspec` row of `devops ci` SHALL run `devops openspec check` and fail when an active change holds a long `ADDED` or `MODIFIED` requirement.

#### Scenario: CI row on a long requirement
- **WHEN** a test executes the `openspec` row via `devops ci --check --only openspec` with the row command routed to `devops openspec check` against a scripted change with a 523-character `MODIFIED` requirement
- **THEN** the row exits non-zero and prints the requirement name and length `523`

### Requirement: Archived changes out of scope
The OpenSpec gate SHALL inspect active changes only and MUST NOT fail on a long requirement under `openspec/changes/archive/`.

#### Scenario: Archived long requirement
- **WHEN** an archived change under `openspec/changes/archive/` holds a `MODIFIED` requirement of 523 characters and no active change holds a long requirement, and `uv run devops openspec check` runs
- **THEN** the command exits 0
