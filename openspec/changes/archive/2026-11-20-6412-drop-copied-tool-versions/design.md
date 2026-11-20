# Design

## Decisions
- The CycloneDX tool entry keeps `vendor` and `name`. The schema makes `version` optional, and the version of the scanner that ran is not a fact that the adapter reads.
- The seed of the empty-database digest is a fixed string with no version. The digest identifies the content of the cache, and an empty cache has no content that changes with the scanner.
- The scaffold has no `features` key on any path. The published image holds `common-utils` (the user `vscode`) and `podman-in-podman`, and its label gives them to a child repository. An image that `--image` names must hold the same, because the scaffold cannot know which tools that image has.
- The published path of the scaffold does not set `DOCKER_HOST`. The `remoteEnv` of `.devcontainer/image/devcontainer.json` goes into the `devcontainer.metadata` label, so the child repository gets `DOCKER_HOST` from the image, as `.devcontainer/devcontainer.json` of devops-cli does.
- The extension list of the scaffold is the same as the list in `.devcontainer/devcontainer.json`.
- The knowledge base names the owners of the versions (`pyproject.toml` and `uv.lock`) and no version.

## Rejected alternatives
- Update the copied versions to the values of `uv.lock`: `python_packages.md` already has pins that differ from `uv.lock`, so each copy drifts again at the next Renovate update.
- Keep the copies and add a check that compares them with `uv.lock`: the owner rule of 2026-11-19 forbids a test that compares pins across files, and the check keeps two sources.
- Keep the `features` block for `--image` and update it: the block already drifted (`node:1` against `node:2`), and it copies the tools of the image.
- Add `remoteEnv` `DOCKER_HOST` to the published path of the scaffold: the image label already sets it, and the smoke action of the image checks the value. A copy in the template drifts when the image changes.
