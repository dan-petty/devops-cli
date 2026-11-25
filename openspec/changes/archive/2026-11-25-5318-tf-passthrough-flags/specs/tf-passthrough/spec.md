# tf-passthrough Specification

## Purpose

Define directory-boundary argument pass-through, short-alias removal, zero-request `--dry-run` reporting, and `import`, `state`, `show`, and `force-unlock` mirror subcommands under `devops tf`.

## ADDED Requirements

### Requirement: Plan and mirror verb pass-through

Each `devops tf` mirror verb (`init`, `plan`, `apply`, `destroy`, `output`, `validate`, `fmt`) SHALL parse wrapper options before `<directory>` and pass every argument after `<directory>` to `tofu <verb>` unchanged, with `<directory>` as working directory.

#### Scenario: Plan flags reach tofu

- **WHEN** a test runs `devops tf plan <dir> -out=x.plan -lock=false` with a fake `tofu` executable
- **THEN** the fake records the argv `tofu plan -out=x.plan -lock=false` and the working directory `<dir>`

### Requirement: Colliding short aliases removed

All `devops tf` subcommands MUST NOT declare `-o`, `-v`, `-p`, or `-u` as wrapper short options while keeping existing long wrapper options before `<directory>`.

#### Scenario: Removed alias is rejected

- **WHEN** a test runs `devops tf plan -o x.plan <dir>`
- **THEN** the command exits non-zero with an unknown option error and starts no `tofu` process

### Requirement: Import pass-through

The `devops tf import` command SHALL run `tofu import` in `<directory>` and forward every remaining argument unchanged.

#### Scenario: Import address and id reach tofu

- **WHEN** a test runs `devops tf import <dir> aws_instance.web i-123` with a fake `tofu` executable
- **THEN** the fake records `tofu import aws_instance.web i-123` and the working directory `<dir>`

### Requirement: State pass-through

The `devops tf state` command SHALL run `tofu state` in `<directory>` and forward every remaining argument unchanged.

#### Scenario: State list reaches tofu

- **WHEN** a test runs `devops tf state <dir> list` with a fake `tofu` executable
- **THEN** the fake records `tofu state list` and the working directory `<dir>`

### Requirement: Show pass-through

The `devops tf show` command SHALL run `tofu show` in `<directory>` and forward every remaining argument unchanged.

#### Scenario: Show JSON reaches tofu

- **WHEN** a test runs `devops tf show <dir> -json` with a fake `tofu` executable
- **THEN** the fake records `tofu show -json` and the working directory `<dir>`

### Requirement: Force-unlock pass-through

The `devops tf force-unlock` command SHALL run `tofu force-unlock` in `<directory>` and forward every remaining argument unchanged.

#### Scenario: Force-unlock id reaches tofu

- **WHEN** a test runs `devops tf force-unlock <dir> -force 123456` with a fake `tofu` executable
- **THEN** the fake records `tofu force-unlock -force 123456` and the working directory `<dir>`

### Requirement: Zero-request dry run

Each `devops tf` mirror verb with `--dry-run` (`init`, `plan`, `apply`, `destroy`, `output`, `import`, `state`, `show`, `force-unlock`) SHALL print the full `tofu` argv (including forwarded trailing arguments) and the target `<directory>` without starting `tofu`.

#### Scenario: Dry run starts no process

- **WHEN** a test runs `devops tf plan --dry-run <dir> -out=x.plan` with a fake `tofu` executable
- **THEN** the output contains `tofu plan -out=x.plan` and `<dir>`, and the fake records zero calls

### Requirement: Command documentation

The change SHALL document the new `tf` mirror verbs and removed short aliases in `docs/commands/tf.md` and regenerate `docs/CLI_REFERENCE.md` from the command tree.

#### Scenario: Generated docs pass check

- **WHEN** `uv run devops docs generate && uv run devops docs check` runs
- **THEN** both exit 0 and `docs/commands/tf.md` lists `import`, `state`, `show`, and `force-unlock`
