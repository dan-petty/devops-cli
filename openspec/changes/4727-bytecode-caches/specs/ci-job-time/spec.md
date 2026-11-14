## ADDED Requirements

### Requirement: The test jobs skip the bytecode compile
`setup-toolchain` SHALL take a `compile-bytecode` input with the default `true`, and the `test-shard`, `changed-tests`, `job-time` and Service Image Tests jobs SHALL pass `false`.

#### Scenario: A test job synchronizes dependencies
- **WHEN** the `test-shard` job runs `setup-toolchain` with `compile-bytecode: "false"`
- **THEN** `uv sync` runs without `--compile-bytecode`

#### Scenario: A job that keeps the compile
- **WHEN** a job calls `setup-toolchain` with no `compile-bytecode`
- **THEN** `uv sync` runs with `--compile-bytecode`
