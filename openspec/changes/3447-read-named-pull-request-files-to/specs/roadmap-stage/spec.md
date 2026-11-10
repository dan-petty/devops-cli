## ADDED Requirements

### Requirement: The verification request holds each named pull request at its merge commit

The verification input SHALL hold a `pull_requests` list with one entry for each pull request that the issue body or the plan names as `pull request #<number>` or `PR #<number>`, with no regard to case. Each entry SHALL hold the number of the pull request, its merge commit, and the text of each changed file at that merge commit. The reader SHALL take no other number, SHALL read each number once in first-seen order, and SHALL hold no entry for a pull request with no merge commit.

#### Scenario: A named pull request is read at its merge commit

- **WHEN** the issue body names `pull request #3378` and GitHub holds the merge commit `abc123` for it
- **THEN** the input holds the changed files of #3378 at `abc123`, and no file comes from another commit

#### Scenario: A pull request with no merge commit adds no entry

- **WHEN** the issue body names `PR #12` and pull request #12 is open with no merge commit
- **THEN** the input holds no entry for #12 and the pass runs on the input it has

#### Scenario: A bare number names no pull request

- **WHEN** the issue body says `see #3410 and pull request #3378`
- **THEN** the input holds only the entry for #3378

### Requirement: The named pull request read is bounded

The reader SHALL hold at most `CONST_ROADMAP_STAGE_VERIFY_MAX_FILES` files over all named pull requests and SHALL cut each held file to `CONST_ROADMAP_STAGE_VERIFY_FILE_MAX_TOKENS` tokens. It SHALL mask each secret and SHALL put a path under `openspec/changes/` before a path that the claim names, and that path before the other changed files.

#### Scenario: A large pull request is bounded

- **WHEN** a named pull request changes more files than `CONST_ROADMAP_STAGE_VERIFY_MAX_FILES` and each file is longer than `CONST_ROADMAP_STAGE_VERIFY_FILE_MAX_TOKENS` tokens
- **THEN** the input holds at most the maximum files, and each held file is cut to the token limit

#### Scenario: The plan of a named plan pull request comes first

- **WHEN** the issue body names a plan pull request that changes a file under `openspec/changes/` and other files
- **THEN** the input holds the file under `openspec/changes/` first

### Requirement: A quote from a named pull request file returns the plan

The verification pass SHALL put the text of each named pull request file in the texts of the request. A finding of type `false_premise` whose quote, with white space folded, is in one of those texts SHALL return the plan to the planner and SHALL be an open finding.

#### Scenario: A false-premise finding with a pull request quote

- **WHEN** the verifier returns a `false_premise` finding whose quote is in a named pull request file
- **THEN** `returning` returns the finding and `open_findings` holds it

#### Scenario: The #3410 claim is checked

- **WHEN** the pass reads the recorded #3378 plan, which holds the literal `! git grep -n -F devops_cli.roadmap.stage src/ tests/` and no move group, and the plan claims a move
- **THEN** the pass reports a `false_premise` finding that returns the plan to the planner

### Requirement: The verification prompt describes the named pull request files

The stage verification prompt SHALL name the `pull_requests` key, the `number` and `merge_commit` of an entry, and its map of path to text. It SHALL tell the model to check a claim about an earlier pull request against those files.

#### Scenario: The verification prompt is loaded

- **WHEN** the stage verification task loads `roadmap_stage_verify.md`
- **THEN** the prompt names `pull_requests`, its merge commit and its path to text map
