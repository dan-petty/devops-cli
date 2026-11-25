## MODIFIED Requirements

### Requirement: The committed set holds both good and bad results
The committed set SHALL hold at least 40 fixtures, the fixtures of #2175 and #2735 among them. It SHALL hold a recorded result that fails no property and a recorded result that fails some.

#### Scenario: The committed set
- **WHEN** the loader reads the committed folder
- **THEN** it returns at least 40 fixtures, including those of #2175 and #2735, with a recorded result that fails no property and one that fails some

### Requirement: One Harbor task folder for each implement fixture
The exporter SHALL write one Harbor task folder for each fixture under `tests/fixtures/roadmap_eval/implement`, and each folder SHALL hold an instruction file, an environment Dockerfile, a test script and a task configuration with text in each.

#### Scenario: A fixture becomes a task folder
- **WHEN** The exporter runs on the fixture `2747-env-keys`
- **THEN** The output folder holds the four files, and each of the four holds text.

#### Scenario: Every committed fixture gets a folder
- **WHEN** The exporter runs on the fixtures of the committed set
- **THEN** It writes one task folder for each loaded fixture, and each of the four files of each folder holds text.

## ADDED Requirements

### Requirement: Case content
Each case MUST record a full 40-character SHA `base`, the issue text in `issue.md`, the three merged plan files under `plan/`, and the test commands in `tests_pass`.

#### Scenario: A new case holds its four parts
- **WHEN** the loader validates a new case of the implement golden set
- **THEN** `base` is a full 40-character hexadecimal SHA, `plan/` holds `proposal.md`, `design.md` and `tasks.md`, `issue.md` holds text, and `tests_pass` holds the expected test commands

### Requirement: Base commit exists
The base commit of every implement golden-set case MUST resolve to a commit of the `devops-cli` repository.

#### Scenario: The gate row resolves each base
- **WHEN** `uv run devops ci --check --only roadmap-eval-commits` runs on a full clone
- **THEN** the row exits 0 and prints the count of stage and implement cases whose base commit is a commit of the repository, with no case named as refused

### Requirement: Size bound
The implement golden set SHALL stay under 1,000,000 bytes.

#### Scenario: The set fits its raised bound
- **WHEN** `uv run devops ci test tests/invariants/test_roadmap_eval_fixtures.py` runs `test_the_set_stays_small`
- **THEN** the total size of `tests/fixtures/roadmap_eval/implement` is under 1,000,000 bytes

### Requirement: Scope counts
The implement golden-set test MUST record the count of cases for each scope and MUST fail when the set does not match that record.

#### Scenario: Scope counts match the delivery mix
- **WHEN** the scope test runs over `tests/fixtures/roadmap_eval/implement` and reads each scope from the fixture `title`
- **THEN** it prints each scope with its count, and passes only when each count equals the distribution recorded from the merged delivery pull requests of the last 90 days and the counts sum to the number of cases
