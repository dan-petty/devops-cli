# Task: A Pull Request That Changes the Docs Builds the Pages Site (#1651)

**Issue**: [#1651](https://github.com/dan-petty/devops-cli/issues/1651)
**Scope**: scope/ci
**Feasibility**: On 2026-10-23, `docker buildx imagetools inspect ghcr.io/actions/jekyll-build-pages:v1.0.13` gave `sha256:6791ebfd912185ed59bfb5fb102664fa872496b79f87ff8b9cfba292a7345041`. This is the image that `action.yml` of `actions/jekyll-build-pages` v1.0.13 (commit `44a6e6be`, the latest release) names. The build step of the job ran locally, with no network and `docs/` mounted read-only. It built the tip in 4 s after a pull of 13 s. With an `if` tag that never closes in `docs/VISION.md`, it exited 1 and logged `Liquid Exception: ... in VISION.md`. The build log names `docs/_config.yml` as the only configuration file that the builder reads.

## Description

- [x] **Docs-site job** (`.github/workflows/ci.yml`, `Docs Site Build`): on a pull request, `dorny/paths-filter` v4.0.3 reads the changed files. When `docs/**` or `ci.yml` changed, the job checks out the tree and runs the Pages builder by digest, with `docker run --network none` and `docs/` mounted read-only.
- [x] **Limits**: the job holds `contents: read` and `pull-requests: read`, keeps no checkout credentials and stops after 10 minutes. Its `if` names no branch, and no other job needs it.
- [x] **Skip**: on a pull request that changes neither path, the job skips the checkout and the build, and the check reports success.
- [x] **No token, no writes**: the container has no network and a loopback resolver (`--dns 127.0.0.1`). The GitHub metadata plugin of the builder checks the network with a DNS lookup, catches the failed lookup, and makes no API call, so the build needs no token. Without the loopback resolver, the lookup to the runner's resolver raises `Errno::ENETUNREACH`, which the plugin does not catch, and the build fails. The built site stays inside the container.
- [x] **Test** (`tests/test_workflow_contracts.py`): `test_a_pull_request_that_changes_the_site_builds_it_with_the_pages_builder` holds the condition, the permissions, the time limit, the filter, the checkout credentials, the digest and the `docker run` command. It also checks that no job needs the docs-site job. It failed before the change.
- [x] **Documents**: Phase 4 of `docs/SDLC.md` describes the job. The header of `docs/_config.yml` names it.
- Not done: the image-pins check of the Argo CD overlay moves to its own item, #1994.
- Pending a person: the owner decides whether the `main` ruleset requires `Docs Site Build`.
- Pending a person: on a pull request, add an `if` tag that never closes to a file under `docs/`. Check that `Docs Site Build` fails, then remove the tag and check that it passes.
- Pending a person: on a pull request that changes no file under `docs/` and not `ci.yml`, check that `Docs Site Build` skips its build and reports success.

## Notes

`check_argocd_gate` already builds every Argo CD Application of this repository with `kubectl kustomize` on each pull request. `test_this_repository_passes_the_argocd_gate` in `tests/test_k8s_argocd_apps.py` calls it in `Tests & Coverage` and takes about 1 s. The runner image has `kubectl` 1.37.1. So this change adds no second caller of the gate.
