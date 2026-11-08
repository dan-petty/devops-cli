# Design

## Decisions

- **Add `src/devops_cli/ai/knowledge_base/` to `_NO_SPEC_PREFIXES`**: The knowledge-base manuals are documentation files. A change that edits manuals does not change observable software behavior.
- **Add helper `_is_no_spec_path`**: The helper returns true for prefixes in `_NO_SPEC_PREFIXES`. It also returns true for paths ending in `.md` outside `src/`.
- **Keep task prompts under `src/devops_cli/ai/tasks/` observable**: A markdown file under `src/` changes model behavior unless it is in the knowledge base. It keeps a spec delta.
- **Keep `pyproject.toml` observable and defer case 2163**: A path-only check cannot tell a tool setting from a dependency change. Issue #3491 tracks a diff-aware rule.
- **Set gate `paths` on case 2526 and remove reason**: Case 2526 changes only root documents with a spec delta. The updated rule catches this defect.

## Rejected alternatives

- **Treat every `.md` file as no-spec**: A task prompt under `src/devops_cli/ai/tasks/` changes model behavior, so it must stay observable.
- **List each root document by name**: A new root document would need a code change.
- **Add `pyproject.toml` to `_NO_SPEC_PREFIXES`**: That would hide dependency or entry point changes that consumers observe.
- **Parse `pyproject.toml` in the stage check**: The stage check receives paths, not diff contents.
