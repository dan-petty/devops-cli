# Design

## Decisions

- **Delete the 4 duplicate articles and keep the tree**: Remove `architecture.md`, `cli_command_reference.md`, `configuration_and_settings.md`, and `python_packages.md` from `src/devops_cli/ai/knowledge_base/devops_cli/`. Update `src/devops_cli/ai/knowledge_base/README.md`, `tests/ai/test_kb.py`, and `tests/docs/test_docs_inventory.py` so no reader or test pins them.
- **Cover all remaining articles with one subfolder list**: Widen `CONST_KB_METADATA_TARGET_SUBDIRS` in `src/devops_cli/config/constants.py` to `("devops_cli/libraries", "devops_cli/tasks", "it_domains/tools", "it_domains/topics")`. Because `CONST_KB_METADATA_TARGET_SUBDIRS` lists all four article directories and tests verify equality with the directory tree, any new article directory or article lacking `reviewed`, `sources`, or `applies_to` fails CI immediately.
- **Metadata validator helper**: Add `kb_metadata_problems(kb_dir: Path | None = None) -> list[str]` in `src/devops_cli/ai/kb.py` using existing `parse_manual_front_matter`, checking every non-`README.md` Markdown article under `kb_dir`.
- **Documentation updates**: Update `docs/SDLC.md` to record that the repository tree copy is the single knowledge base source, and regenerate `docs/KNOWLEDGE_BASE.md` via `uv run devops docs generate`.

## Rejected alternatives

- Adding a separate validator for `devops_cli/tasks/` or a pre-commit hook (rejected: duplicates `CONST_KB_METADATA_TARGET_SUBDIRS` and `parse_manual_front_matter`).
- Deleting the entire `knowledge_base/` directory (rejected by the 2026-11-11 owner decision).
