# Proposal: #3917

## Why

Four articles in `src/devops_cli/ai/knowledge_base/devops_cli/` (`architecture.md`, `cli_command_reference.md`, `configuration_and_settings.md`, and `python_packages.md`) only copy generated documentation, standards documents, `pyproject.toml`, or `uv.lock`, causing drift findings while `CONST_KB_METADATA_TARGET_SUBDIRS` enforces front matter on only 3 of the 4 knowledge base subfolders. Per the 2026-11-11 owner decision, the knowledge base stays as a source of the project brain while copy articles are removed and front matter covers every article. Closes #3917.

## What Changes

- Delete `src/devops_cli/ai/knowledge_base/devops_cli/architecture.md`, `cli_command_reference.md`, `configuration_and_settings.md`, and `python_packages.md`, and remove all reader/test references to those four files (`knowledge_base/README.md`, `tests/ai/test_kb.py`, `tests/docs/test_docs_inventory.py`).
- Add `reviewed`, `sources`, and `applies_to` YAML front matter to every remaining article under `src/devops_cli/ai/knowledge_base/devops_cli/tasks/`.
- Widen `CONST_KB_METADATA_TARGET_SUBDIRS` in `src/devops_cli/config/constants.py` to include `devops_cli/tasks` so front matter is required across every article subfolder of the knowledge base, and add `kb_metadata_problems` in `src/devops_cli/ai/kb.py`.
- Regenerate `docs/KNOWLEDGE_BASE.md` with `uv run devops docs generate` and update `docs/SDLC.md` to state that the repository tree copy is the single knowledge base source (with live Qdrant purge and eval comparison deferred to split issues #6578 and #6579).

## Capabilities

### New Capabilities

- `project-brain/kb-front-matter`: Whole-tree knowledge base front-matter validation (`reviewed`, `sources`, `applies_to`) across every article subfolder in `CONST_KB_METADATA_TARGET_SUBDIRS` with single-source non-duplicated articles.

### Modified Capabilities

- None.

## Impact

- Deleted KB files: `src/devops_cli/ai/knowledge_base/devops_cli/{architecture,cli_command_reference,configuration_and_settings,python_packages}.md`
- Modified KB/code/docs: `src/devops_cli/ai/knowledge_base/README.md`, `src/devops_cli/ai/knowledge_base/devops_cli/tasks/*.md`, `src/devops_cli/config/constants.py`, `src/devops_cli/ai/kb.py`, `docs/KNOWLEDGE_BASE.md`, `docs/SDLC.md`
- Tests: `tests/ai/test_kb.py`, `tests/docs/test_docs_inventory.py`, `tests/review/test_kb_manuals_metadata.py`

## Feasibility

- `src/devops_cli/config/constants.py:5757` defines `CONST_KB_METADATA_TARGET_SUBDIRS` (`devops_cli/libraries`, `it_domains/tools`, `it_domains/topics`), read by `src/devops_cli/ai/kb.py:639` and tested by `tests/review/test_kb_manuals_metadata.py`. Adding `devops_cli/tasks` covers every remaining subfolder after deleting the 4 copy articles directly under `devops_cli/`.
- Split follow-ups #6578 and #6579 already hold the live Qdrant `devops-cli-kb` purge and post-merge eval score comparison.

## Existing Tool Considered

Uses the existing `KbFrontMatter` validator and `parse_manual_front_matter` in `src/devops_cli/ai/kb.py` together with `CONST_KB_METADATA_TARGET_SUBDIRS` rather than building a second validator. Estimated build cost: ~15,000 tokens and <1 hour.
