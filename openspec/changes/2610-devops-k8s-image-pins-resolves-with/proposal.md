# Proposal

## Why

Issue #2610: `devops k8s image-pins` resolves each pinned image with `docker buildx imagetools inspect`. That command reads the manifest with a GET. Docker Hub counts a GET of a manifest as an anonymous pull of the caller's public address. Docker Hub does not count a HEAD request.

Fourteen of the 32 pins under the directory k8s are on Docker Hub. Each run spends 14 pulls. The nodes of the home cluster share that allowance, so a run can fail with `toomanyrequests`.

The project already has a HEAD resolver: `tag_digest` in `src/devops_cli/docker/registry.py` (#1997). This change uses it. The pin of an outside binary is not needed.

## What Changes

- `tagged_image` and `tag_digest` read a Docker Hub name (`nginx:1.27`, `valkey/valkey:9.1.2-alpine`, `docker.io/traefik:v3.7.16`, `index.docker.io/library/nginx:1.27`) and a reference with a digest. A Docker Hub name goes to the registry host `registry-1.docker.io`, and a name of one component goes under the prefix library.
- `image_reference` moves from `src/devops_cli/k8s/image_pins.py` to `src/devops_cli/docker/registry.py`. One reference split stays in the project.
- `resolve_image` and `resolve_image_pins` call `tag_digest` with the HTTP client of `new_http_client` at the public egress level. `inspect_command` goes. A dry run opens no client and sends no request.
- The dry-run message names the HEAD request, not the buildx command. The help text of the command and the documents that name `docker buildx imagetools inspect` change with it.
- The fake `ImagetoolsFake`, its recording, its record and its contract suite go. The tests double the registry at the HTTP edge with the existing `RegistryFake` and `stub_web`.
- `tools.lock` and the steps of the `image-pins` job do not change. Only the comment of the job changes.
- The change fits one pull request.
- Spec delta: the command, its message and its resolver are observable, so the change carries a delta in `k8s-image-pins`. It modifies two requirements.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `k8s-image-pins`: "Each pin resolves in its registry as an anonymous client" and "A dry run renders and resolves nothing".

## Impact

- Code: `src/devops_cli/docker/registry.py`, `src/devops_cli/k8s/image_pins.py`, `src/devops_cli/commands/k8s/image_pins.py`, `src/devops_cli/lang/en/messages.py`.
- Tests: `tests/docker/test_registry_tag_digest.py`, `tests/k8s/test_image_pins.py`. Deleted: `tests/support/fakes/imagetools.py`, `tests/support/imagetools_recording.py`, `tests/k8s/test_imagetools_contract.py`, `tests/fixtures/imagetools_runs/recorded_runs.json`.
- Documents: `docs/SDLC.md`, `docs/TESTING.md`, `k8s/README.md`, the comment of the `image-pins` job in `.github/workflows/ci.yml`, and the generated `README.md`, `docs/CLI_REFERENCE.md` and `docs/commands/k8s.md`.
- Callers and tests that must keep passing: `check_pins` in `src/devops_cli/argo/image_pins.py` (`tests/argo/test_image_pins.py`), and the pin tests of the `image-pins` job in `tests/invariants/test_workflow_contracts.py`.

## Acceptance

The body of the issue lists the criteria of the first proposal (`crane`). The comment of intake and the refined design replace `crane` with `tag_digest`. This plan follows the refined design. The map below uses both lists.

- An anonymous HEAD of Docker Hub images leaves `ratelimit-remaining` unchanged (measured and recorded in the proposal): the measurement is in "Feasibility" below. It needs the network, so no test asserts it. Group 2 delivers the HEAD, and the spec has no scenario for the counter.
- `devops k8s image-pins` resolves with a HEAD request through `tag_digest`, not a GET: groups 2 and 3.
- The contract suite holds the record to the command and to the lock's version: replaced. The fake, its record and its contract suite are deleted, because no process runs any more: group 3. The tests double the registry at the HTTP edge: group 3.
- The `image-pins` job installs the pinned `crane`: replaced by "No new binary pin". No `crane`, no `buildx` and no `tools.lock` entry are needed. Group 5 checks that `tools.lock` has no change. Group 4 fixes the comment of the job.
- `src/devops_cli/k8s/image_pins.py` has no reference split of its own: group 1.
- `tagged_image` reads a name with no registry and a reference with a digest (comment of intake): group 2.
- Pending a person: none.

## Feasibility

Commands run on 2026-11-01 against `origin/main` at `6e8b4ca2` and against the real registries.

- The code exists as the issue says. `grep -n "def inspect_command\|def image_reference\|def resolve_image" src/devops_cli/k8s/image_pins.py` gives lines 97, 102, 313 and 336. The docstring of the module states the measure of 2026-10-29.
- The count. `collect_image_pins(Path("."))` on `origin/main` gives `pinned 32 hub 14 local 0 latest 0 managed 2`. The issue says 13 of 31, from before #2891. The conclusion is the same: 14 pulls for each run. No pin has a digest today.
- Docker Hub does not count a HEAD. An anonymous token for `ratelimitpreview/test`, then three `curl -sI` of its manifest on `registry-1.docker.io`: `ratelimit-remaining: 99;w=3600` each time, and `docker-content-digest` in the reply. Two GET requests of the same manifest then gave `ratelimit-remaining: 98;w=3600`. A GET costs one pull and a HEAD costs none.
- `tag_digest` does it with the project client. A short script read the allowance, then ran `tag_digest` on `registry-1.docker.io/library/traefik:v3.7.16`, `registry-1.docker.io/portkeyai/gateway:1.15.0` and `registry-1.docker.io/valkey/valkey:9.1.2-alpine` with `new_http_client(level=EgressLevel.PUBLIC)`. Each gave a `sha256:` digest. The allowance read `98;w=3600` before and `98;w=3600` after.
- The host matters. `curl -sI https://docker.io/v2/library/nginx/manifests/1.27` gives `302` with `location: https://www.docker.com/v2/library/nginx/manifests/1.27`. `curl -sI https://registry-1.docker.io/v2/library/nginx/manifests/1.27` gives `401` with `www-authenticate: Bearer realm="https://auth.docker.io/token",service="registry.docker.io",scope="repository:library/nginx:pull"`. So `tag_digest` must send a Docker Hub name to `registry-1.docker.io`. `src/devops_cli/docker/registry.py` builds the URL from `image.registry` as written.
- `tagged_image` today does not read the forms that `src/devops_cli/k8s/image_pins.py` reads. A check with `uv run python` gave: `nginx:1.27` raises "names no registry host"; `docker.io/library/nginx:1.27` gives registry `docker.io`, which is the wrong host; `ghcr.io/o/a:1@sha256:<64 a>` gives repository `o/a:1@sha256` and a tag that is the digest text. A digest reference needs its own read: the HEAD goes to the manifest path of the digest.
- Nothing newer did it. `git log origin/main -- src/devops_cli/k8s/image_pins.py src/devops_cli/docker/registry.py tests/k8s/test_image_pins.py` shows #2891, #2617, #2614 and #2605 only. No other change folder in the directory openspec/changes names the capability k8s-image-pins or the module registry.py (`git grep` at `origin/main` finds none). The issue #2603 (docker-py types, then the split moves to its parser) is open and is not a dependency: the split stays hand-written until #2603.
- The dry run. In a dry run `kubectl kustomize` and `helm template` return a planned result with no output, so no image is found and no image resolves. The `planned` field of `PinResolution` can never be set by a run. The command must still not send a request: group 3 tests it.

## Existing Tool Considered

`crane digest` (go-containerregistry, Apache-2.0, maintained by Google) sends a HEAD. `regctl image digest` and `oras manifest fetch --descriptor` do the same. `skopeo inspect` and `docker manifest inspect` use a GET, as `imagetools` does.

The project already holds the same HEAD read: `tag_digest`, with the 401 Bearer handling, used by `devops argo cd apps status` and tested in `tests/docker/test_registry_tag_digest.py`. Using it adds no binary. The `crane` route adds a `tools.lock` entry, an installer step in the job, a process fake, recorded runs and a contract suite for the same read.

The change builds a small extension of `tagged_image` and `tag_digest` (Docker Hub names and digest references). Estimate for the written cost: about 40 changed lines in `registry.py` and about 6,000 tokens for the tests and the code, about 30 minutes. The upkeep is that of the existing registry tests.

The change deletes `inspect_command` and `image_reference` from `src/devops_cli/k8s/image_pins.py`, `ImagetoolsFake` in `tests/support/fakes/imagetools.py`, `tests/support/imagetools_recording.py`, `tests/k8s/test_imagetools_contract.py` and `tests/fixtures/imagetools_runs/recorded_runs.json`.
