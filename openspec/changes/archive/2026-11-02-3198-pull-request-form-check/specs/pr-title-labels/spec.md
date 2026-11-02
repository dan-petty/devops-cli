## MODIFIED Requirements

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

## REMOVED Requirements

### Requirement: A scope with no declared label gets no label and a warning
**Reason**: `devops pr create` refuses a title whose scope has no label before it opens the pull request, so no pull request is open to get a warning. The requirement "The title has a type, a declared scope and a short summary" and the scenario "A scope with no label" of the capability `pull-request-form` hold the new behavior.
**Migration**: Declare the label of the scope in `.github/labels.yml` (in the same pull request when the scope is new), or use a scope that has a label.
