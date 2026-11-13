## MODIFIED Requirements

### Requirement: Each shard collects only its own test files
The shards SHALL partition the test modules of `tests/`: each module SHALL be in exactly one shard, and no shard SHALL be empty. The split SHALL be the same in every call. It SHALL be computed from the files of the checkout alone: the test modules and the record `tests/module_durations.json`.

#### Scenario: Four shards cover every test module once
- **WHEN** the module lists of shards 1 to 4 of 4 are built for the tree
- **THEN** every test module of `tests/` is in exactly one list, and no list is empty

#### Scenario: The split is the same in every call
- **WHEN** the module list of a shard is built twice, in any order of the shards
- **THEN** the two lists are equal

#### Scenario: The split has no stored input
- **WHEN** the modules of a tree without `tests/module_durations.json` are dealt to two shards
- **THEN** the lists come from the line counts of the files, the heaviest file going first to the shard with the fewest lines so far

## ADDED Requirements

### Requirement: The shards balance the recorded seconds
The split SHALL weigh each test module by its seconds in `tests/module_durations.json`. A module that the record does not hold SHALL weigh its lines times the recorded seconds per line of the recorded modules of the tree. A recorded module that the tree does not hold SHALL be in no shard and SHALL NOT count in that rate. The modules SHALL go, heaviest first and then by path, to the shard with the least weight so far, and a tie SHALL go to the lower shard.

#### Scenario: A short module with a long recorded time
- **WHEN** a module of 10 lines has a record of 300 seconds and three modules of 500 lines each have 10 seconds, and the modules are dealt to two shards
- **THEN** the short module is alone in its shard and the three other modules share the other shard

#### Scenario: A module without a record
- **WHEN** two recorded modules of 100 lines each have 100 and 10 seconds, a third module of 100 lines has no record, and the modules are dealt to two shards
- **THEN** the third module weighs 55 seconds and shares a shard with the module of 10 seconds

#### Scenario: A deleted module in the record
- **WHEN** the record holds a module that the tree does not hold
- **THEN** no shard holds it, and its seconds do not change the weight of a module without a record

### Requirement: The record is written from the shard reports of CI
`devops ci durations` SHALL read the last 20 push runs of `ci.yml` on `main` where `Tests & Coverage` ran to an end. It SHALL download their `coverage-shard-*` artifacts with `gh run download` and read the time of each test from the JUnit XML reports. It SHALL write the mean seconds of each module of the tree over the runs that ran it to `tests/module_durations.json`, in tenths of a second.

#### Scenario: Two runs with reports and one without
- **WHEN** run 2 holds two shard reports, run 1 one report, and run 3 only an expired shard artifact, and the user runs `devops ci durations --runs 3`
- **THEN** gh downloads the artifacts of runs 2 and 1 only, and the record holds the mean of each module over the runs that ran it

### Requirement: No record without a report
When no run read holds a shard artifact that GitHub still keeps, `devops ci durations` SHALL exit 1 and write no record. A dry run SHALL list its requests and the download, and make none.

#### Scenario: No run holds a report
- **WHEN** the shard artifacts of every run read are expired
- **THEN** the command exits 1, writes no record and downloads nothing

#### Scenario: Dry run
- **WHEN** the user runs `devops ci durations --dry-run`
- **THEN** the plan names the listing of runs, the jobs and artifacts of each run and the download, and no request is made
