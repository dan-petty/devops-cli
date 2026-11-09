# openspec-archive Specification

## Purpose
The archive command moves a finished change into the archive and proves it with the folders on disk, so that a pull request never goes on without its archive commit.

## Requirements

### Requirement: The archive is proved on disk
After `openspec archive` exits 0, `devops openspec archive <change>` SHALL check that the folder `openspec/changes/<change>` is gone and that a new folder `openspec/changes/archive/<date>-<change>` exists. If a check fails, the command SHALL exit 1 with a message that names the change and the folder, and SHALL NOT print `Archived`.

#### Scenario: The tool exits 0 and moves nothing
- **WHEN** `openspec archive` exits 0 and the change folder is still there
- **THEN** the command exits 1 and names the change and the folder that is still there

#### Scenario: The tool removes the folder and makes no archive folder
- **WHEN** `openspec archive` exits 0, the change folder is gone, and no new archive folder exists
- **THEN** the command exits 1 and names the change and the archive folder

#### Scenario: The folder moved
- **WHEN** `openspec archive` moves the change folder to `openspec/changes/archive/<date>-<change>`
- **THEN** the command runs the validation and prints `Archived`

### Requirement: A dry run archives nothing
In a dry run, `devops openspec archive <change>` SHALL start no process. It SHALL list the `openspec` commands it would run and print `Would archive <change>`. It SHALL NOT print `Archived`.

#### Scenario: Dry run by variable
- **WHEN** `DEVOPS_CLI_DRY_RUN=1` is set and the user runs `devops openspec archive <change>`
- **THEN** the output lists the archive and validate commands and says `Would archive <change>`, and no `openspec` process starts
