# Proposal

## Why

The `DevContainer Image` check fails while it installs devcontainer features from the internet: the Helm install of the `kubectl-helm-minikube` feature cannot reach its keyserver, and the `docker-in-docker` feature reads an empty compose checksum. Each version option says `latest`, so each build looks up a release and its checksum at build time, and one commit failed three attempts in two different ways (#3612).

## What Changes

- Pin the version options of the `docker-in-docker` and `kubectl-helm-minikube` features in `.devcontainer/image/devcontainer.json`, so the image build downloads a named release and no `latest` lookup runs.
- Set the kubectl and Helm options to the releases that the image already installs, and set an explicit Docker Compose release for the docker-in-docker feature.
- Add invariant cases to `tests/invariants/test_devcontainer_config.py` that fail on a `latest` option, on a docker-in-docker feature with no Compose release, and on a feature that the lockfile beside its config does not hold, and that name the config path, the feature id and the option name.
- Document the pinned feature releases and their bump in `docs/DEVCONTAINER_USAGE.md`.
- The change carries no spec delta: it pins the inputs of the image build and adds an invariant over committed files, so no behavior that a consumer observes changes.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- Code: `.devcontainer/image/devcontainer.json`
- Documents: `docs/DEVCONTAINER_USAGE.md`
- Tests: `tests/invariants/test_devcontainer_config.py`

## Feasibility

- `read_file` of `.devcontainer/image/devcontainer.json` showed the four option values that start a release lookup at build time: `.devcontainer/image/devcontainer.json:17:"version": "latest",`, `.devcontainer/image/devcontainer.json:22:"version": "latest",`, `.devcontainer/image/devcontainer.json:23:"helm": "latest",` and `.devcontainer/image/devcontainer.json:24:"minikube": "latest",`. `search_code` for `dockerComposeVersion` found no line of the commit, so the docker-in-docker feature names no Compose release today.
- The issue names the `devcontainer` job of `.github/workflows/ci.yml`, and no such job is there: `read_file` of `.github/workflows/devcontainer-image.yml` showed it at `.github/workflows/devcontainer-image.yml:46:devcontainer:` under the check name `DevContainer Image`, and that workflow's filter holds `.github/workflows/devcontainer-image.yml:16:- ".devcontainer/**"`, so the check builds the image on the pull request that pins it. The plan targets the image config and no job of `ci.yml`.
- The probe line confirms the two configs of the plan, word for word: "The path `.devcontainer/devcontainer.json` is a file of the staging commit." and "The path `.devcontainer/devcontainer-lock.json` is no file at the root of the staging commit. These files of the commit are candidates: `.devcontainer/image/devcontainer-lock.json`, `tests/fixtures/research/repo/.devcontainer/devcontainer-lock.json`. Commit a19a3b7f 2026-11-09 build(devcontainer): use the published image and drop cache volumes (#4252) deleted or renamed it."
- `read_file` of `.devcontainer/devcontainer.json` showed a config that names the published image at `.devcontainer/devcontainer.json:3:"image": "ghcr.io/dan-petty/devops-cli/devcontainer:latest",` and holds no `features` key in its first 30 lines; the invariant holds the same fact at `tests/invariants/test_devcontainer_config.py:81:assert ("build" in workspace, "features" in workspace) == (False, False)` and the absence of a lockfile beside it at `tests/invariants/test_devcontainer_config.py:83:assert not (DEVCONTAINER / "devcontainer-lock.json").exists()`. The plan pins the image config and covers the workspace config as a config that names no feature.
- `read_file` of `.devcontainer/image/devcontainer.json` counted 7 features and 13 option values, 4 of them `latest`, and `read_file` of `.devcontainer/image/devcontainer-lock.json` counted 7 `resolved` digests. Each of the 13 members is decided: the 4 `latest` values become explicit releases, and the other 9 stay, being 5 booleans and 4 strings that name a user, a uid or the Node major. The workspace config adds 0 option values, and its 0 features need no lockfile.
- `search_code` for `get.helm.sh` and `read_file` of `src/devops_cli/tools_lock/tools.lock` showed the pins the image already installs: `.devcontainer/Dockerfile:19:# kubectl 1.37.2`, `src/devops_cli/tools_lock/tools.lock:55:version = "1.37.2"`, `.devcontainer/Dockerfile:41:# helm 4.3.2` and `src/devops_cli/tools_lock/tools.lock:105:version = "4.3.2"`, so the kubectl and Helm options take a version that the staged tree holds.
- `search_code` for `kubectl` found no version pin of Minikube in the tree: the only option line is `.devcontainer/image/devcontainer.json:24:"minikube": "latest",`, so the Minikube, Docker and Compose releases are chosen at implementation time from each publisher, and no test of the tree can compare them with a pin.
- No lockfile edit belongs to this plan: each of the 7 entries holds the digest of a feature artifact, as at `.devcontainer/image/devcontainer-lock.json:30:"resolved": "ghcr.io/devcontainers/features/kubectl-helm-minikube@sha256:85bbe589703f8247b594ec821b028e7bb807d05c2bced61085403221ff71f1e5",`, and an option value changes no artifact, so the build keeps reading them with `.github/actions/devcontainer-image/action.yml:83:--frozen-lockfile \`.
- The invariant module already reads both configs at `tests/invariants/test_devcontainer_config.py:10:DEVCONTAINER = REPO_ROOT / ".devcontainer"`, and the `Tests & Coverage` check runs that module.
- The documentation target exists and holds a tooling section: `search_code` showed `docs/DEVCONTAINER_USAGE.md:31:## 2. Pre-Installed Tooling & Capabilities`.
- Not checked: the install script of each feature and its keyserver call. The Dev Containers CLI pulls each feature from its registry at build time, and no tool of this run reaches it, so the plan relies on the issue's report that a pinned option verifies the release's published checksum. The pull request's own `DevContainer Image` run proves that on the real system.
- The first checks against the real system: `uv run devops ci test tests/invariants/test_devcontainer_config.py` reads the checkout only; `uv run devops devcontainer validate --workspace .` reads the checkout only; `gh pr checks --watch` reads the `DevContainer Image` run of the pull request and needs a client of GitHub and a network.
- Each implementation-time release read needs a network and a client of the service: `gh api repos/docker/compose/releases/latest --jq .tag_name`, `gh api repos/kubernetes/minikube/releases/latest --jq .tag_name`, and the Docker CE index at download.docker.com. None runs in a `verify`.
- No verify program is new: each `verify` is the existing `uv run devops ci test` row or the existing `uv run devops ci docs` row. The programs are `uv`, `python`, `pytest` and `devops`, each in the runner image, and both rows read the checkout only, so a failing case stops the step with the class `test`; no network, cluster or scanner is needed, and the pod keeps `readOnlyRootFilesystem: true`, `runAsNonRoot: true` and `capabilities.drop: ALL`.

## Existing Tool Considered

The Dev Containers CLI (`@devcontainers/cli`, MIT, maintained) covers the feature pinning: `.github/actions/devcontainer-image/action.yml` builds with `--frozen-lockfile` against `.devcontainer/image/devcontainer-lock.json`, and Renovate's devcontainer manager writes that lockfile. No code is written for the pins, and the new cases only read the committed files.

## Dependencies

- Pull request #5796 changes `.devcontainer/Dockerfile`, which the image build also reads; this plan changes no line of that file, so the two merge with no conflict.
