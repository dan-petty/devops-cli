# Design

## Decision

The `latest` rule is part of `devops k8s image-pins`. After the render sorts the images, an image that names no digest, and names the `latest` tag or no tag, goes to `ImagePins.latest` and not to `pinned` or `local`. The command refuses these images before it resolves anything, so a refused pull request spends no Docker Hub pull. An image whose repository an `ImageUpdater` object names is not checked: Image Updater writes its tag and digest into the live Application.

An untagged image counts as `latest`. The reference grammar gives a reference with no tag the tag `latest`, so `example/app` and `example/app:latest` pull the same image. The issue limits kube-linter's block list to `.*:(latest)$` only because kube-linter cannot tell the untagged service image from other untagged images. The render can tell them apart, because it knows the repositories that Image Updater moves. Today no rendered image is untagged except the service image.

An image with a digest is a pin whatever its tag: `example/app:latest@sha256:<digest>` always pulls that digest.

The chart render adds `--skip-tests`. Argo CD does not apply a Helm test hook, so a test pod's image is never pulled. Without the flag, the `qdrant` chart's test pod (`registry.suse.com/bci/bci-base:latest`) fails the check, and its images and those of other test pods are resolved for nothing.

## Rejected alternatives

- **A kube-linter custom check over `k8s/`** (the issue's proposal). kube-linter 0.8.3 passes a copy of `k8s/` in which a value file sets `tag: "latest"`, because it reads raw files and does not render a chart with the repository's value files. Five value files set an image tag today.
- **kube-linter over the rendered output.** It needs the render written to a tree, a kube-linter install in the job, and a config file, to read the same `image` values that the render already holds. It also cannot tell an Image Updater image from another untagged image.
- **Leaving out every Helm hook that Argo CD does not apply.** Argo CD's guide says that its skip "is not totally congruent with --skip-tests": it also skips `pre-rollback`, `post-rollback` and `test-failure` hooks. No chart of the repository renders one of these. With `--skip-tests` only, such a hook's image is still checked, which is stricter, not weaker. A filter on the hook annotation would copy Argo CD's hook table into this module.
- **Disabling each chart's tests in its value file**, as `k8s/gitea/values.yaml` does for its connection test. Each new chart would need the same line, and the check would fail until someone adds it.
