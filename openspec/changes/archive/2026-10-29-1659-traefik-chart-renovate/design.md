# Design

## Target chart: 42.1.3, not 41.7.1

The issue named chart 41.7.1 (Traefik v3.7.14). Chart 41.7.1 is the last 41.x chart, and Traefik v3.7.15 and v3.7.16 fixed four more advisories after the issue was written. Only chart 42 ships them. Chart 42.0.0's three breaking changes need Kubernetes v1.30 or later and change only Traefik Hub settings; both clusters meet the first, and the values set no Hub value. The render of 42.1.3 differs from the render of 41.6.0 only in the image tag and the chart labels. So the newest chart, 42.1.3, is the target.

Rejected: 41.7.1. It leaves GHSA-p8wx-ph99-xgcr, -ww7c-q3mv-xx22, -28hp-c82p-8vqj and -hrpp-p4fc-wwf8 unfixed, and Renovate would propose chart 42 at once after the merge.

## The pin floor is a version, not one value

The test reads the Application's `targetRevision` as a version and requires 42.1.1 or later, the first chart that ships v3.7.16. A test that names one version would fail on each Renovate update.

## deploy-stack keeps its own version list, with a parity check

Renovate's `argocd` manager changes only `k8s/argocd/apps/*.yaml`. `deploy-stack` keeps its versions in `_HELM_RELEASES_BY_STACK`, so a new test requires each `deploy-stack` release to install a chart at a version that an Application pins.

Rejected: `deploy-stack` reads each version from the Application at run time. That removes the second declaration, but it changes how `deploy-stack` finds its releases, beyond this item. A Renovate chart pull request already needs a manual commit for the `_CHART_TOKENS` check (#1652: an entry names the chart version that its pods were read from), so the parity check adds no step to that commit.

Rejected: a Renovate regex manager over `stack_lifecycle.py`. A regex over a Python dict that spans several lines breaks on a reformat, and the chart name and the version are on different lines.

## The git sources stay off

Renovate reads each Application source with no chart as a `git-tags` dependency: the `ref: values` sources and the `path` sources, which track `main`. A rule turns those dependencies off. Argo CD tracks `main` on purpose (ADR 0013), and `main` is no version that a tag could replace.
