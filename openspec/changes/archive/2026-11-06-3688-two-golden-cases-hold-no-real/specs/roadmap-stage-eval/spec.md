## ADDED Requirements

### Requirement: A case that holds no commit is left out and named
A case with the commit `NO_COMMIT`, forty zeros, as its `base_commit` holds no commit, as the change of its plan was never merged as that plan. `devops roadmap eval verify` and `devops roadmap eval stage` SHALL leave such a case out of a live run and of a dry run, by one shared rule that reads no git. The text report and the JSON report (`left_out`) SHALL name each left-out case. A left-out case SHALL NOT count in the cases, in the labeled defects, in the score or in the exit code.

#### Scenario: The verify command leaves a case out
- **WHEN** `devops roadmap eval verify` runs on a set of one case with a commit and one case with `NO_COMMIT`, and the model finds the defect of the first case
- **THEN** the command exits 0, the model gets one call, the report counts one case and the defects of that case only, and the text and the JSON name the left-out case

#### Scenario: The stage command leaves a case out
- **WHEN** `devops roadmap eval stage` runs on the same set
- **THEN** the command exits 0, the score counts one case, and the text and the JSON name the left-out case

#### Scenario: The dry run leaves a case out
- **WHEN** either command runs with `--dry-run` on a set that holds a case with `NO_COMMIT`
- **THEN** the output lists the model calls of the other cases only, names the left-out case, and makes no request

### Requirement: A run with no case to check out fails, and the replay keeps every case
When the selection holds no case with a commit, the command SHALL exit 1 and name the cases. `devops roadmap eval stage --replay` reads no git and SHALL keep every case.

#### Scenario: Nothing is left to run
- **WHEN** `--case` picks only a case with `NO_COMMIT`
- **THEN** the command exits 1 and names the case

#### Scenario: The replay keeps the case
- **WHEN** `devops roadmap eval stage --replay` runs with `--case` for a case with `NO_COMMIT`
- **THEN** the replay runs the case and exits 0

### Requirement: A commit that git cannot check out ends its case and not the run
When git cannot check out the `base_commit` of a case in the live run of `devops roadmap eval stage`, the case SHALL end `failed` with the git error as its reason. The other cases SHALL run, the report SHALL be stored, and the command SHALL exit 1.

#### Scenario: A repository without the commit
- **WHEN** a live run has two cases, and the repository lacks the commit of the first
- **THEN** the first case ends `failed`, the second case is staged, the report is stored with both outcomes, and the command exits 1

### Requirement: Each commit of the set is a real commit or the case reads none
The `base_commit` and the `merge_commit` of each case of the golden set SHALL each be the full hash of a commit of this repository, or `NO_COMMIT` in a case whose notes say that it reads no commit.

#### Scenario: The commits of the set
- **WHEN** the test reads the 45 cases
- **THEN** each hash that is not `NO_COMMIT` has 40 hexadecimal characters and names a commit of this repository, and each case with `NO_COMMIT` has a note that says it reads no commit
