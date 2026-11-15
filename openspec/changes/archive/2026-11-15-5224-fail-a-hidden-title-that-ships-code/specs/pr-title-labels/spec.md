## ADDED Requirements

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
