# Proposal

## Why

Issue #1994: nothing checks that the images pinned under `k8s/` exist. A wrong tag fails only when Argo CD syncs, after the merge.

## What Changes

- New command `devops k8s image-pins [ROOT] [--dry-run]` (`src/devops_cli/k8s/image_pins.py`, `src/devops_cli/commands/k8s/image_pins.py`):
  - It renders each Argo CD Application under `k8s/argocd/` as Argo CD does. A path source renders with the builder of the Argo CD gate (`kubectl kustomize`). A chart source renders with `helm template` and the value files of the repository, and the output then passes through `kubectl kustomize`, which reads YAML as Kubernetes does.
  - It takes each `image` value of the rendered objects, with `yaml.compose_all`, and does not resolve the images that an `ImageUpdater` object names or the images of a registry that only the cluster or the host reaches (an IP address, `localhost`, a name with no dot, or a name under `.svc`, `.cluster.local` or `.local`).
  - It resolves each other image once with `docker buildx imagetools inspect`, as an anonymous client, eight at a time, and exits 1 when a registry does not hold an image or refuses the read. The error names the image, its Applications, its registry and the resolver's own error line. `--dry-run` starts no render and no resolve.
- New error `ImagePinError` (`K8S_IMAGE_PIN_ERROR`).
- The command is not an MCP tool (`tests/test_mcp.py` lists it with the excluded commands): each run spends the Docker Hub allowance of the network's address, so an agent does not run it in a loop.
- New CI job `image-pins` in `ci.yml`, scoped like `docs-site`: a `dorny/paths-filter` step on `k8s/**`, `src/devops_cli/**/image_pins.py` and `ci.yml`, with `contents: read` and `pull-requests: read`. It installs the pinned helm with the lock's installer and runs the command.
- New shared fake `ImagetoolsFake` (`tests/support/fakes/imagetools.py`, fixture `imagetools`) that replays the real tool's recorded runs (`tests/fixtures/imagetools_runs/recorded_runs.json`, made by `tests/support/imagetools_recording.py`), with its contract suite `tests/k8s/test_imagetools_contract.py`.
- Docs: `docs/SDLC.md` (the job), `k8s/README.md` (Image Pins), `docs/TESTING.md` (the fake), and the regenerated command reference.
- The command's behavior is observable, so the change carries a spec delta: the new capability `k8s-image-pins`.
- This change fits one pull request.

## Capabilities

### New Capabilities

- `k8s-image-pins`: render the Argo CD Applications, sort the images they name, and resolve each pinned image in its registry before the merge.

## Impact

- `src/devops_cli/k8s/image_pins.py` (new), `src/devops_cli/commands/k8s/image_pins.py` (new), `src/devops_cli/commands/k8s/__init__.py`, `src/devops_cli/exceptions/k8s.py`, `src/devops_cli/lang/en/{help,messages}.py`.
- `.github/workflows/ci.yml`, `tests/test_workflow_contracts.py`, `tests/test_ci.py`, `tests/test_mcp.py`.
- `tests/k8s/test_image_pins.py`, `tests/k8s/test_imagetools_contract.py`, `tests/support/fakes/imagetools.py`, `tests/support/imagetools_recording.py`, `tests/fixtures/image_pins/`, `tests/fixtures/imagetools_runs/`.
- `docs/SDLC.md`, `docs/TESTING.md`, `k8s/README.md`, and the files that `devops docs generate --sync-readme` writes.

## Feasibility

Measured on origin/main `a95992aa` (2026-10-29), Docker Engine 29.9.2, buildx v0.38.1, helm v4.3.0:

- **No check exists.** `git grep` finds `imagetools` only in `release.yml` and its tests.
- **Images.** The 29 Applications (13 path sources, 16 chart sources) name 32 distinct images. One, `ghcr.io/dan-petty/devops-cli/service`, is the repository that the `ImageUpdater` object `devops` names, so 31 are pins, 13 of them on Docker Hub. Five value files set an image tag (`argo-workflows`, the Argo CD Valkey, `gitea`, `open-webui`, `dcgm-exporter`), so a check of the path sources alone would miss pins under `k8s/`.
- **YAML.** PyYAML refuses the `prometheus` chart's Alertmanager StatefulSet (a tab after `apiVersion: v1`), and so does ruamel.yaml; that document holds the pin `quay.io/prometheus/alertmanager:v0.34.1`. `kubectl kustomize` reads it, and `yaml.compose_all` then reads its output, also the lone `=` of a CRD schema that YAML 1.1 tags as `value`.
- **Time.** The command renders in 18.7 s (Applications eight at a time; the C loader of PyYAML) and resolves the 31 pins in 9.6 s; the whole command ran in 33 s on this host. Sequential renders with the pure-Python loader took 175 s.
- **The resolver.** `docker buildx imagetools inspect` is in the devcontainer and on the runner image, and `release.yml` already uses it. A resolved image prints the manifest with its digest and exits 0; a refused one exits 1 with one `ERROR:` line that names the cause (not found, pull access denied, a 403 on the anonymous token, `toomanyrequests`).
- **Anonymous.** With the developer's Docker configuration, GHCR refused 5 public images with 403 (a stored, refused credential); with an empty Docker configuration all 31 resolved. The cluster pulls without credentials, so the command resolves as an anonymous client.
- **Docker Hub counts the read.** Three anonymous inspects took Docker Hub's `ratelimit-remaining` from 100 to 97 (`ratelimit-limit: 100;w=3600`). Thirteen of the 31 pins are on Docker Hub. On the home network the measurements of this change spent the address's whole allowance, which the cluster's nodes share, and a run then failed with `toomanyrequests`. So the check runs as a CI job on a pull request that changes `k8s/`, and the help and `k8s/README.md` say so.

## Existing Tool Considered

- **The resolver:** `docker buildx imagetools inspect`, as the issue proposes, already present wherever the check runs. `crane digest` (go-containerregistry) resolves with a HEAD request, which Docker Hub does not count, but it needs a new pin in `tools.lock`, and a downloaded binary could not be run in this change's session to record it; #2610 holds the measurement. `skopeo inspect` (on the runner, not in the devcontainer) and `docker manifest inspect` read the manifest as imagetools does.
- **The render:** `kubectl kustomize` (the gate's builder) and `helm template`, the tools Argo CD itself runs, and PyYAML's composer. No parser is written.
- **The image reference:** the Docker SDK's `parse_repository_tag` and `resolve_repository_name` split a reference by the reference grammar, but the SDK ships no type information and `src` holds `type: ignore` at its ceiling of 51. `image_reference` writes the grammar's one rule (`splitDockerDomain`) in 10 lines instead, and a test holds it equal to the SDK on 12 references. Written cost: about 2,000 tokens to build and test, nothing to keep while the grammar stands, and minutes of elapsed time.
- **Deleted code:** none; no check of image pins existed.
