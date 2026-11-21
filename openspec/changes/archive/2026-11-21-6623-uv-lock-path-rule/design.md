# Design

## Decisions
- **The rule is a path rule at one place.** `is_release_path` decides, and `release_conflict` calls it for the plan and for the round, so both stop on the same paths.
- **The version line counts only in `pyproject.toml`.** release-please writes the version there and into the `devops-cli` block of `uv.lock` (`extra-files` of `release-please-config.json`). `uv lock` writes that block again from `pyproject.toml`, and the other package versions of `uv.lock` come from the resolver, so tier 1 makes the whole file again.
- **The `__version__` check goes.** No file under `src/` sets `__version__`. A conflict on another file stops anyway, because tier 1 does not settle it.

## Rejected alternatives
- **Skip only `uv.lock` in the diff rule.** It keeps a rule that reads the diff of each path, which is the cause of #6623. The owner chose a path rule on 2026-11-21.
- **Merge `uv.lock` by hand.** Tier 1 takes the side of the default branch and runs `uv lock`, which resolves the versions again with no hand merge.
