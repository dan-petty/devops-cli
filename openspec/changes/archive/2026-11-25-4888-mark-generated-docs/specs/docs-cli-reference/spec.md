## ADDED Requirements

### Requirement: Generated documents carry the linguist-generated attribute

`.gitattributes` SHALL set `linguist-generated=true` for every glob of the generated class of `CONST_DOCS_INVENTORY`, and tracked Markdown files outside that class (except `CHANGELOG.md`, already marked generated for `release-please`) MUST remain `unspecified`. A missing glob line in `.gitattributes` MUST fail the attribute check and name both the glob and the missing attribute.

#### Scenario: Generated and hand-written attributes match inventory

- **WHEN** `git check-attr linguist-generated` checks every tracked Markdown file
- **THEN** each file matching `CONST_DOCS_INVENTORY["generated"]` prints `true` and every non-generated, non-`CHANGELOG.md` tracked Markdown file (including `README.md`) prints `unspecified`

#### Scenario: Missing generated glob fails attribute check

- **WHEN** a glob is added to `CONST_DOCS_INVENTORY["generated"]` without a line in `.gitattributes`
- **THEN** the attribute check fails and names the missing glob and `linguist-generated=true`

### Requirement: Review skip reads the generated class from inventory

`is_secret_scan_only` SHALL return `True` for every path matching `CONST_DOCS_INVENTORY["generated"]`, and `CONST_REVIEW_ROUTED_PATH_PATTERNS` MUST NOT contain `docs/commands/*.md`, `docs/CLI_REFERENCE.md`, or any generated glob.

#### Scenario: Dynamically added generated glob is skipped by review

- **WHEN** a glob is added to `CONST_DOCS_INVENTORY["generated"]` and passed to `is_secret_scan_only`
- **THEN** `is_secret_scan_only` returns `True`

### Requirement: CONTRIBUTING.md documents the generated-file rebase conflict step

The Documentation Synchronization bullet of `CONTRIBUTING.md` SHALL document running `git checkout --ours -- <file>`, `git rebase --continue`, and `uv run devops docs generate`.

#### Scenario: Conflict procedure appears beside docs generation

- **WHEN** a contributor reads the Documentation Synchronization bullet in `CONTRIBUTING.md`
- **THEN** it names `git checkout --ours -- <file>`, `git rebase --continue`, and `uv run devops docs generate`
