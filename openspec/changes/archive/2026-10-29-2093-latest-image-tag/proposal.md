# Proposal

## Why

Issue #2093: nothing stops an image with the `latest` tag from coming back under `k8s/`. Such an image is not a pin: each pull can get a different image. The service image `ghcr.io/dan-petty/devops-cli/service` has no tag in Git by design, because Argo CD Image Updater sets its tag and digest, so the check must pass for it.

## What Changes

- `devops k8s image-pins` refuses each rendered image that names no digest, and names the `latest` tag or no tag, which the reference grammar reads as `latest`. It exits 1 before it resolves an image, and the error names each such image and its Applications. An image whose repository an `ImageUpdater` object names stays out of the check, as before: Image Updater sets its tag and digest.
- The chart render runs `helm template --skip-tests`. Argo CD does not apply a Helm test hook, so the image of a chart's test pod is never pulled, and it is neither a pin nor a `latest` image. The `qdrant` chart's test pod names `registry.suse.com/bci/bci-base:latest`.
- The CI job `image-pins` already runs the command on each pull request that changes `k8s/`, so the job now fails on a `latest` image. The job does not change.
- Docs: `k8s/README.md` (Image Pins), `docs/SDLC.md` (the job), and the files that `devops docs generate --sync-readme` writes from the command's help.
- The command's behavior is observable, so the change carries a spec delta on `k8s-image-pins`.
- This change fits one pull request.

## Capabilities

### Modified Capabilities

- `k8s-image-pins`: the render leaves out Helm test manifests, and an image on the `latest` tag fails the check.

## Impact

- `src/devops_cli/k8s/image_pins.py`, `src/devops_cli/commands/k8s/image_pins.py`, `src/devops_cli/lang/en/messages.py`.
- `tests/k8s/test_image_pins.py`.
- `k8s/README.md`, `docs/SDLC.md`, and the files that `devops docs generate --sync-readme` writes.

## Feasibility

Checked on origin/main `29f5a745` (2026-10-29) with helm v4.3.0 and kube-linter 0.8.3, the versions of `tools.lock`:

- **Raw files.** `grep -rnE 'image:.*:latest' k8s/` finds no match.
- **Rendered images.** `collect_image_pins` (the render only, with no resolve) renders the Applications in 19.8 s and names 32 images. One names `latest`: `registry.suse.com/bci/bci-base:latest`, in the `qdrant` chart's Pod `qdrant-test-db-interaction`, which has the annotation `helm.sh/hook: test`. The only untagged image is `ghcr.io/dan-petty/devops-cli/service`, which the `ImageUpdater` object names.
- **Argo CD and test hooks.** Argo CD's Helm guide (`docs/user-guide/helm.md`, "Helm `--skip-tests`") says: "Argo CD currently skips manifests that include hooks not supported by Argo CD, including Helm test hooks." The hook map of gitops-engine (`pkg/sync/hook/helm/type.go`) maps only `pre-install`, `pre-upgrade`, `post-upgrade` and `post-install`. `helm template --skip-tests` of the `qdrant` chart 1.19.1 writes no test pod and no `bci-base` image.
- **After the change.** The render of the repository gives 29 pins and no `latest` image. The two images that only test pods name, `registry.suse.com/bci/bci-base:latest` (`qdrant`) and `docker.io/bats/bats:1.14.0` (`grafana`), are no longer pins, so each run reads one Docker Hub image less.
- **kube-linter cannot see a tag that a value file sets.** A custom check from the `latest-tag` template with the block list `.*:(latest)$` and `doNotAutoAddDefaults: true`:
  - reports `latest-tag-only` on a raw Pod with `image: example/app:latest`;
  - passes `k8s/` (exit 0, 0.1 s);
  - also passes a copy of `k8s/` in which `k8s/llm/values-open-webui.yaml` sets `tag: "latest"` (exit 0, "No lint errors found!").
  Five value files set an image tag (`argo-workflows`, the Argo CD Valkey, `gitea`, `open-webui`, `dcgm-exporter`).
- **`devops k8s lint`.** The bug that the issue names, #2095 (the command passed on findings and on a missing kube-linter), is closed as completed. This change does not need the command.

## Existing Tool Considered

- **kube-linter** (StackRox, Apache-2.0, pinned 0.8.3), as the issue proposes: a `.kube-linter.yaml` with the custom check, a CI step that installs kube-linter, and a lint of `k8s/`. It reads raw files only, so it misses each tag that a chart value file sets (measured above). To lint the rendered charts, the job would also have to write the render of `image-pins` to files and lint them: a second tool, a second step and a temporary tree for the same render.
- **The `image-pins` render** (#1994), chosen: it already runs `kubectl kustomize` and `helm template` with the value files, as Argo CD does, and already knows the repositories that Image Updater moves. The rule is one predicate on a reference that the module already splits. Written cost: about 3,000 tokens to build and test, nothing to keep while the reference grammar stands, minutes of elapsed time, and 0 s more in CI, because the job renders already.
- **The tag:** the predicate reads the tag with the same rule as `image_reference`. #2603 moves the module's reference split to the Docker SDK's parser.
- **Deleted code:** none.
