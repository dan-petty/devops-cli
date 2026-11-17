## ADDED Requirements

### Requirement: Named pull request files at the merge commit
The stage verification input SHALL hold the changed files of each pull request that the issue body or a plan text names, read at the merge commit of that pull request.

#### Scenario: A named pull request is read at its merge commit
- **WHEN** The issue body names `pull request #3378`, and the pull request read returns merge commit `abc123`.
- **THEN** The verification input holds a `pull_requests` entry for `3378` with the commit `abc123` and a path-to-text map of the files that the pull request changed.

### Requirement: Only a named pull request number is read
The stage job SHALL read a pull request number only when the phrase `pull request #` or `PR #` names it, in the issue body or in the plan texts.

#### Scenario: A bare issue reference is not read
- **WHEN** The issue body holds `#3410` with no phrase before it and also holds `pull request #3378`.
- **THEN** The verification input holds an entry for `3378` and no entry for `3410`.

### Requirement: A pull request that cannot be read leaves the plan running
The stage job MUST record a named pull request that it cannot read at a merge commit as no entry in the verification input, and SHALL go on with the plan.

#### Scenario: A named pull request has no merge commit
- **WHEN** The issue body names `pull request #3378`, and the pull request read reports that it is not merged.
- **THEN** The verification input holds no `pull_requests` entry for `3378`, the pass still runs, and the plan is not stopped by the read.

### Requirement: A pull request quote is evidence
The verification pass MUST treat a quote from a named pull request file as a text of its input, so that a `false_premise` finding with that quote is open.

#### Scenario: A false-premise finding quotes a pull request file
- **WHEN** The verifier returns a `false_premise` finding of severity `major` whose `quote` is a line of a file that the #3378 pull request changed.
- **THEN** The finding is open, and the repair rounds return the plan to the planner.

### Requirement: Bounded pull request read
The verification input SHALL read no more than `CONST_ROADMAP_STAGE_VERIFY_MAX_FILES` files from a named pull request and SHALL cut each file to `CONST_ROADMAP_STAGE_VERIFY_FILE_MAX_TOKENS` tokens.

#### Scenario: A large pull request is bounded
- **WHEN** A named pull request changes more files than the maximum, and each file is longer than the token limit.
- **THEN** The input holds at most the maximum number of files, and each held file is cut to the token limit.

### Requirement: The prompt names the pull request files
The stage verification prompt SHALL name the `pull_requests` key and SHALL tell the model to check a claim against those files.

#### Scenario: The verification prompt is loaded
- **WHEN** The stage verification task loads `src/devops_cli/ai/tasks/roadmap_stage_verify.md`.
- **THEN** The prompt names `pull_requests`, its merge commit and its path-to-text map.

### Requirement: Regression case for #3410
The test suite MUST hold the #3410 claim, the literal `! git grep -n -F devops_cli.roadmap.stage src/ tests/`, and the recorded #3378 plan at merge commit `6c15a64a614941629669a181e3220ae8bc7e27d0`, which holds no move group.

#### Scenario: The #3410 claim is checked
- **WHEN** The test builds the verification input for the #3410 issue body with the recorded #3378 plan and its files, and a `false_premise` finding quotes the literal from a file that the #3378 pull request changed.
- **THEN** The input holds the #3378 file with the literal, the recorded #3378 plan holds no move group, and the finding is open.
