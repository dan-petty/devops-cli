# Design

## Decisions

- **Classify `pyproject.toml` changes by TOML table path**: When every changed key is under a `[tool.*]` table, the change is a tool setting and needs no spec delta. When a changed key is under `[project]` (dependencies) or `[project.scripts]` (entry points) or outside `[tool.*]`, it needs a spec delta.
- **Resolve table headers with line numbers and base content**: Use `unidiff` to parse hunks. Find the nearest table header by checking added table headers in the hunk, or searching backward in the base `pyproject.toml` from the hunk line.
- **Store `pyproject_diff` in `CaseFacts`**: `replay_case` reads recorded facts without git checkouts. Adding `pyproject_diff` to `CaseFacts` allows offline eval replay for case 2163.
- **Update case 2163 in golden set**: Set gate to `paths` and remove `reason` in `case.json`.

## Rejected alternatives

- **Treat all `pyproject.toml` changes as needing no spec delta**: This would hide dependency or entry point changes that consumers observe.
- **Treat all `pyproject.toml` changes as needing a spec delta**: This continues to fail case 2163 and rejects valid tool-only changes.
- **Hunk context only**: A table header can sit outside the three lines of diff context.
