# Design

## Decisions

- **Read `CONST_DOCS_INVENTORY[CONST_DOCS_CLASS_GENERATED]` directly in `is_secret_scan_only`**: Reading the existing documentation inventory at call time removes the duplicate generated-doc globs from `CONST_REVIEW_ROUTED_PATH_PATTERNS` and prevents the two lists from drifting apart.
- **Keep `.gitattributes` hand-maintained and verify with a tested helper**: `git check-attr` runs before Python tooling starts, so `.gitattributes` keeps explicit `linguist-generated=true` lines for all 11 globs alongside eol, binary, lockfile, and vendored lines, while a helper in `src/devops_cli/docs/inventory.py` fails when any generated glob lacks a matching line.
- **Place the conflict procedure in `CONTRIBUTING.md` Documentation Synchronization**: Putting `git checkout --ours -- <file>`, `git rebase --continue`, and `uv run devops docs generate` beside the doc generation instruction keeps one canonical contributor step without needing a custom merge driver in local git config.

## Rejected alternatives

- **Copy all 11 globs into `CONST_REVIEW_ROUTED_PATH_PATTERNS`**: Maintains two copies of the same list that drift whenever a generated doc is added.
- **Generate `.gitattributes` dynamically**: Unrelated eol, lockfile, and vendored rules belong in one hand-edited file checked by a test.
- **Configure a `merge=ours` git attribute driver**: GitHub ignores custom merge drivers, and local clones do not define an `ours` driver automatically.
