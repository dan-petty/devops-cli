# Design

## Decisions
- A pull request image job reads the BuildKit `gha` cache and writes none. GitHub keeps the cache of a pull request in the scope of its merge ref, so only a new run of the same pull request can read it. The measured cache list shows these entries as 11.24 GB of the 12.83 GB, and the eviction then removes the layers of `main`.
- The release writes the cache once for each image, in the `Build and Push` step. The `Build and Load` step and the `Build and Push` step of a job use the same Buildx builder, so the second build takes the layers of the first from the local store, and its export holds all the stages of the image with `mode=max`. One export for each job is enough, and the cache then holds the layers of the image that the release publishes.
- The export stays in `release.yml`, not in a push run of `ci.yml`. The image jobs of `ci.yml` run only on a pull request and on a manual run, and the release builds the same images on `main` at each release, 4 to 9 times each day (CI audit of 2026-11-11). A new job on each push to `main` would add runner time for each merge.
- The export keeps the default error behavior: a failed export fails the release job, as it did before. The change does not add `ignore-error=true`, which would hide a failed export.
- The scope of each image stays out of this change. #4928 sets `scope=<target>` on each `type=gha` entry and adds its own invariant test, README sentence and spec requirement.

## Rejected alternatives
- Keep the pull request export with a scope for each pull request: GitHub still keeps the entries in the merge ref, which no other pull request reads, so they fill the cache as before (11.24 GB measured).
- Write the cache from only one release job, as the issue text says ("one scoped `cache-to`"): the export of one target holds only the stages of that target. The `mcp-server` export holds `runner-deps` but not `service-deps`, and the `service` export holds `service-deps` but not `runner-deps`. So the other images would build their own dependency stages again on each pull request. One export for each job keeps the stages of each image, and #4928 then puts each in its own scope.
- `mode=min`: it exports only the layers of the final image, not the `lock`, `deps` and `builder` stages that a pull request needs.
- A registry cache in GHCR (`type=registry`), as the DevContainer image uses: it has no 10 GB limit, but each pull request job then needs a GHCR login and `packages: read`, and the release publishes three more cache images. With no pull request writes, the `gha` cache holds only the release layers and the small caches of the other jobs (1.5 GB of entries that are not BuildKit entries, measured), so the issue keeps the `gha` backend.
