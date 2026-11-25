## ADDED Requirements

### Requirement: Prepare writes named issues with comments
The `prepare` phase SHALL write each issue that the item body names, with its comments, to `work/github/issues/<number>.json` before the agent phase starts.

#### Scenario: Two named issues
- **WHEN** a test runs `prepare` for an item whose body names #12 and #34 with a fake GitHub client that returns one comment on #12
- **THEN** `work/github/issues/12.json` holds the state, title, labels, body and that comment, and `work/github/issues/34.json` exists

### Requirement: Prepare writes open pull requests with paths
The `prepare` phase SHALL write each open pull request with the paths that it changes to `work/github/pulls.json`.

#### Scenario: Two open pull requests
- **WHEN** a test runs `prepare` with a fake client that returns two open pull requests, one of which changes `src/app.py`
- **THEN** `work/github/pulls.json` holds both numbers and titles, and the paths of the second include `src/app.py`

### Requirement: Prepare writes files of a named pull request
The `prepare` phase SHALL write the files of each pull request that the item body names to `work/github/pull-files/<number>.json`.

#### Scenario: Named pull request
- **WHEN** a test runs `prepare` for an item whose body names #56 with a fake client that returns one changed file with a patch
- **THEN** `work/github/pull-files/56.json` holds the path and the patch of that file

### Requirement: Issue index is newline-delimited and bounded
The `prepare` phase SHALL write the open issues to `work/github/issue-index.jsonl` as one JSON object per line, with at most 1000 records and a body of at most 500 characters.

#### Scenario: Repository with 3000 open issues
- **WHEN** a test runs `prepare` with a fake client that returns 3000 open issues, each with a body of 2000 characters
- **THEN** `work/github/issue-index.jsonl` holds at most 1000 lines, each body is at most 500 characters, and the file is at most 1 MiB

### Requirement: A shell search finds an issue in the index
The open-issue index MUST let a shell search find an open issue by a word of its title or body.

#### Scenario: Word that only one open issue has
- **WHEN** a test runs `prepare` with a fake client that returns an open issue #4211 with the word `nondisruptive` in its body, and then runs `grep -i nondisruptive work/github/issue-index.jsonl`
- **THEN** the output holds `#4211` and no other issue number

### Requirement: Coder prompt names the snapshot files
The stage Coder prompt `roadmap_stage_coder.md` SHALL name `work/github/issues/`, `work/github/pulls.json`, `work/github/pull-files/` and `work/github/issue-index.jsonl` and tell the Coder to read them with its shell.

#### Scenario: Prompt for the stock Coder
- **WHEN** a test builds the stage Coder prompt
- **THEN** the prompt holds each path and a shell command that searches `work/github/issue-index.jsonl`

### Requirement: Agent phase offers no custom GitHub read tool
The `--phase agent` stage run SHALL offer only the stock Coder tools and no `read_issue` or `find_issues` tool.

#### Scenario: Agent phase tool list
- **WHEN** a test runs the stage agent phase with a fake Coder
- **THEN** `script.tools_offered` equals `stock.tools_offered`

### Requirement: Phase all keeps the live reads
A run of `--phase all` MUST keep the live GitHub reads and write no file under `work/github/`.

#### Scenario: Phase all run
- **WHEN** a test runs `--phase all` for an item with a fake GitHub client
- **THEN** the client receives the issue reads and no file under `work/github/` is written

### Requirement: A failed read does not stop prepare
The `prepare` phase SHALL record a failed GitHub read in `work/github/errors.json` and continue with the other reads.

#### Scenario: One read fails
- **WHEN** a test runs `prepare` with a fake client that raises for #34 and returns data for #12
- **THEN** `work/github/issues/12.json` exists, no `work/github/issues/34.json` exists, and `work/github/errors.json` names #34
