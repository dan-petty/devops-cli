## ADDED Requirements

### Requirement: One repeat run starts alone
`devops ci test` SHALL take the option `--run <k>`, a whole number of at least 1. With `--run`, a `--repeat <n>` run SHALL start only run `<k>`, with the seed that run `<k>` of the `<n>` runs gets, so that CI can start each run on a runner of its own. The command SHALL refuse a `--run` above `--repeat` with exit 2 before it starts a process.

#### Scenario: Run 2 of 3
- **WHEN** The caller passes `--repeat 3 --run 2 --seed 10` and one test file.
- **THEN** The command runs pytest one time, with `--randomly-seed=11`.

#### Scenario: Run above the repeat count
- **WHEN** The caller passes `--repeat 3 --run 4` and one test file.
- **THEN** The command exits 2 and starts no process.
