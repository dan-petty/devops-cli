## ADDED Requirements

### Requirement: The probe names the files of a cited bare name
When a cited path is no file at the root of the staging commit and the staged tree holds files with the same name under a folder, the stage probe SHALL name those files and give the existing file as the candidate.

#### Scenario: Cited bare name with a file under a folder
- **WHEN** The issue cites `stage_specs.py`, the staging commit holds no root `stage_specs.py`, and `src/devops_cli/roadmap/stage_specs.py` is a file of the commit.
- **THEN** The probe line for `stage_specs.py` says the path is no file at the root of the staging commit, names `src/devops_cli/roadmap/stage_specs.py` as the candidate, and lists `stage_specs.py` in `missing`.

#### Scenario: Cited root file lists no same-name file
- **WHEN** The issue cites `README.md` and the staging commit holds `README.md` at the root.
- **THEN** The probe reports `README.md` as a file of the staging commit and lists no other file.

#### Scenario: Missing path with no same-name file keeps its line
- **WHEN** The issue cites `src/devops_cli/never.py`, the staging commit holds no such file, and no file of the commit has the name `never.py`.
- **THEN** The probe reports the path as no file of the staging commit and names no candidate.

#### Scenario: Same-name files stay bounded
- **WHEN** Six files of the staged tree carry the name of the cited path and the root holds none of them.
- **THEN** The probe names at most five of them, in sorted order.
