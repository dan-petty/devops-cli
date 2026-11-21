# Proposal: #6407

## Why

Issue #6407: the release builds the service, runner and mcp-server images two times. The first build loads the image, and the job smoke-tests and scans it. The second build pushes the image. The second build runs the stages of `no-cache-filters` again, so it can push an image that no step started or scanned. In release run 44828633787 (0.185.1), the config digest of each scanned image is not the config digest of the pushed image. The devcontainer image already goes through one build that pushes by digest, then a smoke test, an attestation and a tag of that digest.

## What Changes

- Add the called workflow `.github/workflows/release-image.yml` with three jobs for one image:
  - `Build` checks out the release commit, takes the labels from `docker/metadata-action` with the revision label of the release commit, and builds the image one time with `docker/build-push-action`: push by digest with no tag, `sbom: true`, `provenance: mode=max`, the `no-cache-filters` of the image, and the registry cache of its target.
  - `Verify` pulls that digest, runs the smoke test of the image that `ci.yml` runs, and scans the digest with `.github/actions/image-scan`. It holds `contents: read`, `packages: read` and `security-events: write` (the scan uploads its SARIF), and no OIDC token.
  - `Attest & Tag` attests the digest with `actions/attest`, puts the release tag and `latest` on it with `docker buildx imagetools create`, and fails when a tag does not resolve to the digest.
- In `release.yml`, one job `image` calls the workflow with a matrix over `service`, `runner` and `mcp-server` and `fail-fast: false`. The jobs `service-image`, `runner-image` and `mcp-server-image` go, with their three 'Build and Load' steps.
- The filters stay as on `main`: `service` for the service image, none for the runner image, and `mcp-server` for the MCP server image. The issue asked for `runner` and `runner,mcp-server`, but the runner stage now runs no `apt-get upgrade`, and the `mcp-server` stage no longer builds FROM `runner` (#4361, #6555).
- RELEASE_CYCLE.md names the new jobs. For a vulnerability that a new package outside the repository fixes, a person re-runs the `Build` job of the image. GitHub then re-runs its `Verify` and `Attest & Tag` jobs.
- The test of the old service job values goes (docs/TESTING.md: no test asserts a value of a config file). The smoke parity test, the attestation test and the release-please test read the new jobs. `docs/SDLC.md`, `docs/CLUSTER.md`, `docs/guidelines/production-readiness.md`, `k8s/README.md` and two comments of `ci.yml` describe the new order.

The change fits one pull request.

## Capabilities

### New Capabilities

- `release-images`: the release builds each of the three images one time, then verifies, attests and tags that digest, one image at a time.

### Modified Capabilities

- `mcp-server-image`: the release publishes the MCP server image in the new order.
- `roadmap-implement-runner`: the release publishes the runner image in the new order, and the smoke test and the scan of the release are in the `Verify` job.
- `ci-image-scan`: the release scans with the action in the `Verify` job.
- `container-image-layers`: the release builds of `release-image.yml` read and write the registry cache.

## Impact

- `.github/workflows/release-image.yml` (new), `.github/workflows/release.yml`, `.github/workflows/ci.yml` (comments only).
- Each image gets two more jobs in a release: the start of two runners and a pull of the digest. A failed `Verify` leaves a digest with no tag in the public package; Image Updater reads only `latest`, so no cluster runs it, and #4816 removes such digests.
- No command, option or message of `devops` changes.

## Feasibility

Read on 2026-11-20 against `origin/main` at `eec467723`.

- Release run 44828633787 (0.185.1): the 'Build and Load' and 'Build and Push' steps of each image job export other config digests. Service: `f283b2364f27` scanned, `99b340da6d77` pushed. Runner: `34f2143fa220` and `ecec6b463d0d`. MCP server: `bc1ddf7bc290` and `c1d9ff7e1154`. The second service build ran `apt-get upgrade` of stage `service` again.
- GitHub documents that a job that needs another job waits for all of its matrix legs and is skipped when one fails. It also documents that a matrix job can call a reusable workflow, one call for each leg, and that a called workflow can only keep or lower the permissions of its caller (docs.github.com, "Reuse workflows" and "Reusing workflow configurations").
- GitHub documents that a re-run of a specific job also re-runs the jobs that depend on it, and that the jobs that it does not re-run keep their outputs. In release-please `src/manifest.ts`, `findMergedReleasePullRequests` gives only merged pull requests with the label `autorelease: pending`, and the run that creates the release changes that label to `autorelease: tagged`. So **Re-run all jobs** creates no release, and each image job skips: the issue's instruction would publish nothing.
- `actions/attest-build-provenance` v4.2.2 calls `actions/attest` v4.2.1 with the same inputs. The README of `actions/attest` v4.2.2 (commit `1e69f48acb82`) says that with no `sbom-path` and no predicate input, it writes SLSA build provenance.
- `docker/metadata-action` v6.2.0 with `context: git` fails on the checkout of the release commit. `actions/checkout` fetches the commit with `--no-tags --depth=1` and gives a detached HEAD: `git show -s --pretty=%D` prints `grafted, HEAD`, and no branch, remote branch or tag contains HEAD. Then `inferRefFromHead` of the action throws `Cannot infer ref from detached HEAD`. The default `workflow` context runs no git command. In `getOCIAnnotationsWithCustoms`, a label of the `labels` input comes after the default labels in one `Map`, so it replaces the default revision.
- `Dockerfile`: stage `runner` builds FROM the devtools image and runs no `apt-get upgrade`; stage `mcp-server` builds FROM `mcp-server-deps`, which builds FROM `service-deps`.
- `.github/actions/` holds no image-smoke action (#1858 is open). `Verify` runs the three smoke steps of `ci.yml` with the same text, one for each image; #1858 replaces them with its action.
- `uv run devops ci --check --only actionlint,zizmor` passes (actionlint 1.17.1, zizmor 1.32.0). In a copy with an unknown input and no `sha` input in the call, actionlint fails with two `[workflow-call]` errors, so it checks the call against the inputs of the called workflow.
- An anonymous pull of `latest` of the three packages gets HTTP 200: they are public.

## Existing Tool Considered

`docker/build-push-action` builds once and pushes by digest. `docker buildx imagetools create` and `inspect` put the tags on the digest and check them. `actions/attest` writes the provenance, and `docker/metadata-action` gives the labels. A GitHub reusable workflow called from a matrix runs the three jobs for each image on their own. Renovate's built-in github-actions manager moves the new `actions/attest` pin. The change builds no code of its own.
