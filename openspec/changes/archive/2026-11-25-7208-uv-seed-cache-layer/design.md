# Design

## Decisions
- The seed follows the pattern of the other images: dependency layers read the `lock` stage only.
- A stub project puts the build backend into the cache, by the same editable build as a sync of a checkout. So the file names no build package.
- The index pages that `uv pip sync` leaves are removed. A sync of a lock file does not read them.

## Rejected alternatives
- `uv sync --no-install-project` on `uv.lock`: the file changes with each release.
- A rewrite of the version in `uv.lock`: it edits a generated lock file.
- A list of the build packages in the stage: it misses what the backend asks for at build time.
