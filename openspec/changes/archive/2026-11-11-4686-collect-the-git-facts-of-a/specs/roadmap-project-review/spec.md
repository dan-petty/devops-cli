## Purpose

How `devops roadmap review run` resolves a version range or a period to a half-open window of first-parent commits and UTC times, reads the git facts of that window from the local checkout, and writes them with their sources to `data.json`.

## ADDED Requirements

### Requirement: A review window is half-open on first-parent commits and UTC times
`devops roadmap review run` SHALL take one window: `--version A..B`, `--since` with `--until`, `--week` or `--last`. A tag SHALL become its commit and commit time. A time SHALL become an aware UTC value, UTC when it has no offset, and the last first-parent commit of the default branch at or before it. The base commit and the start time SHALL be out of the window, and the head commit and the end time SHALL be in.

#### Scenario: Tags in two time zones compare by the instant
- **WHEN** `v1.1.0` is created at +02:00 and `v1.1.1` at -07:00, and the review resolves the week `2026-W40`
- **THEN** the tags of the week are `v1.1.0` only, by the UTC instant of each tag

#### Scenario: The base tag is out of a version window
- **WHEN** the review resolves `--version v1.0.0..v1.1.1`
- **THEN** the window starts at the commit time of `v1.0.0`, which is out, and its release tags are `v1.1.0` and `v1.1.1`

#### Scenario: A period takes the last first-parent commit at or before each time
- **WHEN** the review resolves `--since 2026-10-03T10:00:00Z --until 2026-10-05T06:30:00Z`
- **THEN** the base and head commits are the commits of `v1.1.0` and `v1.1.1`, and the previous window is `20261001T1330Z..20261003T1000Z`

#### Scenario: Two windows are refused before any read
- **WHEN** a person gives `--version v1.0.0..v1.1.1` and `--last 7d`
- **THEN** the command exits 1 with a message that asks for one window, and it starts no program

### Requirement: The review writes each git fact of the window with its source
The review SHALL write `data.json` and its JSON Schema `data.schema.json`. Each fact SHALL hold an id, a value, a unit, `n`, a source, the exact query, a definition, `read_at` and a status of `ok`, `expired`, `skipped` or `error`; a fact that is not `ok` SHALL give a reason. The facts SHALL be the commits, their types, the net change and the churn with generated paths apart, the release tags, the hot files and the complexity.

#### Scenario: A run writes data.json under the data directory
- **WHEN** a person runs `devops roadmap review run --version v1.0.0..v1.1.1 --json` in a checkout of `example/project`
- **THEN** the command writes `project-review/example/project/v1.0.0..v1.1.1/data.json` and `data.schema.json` under the data directory, and prints the same data

#### Scenario: A review with no lizard skips the complexity and says why
- **WHEN** lizard is not installed
- **THEN** the fact `lizard.complexity` has no value, the status `skipped`, and a reason that names the extra `review`

#### Scenario: A fact that is not ok must say why
- **WHEN** a fact has the status `error` and no reason
- **THEN** the model refuses the fact

### Requirement: Hot files follow renames
The hot-file fact SHALL count a commit at an old path of a renamed file for the row of the path at the head, SHALL name each old path in the row, and SHALL leave out the paths that `.gitattributes` of the head marks `linguist-generated`.

#### Scenario: A commit at an old name counts for the path at the head
- **WHEN** `a.py` becomes `b.py` and then `c.py` in the window, and four commits touch the file
- **THEN** the row of `c.py` counts 4 commits and names `b.py` and `a.py`

### Requirement: A dry run of the review starts no program
`devops roadmap review run --dry-run` SHALL print the git commands that a run starts, in order, with a placeholder for each value that a read gives. It SHALL start no program, open no connection and write no file.

#### Scenario: A dry run lists the git commands
- **WHEN** a person runs `devops roadmap review run --version v1.0.0..v1.1.1 --dry-run`
- **THEN** the output lists the `git log` command of each tag and the first-parent log of `<base commit>..<head commit>`, and no program starts

### Requirement: The review refuses a repository that is not the origin of the checkout
When `--repo` names a repository that is not the origin of the checkout, the command SHALL exit 1 with a message that names both, and SHALL write no file.

#### Scenario: Another repository is refused
- **WHEN** a person runs the review with `--repo example/other` in a checkout of `example/project`
- **THEN** the command exits 1, the message names `example/project`, and no folder is written
