## MODIFIED Requirements

### Requirement: The test row runs one shard of the suite
The command `devops ci` SHALL take the options `--shard <n>` and `--shards <total>`, whole numbers of at least 1 that default to 1. With `--shards` above 1, the command of the `test` row SHALL hold `--cov=src` and the paths of the test modules of shard `<n>`. It SHALL hold none of `--splits`, `--group` and `--splitting-algorithm`. With `--shards` at 1, the command SHALL be that of an unsharded run.

#### Scenario: Shard two of four
- **WHEN** the user runs `devops ci --dry-run --only test --shard 2 --shards 4`
- **THEN** the planned command holds the paths of the test modules of shard 2 and holds none of `--splits`, `--group` and `--splitting-algorithm`

#### Scenario: No shard
- **WHEN** the user runs `devops ci --dry-run --only test`
- **THEN** the planned command holds none of `--splits`, `--group` and `--cov-fail-under=0`, and holds `--cov-report=term-missing`

#### Scenario: A shard above the total
- **WHEN** the user runs `devops ci --only test --shard 5 --shards 4`
- **THEN** the command exits 2 and starts no check

## ADDED Requirements

### Requirement: Each shard collects only its own test files
The shards SHALL partition the test modules of `tests/`: each module SHALL be in exactly one shard, and no shard SHALL be empty. The split SHALL be the same in every call. It SHALL be computed from the files of the checkout alone, with no stored input.

#### Scenario: Four shards cover every test module once
- **WHEN** the module lists of shards 1 to 4 of 4 are built for the tree
- **THEN** every test module of `tests/` is in exactly one list, and no list is empty

#### Scenario: The split is the same in every call
- **WHEN** the module list of a shard is built twice, in any order of the shards
- **THEN** the two lists are equal

#### Scenario: The split has no stored input
- **WHEN** the modules of a tree are dealt to two shards
- **THEN** the lists come from the line counts of the files alone, the heaviest file going first to the shard with the fewest lines so far
