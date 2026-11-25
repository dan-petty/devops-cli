# project-brain/kb-front-matter Specification

## Purpose

Require valid `reviewed`, `sources`, and `applies_to` YAML front matter on every article across all subfolders of the bundled knowledge base and forbid copy articles that only duplicate generated or locked project sources.

## Requirements

### Requirement: Copy articles removed without dangling references
The knowledge base SHALL contain none of `devops_cli/architecture.md`, `devops_cli/cli_command_reference.md`, `devops_cli/configuration_and_settings.md`, or `devops_cli/python_packages.md`, and no source module or test MUST reference those paths.

#### Scenario: Knowledge base tree and tests omit copy articles
- **WHEN** tests list Markdown files under `src/devops_cli/ai/knowledge_base` and inspect references in `src/` and `tests/`
- **THEN** none of the four copy articles or references to them exist.

### Requirement: Front matter required across every knowledge base subfolder
`CONST_KB_METADATA_TARGET_SUBDIRS` SHALL equal the full set of article subdirectories under `src/devops_cli/ai/knowledge_base`, and `devops_cli.ai.kb.kb_metadata_problems` SHALL report any article missing `reviewed`, `sources`, or `applies_to`.

#### Scenario: Article missing applies_to fails validation
- **WHEN** `kb_metadata_problems` checks a temporary knowledge base containing an article without `applies_to`
- **THEN** the returned problem list includes that article path and fails validation.
