## ADDED Requirements

### Requirement: The roadmap-stage-eval-commits row checks the base commit of each golden case
The table of `devops ci` SHALL hold a row `roadmap-stage-eval-commits` that runs the check module of the row from `tests/gate/`. The row SHALL read the golden stage eval cases and the git history of the repository, and it SHALL pass when each base commit that is not `NO_COMMIT` is a full hash that names a commit of the repository.

#### Scenario: The row reads the cases and the history
- **WHEN** `devops ci` runs the `roadmap-stage-eval-commits` row
- **THEN** the row reads the golden cases and the git history of the repository and prints the count of cases that it read

#### Scenario: The golden set passes the row
- **WHEN** each case whose base commit is not `NO_COMMIT` names a full hash of a commit of the repository, and each other case has a note that says it reads no commit
- **THEN** the row passes and prints the count of cases that it read

### Requirement: The roadmap-stage-eval-commits row fails on a base commit that it cannot resolve
The row SHALL fail and SHALL name each case whose base commit is not a full hash of a commit of the repository, and each case whose base commit is `NO_COMMIT` and whose notes do not say that it reads no commit.

#### Scenario: Base commit is no commit
- **WHEN** a case names a 40-character hash that `git cat-file -e` cannot resolve as a commit
- **THEN** the row fails and its message names the case and the hash

#### Scenario: A case with no commit lacks the note
- **WHEN** a case has base commit `NO_COMMIT` and no note that says it reads no commit
- **THEN** the row fails and its message names the case

### Requirement: The roadmap-stage-eval-commits row fails on a shallow clone
The row SHALL fail when the repository is a shallow clone, with a message that says the clone lacks the history that the golden cases name. The `static` job of `.github/workflows/ci.yml`, which runs the row, SHALL check out the full history with `fetch-depth: 0`.

#### Scenario: Shallow repository
- **WHEN** `git rev-parse --is-shallow-repository` prints `true`
- **THEN** the row fails and the message says that the shallow clone lacks the history that the golden cases need

#### Scenario: The Static Analysis job gives the row the full history
- **WHEN** a test reads the `Check out repository` step of the `static` job in `.github/workflows/ci.yml`
- **THEN** the step sets `fetch-depth: 0`
