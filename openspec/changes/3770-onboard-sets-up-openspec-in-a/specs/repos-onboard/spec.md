## ADDED Requirements

### Requirement: The OpenSpec row reads present
`devops repos onboard` SHALL print row 16 `openspec` as `present` when the default branch holds `openspec/config.yaml` with `schema: spec-driven` and at least one tracked regular file under `openspec/specs/`, and the command SHALL write nothing for that row.

#### Scenario: A complete OpenSpec setup
- **WHEN** The default branch holds `openspec/config.yaml` with the schema `spec-driven` and `openspec/specs/.gitkeep`, and `--plan` runs
- **THEN** Row 16 is `present`, the row writes nothing, and the command exits 0

### Requirement: The OpenSpec row reads missing
The command SHALL print row 16 as `missing`, with `openspec/config.yaml` in its reason, when the default branch holds no `openspec/config.yaml` and the head of the open template pull request holds none of the shipped OpenSpec files.

#### Scenario: A repository with no OpenSpec
- **WHEN** The default branch holds no `openspec/config.yaml` and no template pull request is open
- **THEN** Row 16 is `missing`, its reason names `openspec/config.yaml`, and the command exits 1

### Requirement: The OpenSpec row reads invalid
The command SHALL print row 16 as `invalid`, with the failed condition in its reason, when the default branch holds `openspec/config.yaml` and the file does not parse as YAML, names a schema other than `spec-driven`, or no tracked regular file is under `openspec/specs/`.

#### Scenario: A config file of another schema
- **WHEN** `openspec/config.yaml` names a schema other than `spec-driven`
- **THEN** Row 16 is `invalid` and its reason names the schema that it read

#### Scenario: A config file that does not parse
- **WHEN** `openspec/config.yaml` is not valid YAML
- **THEN** Row 16 is `invalid` and its reason names the parse failure

#### Scenario: No file under the specs path
- **WHEN** `openspec/config.yaml` names `spec-driven` and the default branch holds no file under `openspec/specs/`
- **THEN** Row 16 is `invalid` and its reason names `openspec/specs/`

### Requirement: The OpenSpec row reads waiting on the template pull request
The command SHALL print row 16 as `waiting`, with the number of the open template pull request in its reason, when the default branch holds no `openspec/config.yaml` and the head of that pull request holds the shipped OpenSpec files.

#### Scenario: A config file only on the template branch
- **WHEN** The default branch holds no `openspec/config.yaml` and the open template pull request holds it
- **THEN** Row 16 is `waiting` and its reason names that pull request

### Requirement: The shipped OpenSpec config is project-neutral
The command SHALL write the OpenSpec config file from `src/devops_cli/templates/openspec/config.yaml`, and that template SHALL hold a context line marked for a person to fill in and a `rules` entry for proposal, specs, design and tasks, and SHALL hold no text that names devops-cli.

#### Scenario: The template content
- **WHEN** The command writes the config file for a target repository
- **THEN** The written file equals `src/devops_cli/templates/openspec/config.yaml`, holds the marked context line and the four rules, and holds no devops-cli text

### Requirement: The OpenSpec files reach the repository in one pull request
With `--confirm`, the command SHALL add the OpenSpec config file from the shipped template and `openspec/specs/.gitkeep` to the one template pull request of row 9, and it SHALL NOT overwrite a file that the default branch or the head of that pull request holds. A second `--confirm` SHALL create no commit and no second pull request while that pull request is open.

#### Scenario: Both rows need files
- **WHEN** One run finds the label rule of #3742 and the `openspec` row missing
- **THEN** The command opens one pull request that holds `.github/labels.yml`, `openspec/config.yaml` and `openspec/specs/.gitkeep`

#### Scenario: A config file that already exists
- **WHEN** The default branch holds `openspec/config.yaml` with other text
- **THEN** The pull request adds no `openspec/config.yaml` and the existing file is unchanged

#### Scenario: A second confirm
- **WHEN** The user runs `--confirm` again while the template pull request is open
- **THEN** The command creates no commit and opens no second pull request

### Requirement: The merged tree passes the strict OpenSpec validation
After the template pull request merges, the pinned `openspec validate --specs --strict` SHALL exit 0 over the OpenSpec tree of the default branch, and a live test SHALL run that pinned command over the merged tree of a scratch repository that the git fake builds.

#### Scenario: A scratch repository
- **WHEN** The test merges the template pull request in a scratch repository that the git fake builds and runs the pinned `openspec validate --specs --strict` over the merged files
- **THEN** The run exits 0 and the default branch holds the OpenSpec config file and the specs placeholder

### Requirement: The onboard document describes the OpenSpec row
`docs/repos/onboard.md` SHALL describe the `openspec` row, its states, the shipped template and `openspec/specs/.gitkeep`, and `uv run devops ci docs` SHALL exit 0 on the document.

#### Scenario: The onboard document
- **WHEN** A reader opens `docs/repos/onboard.md` after the merge
- **THEN** The document names `present`, `missing`, `invalid` and `waiting`, the marked context line and `openspec/specs/.gitkeep`, and `uv run devops ci docs` exits 0

## MODIFIED Requirements

### Requirement: One row for each step
`devops repos onboard <owner>/<name>` SHALL print rows 0 to 16 in order: preflight, create, repository, security, Code Quality, environment, release secret, App check, labels, template pull request, ruleset, ready, webhook, Service, cluster, RAG and OpenSpec. Each row SHALL show its number, its name, its state and the changes, the reason or the person step of the state. `--only <row>,...` SHALL run only the named rows.

#### Scenario: An onboarded repository
- **WHEN** a fake GitHub holds a repository that matches the baseline, including `openspec/config.yaml` and `openspec/specs/.gitkeep`, and `--plan` runs
- **THEN** each row from 0 to 16 is `present`, `skipped` or `not available`, and the command exits 0

#### Scenario: Only one row
- **WHEN** `--only 8` runs
- **THEN** the output holds row 8 and no other step row
