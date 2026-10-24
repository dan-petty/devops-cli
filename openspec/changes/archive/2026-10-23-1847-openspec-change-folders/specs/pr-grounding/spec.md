# Spec Delta

## Purpose

Readiness holds a pull request to the one item it delivers and to the record of that item: the OpenSpec change of the issue, which the pull request archives in its last commit.

## ADDED Requirements

### Requirement: A pull request archives the change of the issue it closes
Where the base holds `openspec/changes/`, `devops pr check-readiness` SHALL block a pull request into the default branch that adds no file in `openspec/changes/archive/<date>-<issue>-<slug>/` for the one open issue it closes. A file is added when GitHub reports it as added, renamed or copied. The blocker SHALL name the expected folder and the archive command.

#### Scenario: The pull request adds the archived folder of its issue
- **WHEN** a pull request closes #704 and adds `openspec/changes/archive/2026-10-23-704-x/proposal.md`
- **THEN** readiness reports no blocker

#### Scenario: The pull request moves its active folder into the archive
- **WHEN** a pull request closes #704 and GitHub reports `openspec/changes/archive/2026-10-23-704-x/tasks.md` as renamed
- **THEN** readiness reports no blocker

#### Scenario: The pull request has no change folder
- **WHEN** a pull request closes #704 and changes only `src/x.py`
- **THEN** readiness reports one blocker that names `openspec/changes/archive/<date>-704-<slug>/`

#### Scenario: The pull request leaves its change active
- **WHEN** a pull request closes #704 and adds only `openspec/changes/704-x/proposal.md`
- **THEN** readiness reports one blocker that names `openspec/changes/archive/<date>-704-x/` and `uv run devops openspec archive 704-x`

#### Scenario: The pull request removes the archived folder of its issue
- **WHEN** a pull request closes #704 and removes `openspec/changes/archive/2026-10-23-704-x/proposal.md`
- **THEN** readiness reports one blocker that names `openspec/changes/archive/<date>-704-<slug>/`

### Requirement: Only the archive of its own change writes the specs and the archive
`devops pr check-readiness` SHALL block a pull request that changes a file in `openspec/specs/` and adds no archived folder of the issue it closes. It SHALL also block a pull request that changes a file in `openspec/changes/archive/` outside the archived folder of that issue. The blocker SHALL name each such file.

#### Scenario: The archive writes the living spec
- **WHEN** a pull request closes #704, adds `openspec/changes/archive/2026-10-23-704-x/proposal.md` and adds `openspec/specs/widget/spec.md`
- **THEN** readiness reports no blocker

#### Scenario: A spec changes without the archive
- **WHEN** a pull request closes #704, modifies `openspec/specs/widget/spec.md` and adds no archived folder
- **THEN** readiness reports a blocker that names `openspec/specs/widget/spec.md`

#### Scenario: The pull request changes the archived folder of another issue
- **WHEN** a pull request closes #704, adds its own archived folder and modifies `openspec/changes/archive/2026-10-01-705-y/tasks.md`
- **THEN** readiness reports one blocker that names `openspec/changes/archive/2026-10-01-705-y/tasks.md`

### Requirement: Grounding applies where the base holds change folders
`devops pr check-readiness` SHALL apply its grounding rules only when the base commit of the pull request holds `openspec/changes/`. When GitHub answers that the directory is not found, readiness SHALL require nothing of grounding. When the lookup fails for another reason, readiness SHALL report one blocker that names `openspec/changes/`.

#### Scenario: A base without change folders
- **WHEN** GitHub answers HTTP 404 for `openspec/changes` at the base commit
- **THEN** readiness reports no grounding blocker, and a file list that it cannot read is a warning

#### Scenario: The lookup fails
- **WHEN** GitHub answers HTTP 500 for `openspec/changes` at the base commit
- **THEN** readiness reports one blocker that says `openspec/changes/` could not be read at its base
