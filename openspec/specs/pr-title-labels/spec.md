# pr-title-labels Specification

## Purpose
How `devops pr create` gives the pull request it opens the `type/*` and `scope/*` labels that its Conventional Commit title gives, with the rule of intake, and what the command does when a label cannot be added to a pull request that exists.

## Requirements

### Requirement: The title gives the labels of a new pull request
After `devops pr create` opens a pull request, it SHALL add the `type/*` label that the Conventional Commit type of the title names, and `scope/<scope>` when the title has the scope `<scope>`, each only when `.github/labels.yml` on the base branch declares it. It SHALL use the rule of intake, so `fix` gives `type/bug`. A title with no scope SHALL give only the type label. A title with no type, or a scope with no label, is refused before the pull request opens (capability `pull-request-form`).

#### Scenario: A fix with a scope
- **WHEN** `devops pr create --title "fix(ai): a title"` with a body in the form opens pull request 14
- **THEN** pull request 14 holds `type/bug` and `scope/ai` and no other label

#### Scenario: A title with no scope
- **WHEN** `devops pr create --title "docs: a title"` with a body in the form opens a pull request
- **THEN** the pull request holds `type/docs` and no scope label

#### Scenario: A title with no type
- **WHEN** `devops pr create --title "A plain title"` runs
- **THEN** the command exits 1 and opens no pull request, so no label is added

### Requirement: A label that cannot be added is reported and the pull request stays
When the label file cannot be read, the command SHALL stop before it opens the pull request and name the file. When a label cannot be added after the pull request opened, it SHALL print an error that names the pull request number, each label not added, the reason, and the `devops gh api` command that adds a label by hand, and SHALL exit 1. It SHALL try every label, SHALL NOT close or delete the pull request, and SHALL still set the Status of the item that the pull request closes.

#### Scenario: One label is refused
- **WHEN** GitHub refuses `type/bug` for pull request 14 and accepts `scope/ai`
- **THEN** the command exits 1 and its error names pull request 14, `type/bug` and the reason
- **AND** pull request 14 holds `scope/ai`, and the command sent no request that closes it

#### Scenario: The label file is missing
- **WHEN** the repository has no `.github/labels.yml` on the base branch
- **THEN** the command exits 1, its error names `.github/labels.yml`, and it sent no request that opens a pull request

### Requirement: A dry run adds no label and lists the label requests
`devops --dry-run pr create` SHALL read no label file and add no label. It SHALL list the requests that a real run would send: the read of the label file on the base branch, and one label request for each label that the title asks for, with the pull request number as the placeholder `<number>`.

#### Scenario: A dry run
- **WHEN** `devops --dry-run pr create --title "fix(ai): a title"` runs with a body in the form
- **THEN** the command opens no roadmap store and sends no request
- **AND** its output lists the read of `.github/labels.yml` and the label requests for `type/bug` and `scope/ai` for `repos/<repo>/issues/<number>/labels`

### Requirement: The labels agree with the audit
A pull request that `devops pr create` labeled from a title with a type and a scope SHALL pass the label audit of `github/labels.py`.

#### Scenario: Audit passes after creation
- **WHEN** `devops pr create --title "fix(ai): a title"` with a body in the form opens a pull request and the audit runs on it
- **THEN** the audit reports no finding

### Requirement: A hidden title type ships no runtime code
The pull request title check SHALL refuse a title whose type `release-please-config.json` marks hidden when the pull request changes a path under `src/devops_cli/` that does not end with `.md`. The refusal SHALL name the type, the paths and the types that the config shows. A change of documents only SHALL pass, and so SHALL a visible type with the same code change.

#### Scenario: A docs title with runtime code
- **WHEN** a pull request titled `docs(cli): remove the sync` changes `src/devops_cli/commands/docs.py`
- **THEN** the check fails and names `docs`, the path and `feat`

#### Scenario: A docs title with documents only
- **WHEN** the pull request changes `docs/CLI_REFERENCE.md` and `src/devops_cli/ai/knowledge_base/tools/helm.md`
- **THEN** the check passes

#### Scenario: A visible type with runtime code
- **WHEN** a pull request titled `refactor(cli): remove it` changes `src/devops_cli/commands/docs.py`
- **THEN** the check passes

#### Scenario: The config decides the hidden types
- **WHEN** a test marks `feat` hidden in the config
- **THEN** a `feat` title with runtime code is refused
