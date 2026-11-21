# Tasks

## 1. One build, then verify, attest and tag that digest

Kind: other. Reads: `.github/workflows/release.yml`, `.github/workflows/ci.yml`, `.github/actions/image-scan/action.yml`, `Dockerfile`. Changes: `.github/workflows/release-image.yml`, `.github/workflows/release.yml`, `.github/workflows/ci.yml`, `tests/commands/test_ci.py`, `tests/invariants/test_workflow_contracts.py`, `tests/invariants/test_runner_image.py`, `tests/gate/tree_checks/config_reads.toml`.

- [x] 1.1 Add the called workflow `.github/workflows/release-image.yml` with the jobs `Build` (one build that pushes by digest, with an SBOM, provenance `mode=max`, the revision label of the release commit and the cache filters of the image), `Verify` (pull, the smoke test of `ci.yml`, the image scan action) and `Attest & Tag` (`actions/attest`, `imagetools create`, a check of each tag)
  - Verification: `$ uv run devops ci --check --only actionlint,zizmor`
- [x] 1.2 Replace the jobs `service-image`, `runner-image` and `mcp-server-image` of `release.yml` with the job `image`, which calls the workflow with a matrix over the three images and `fail-fast: false`, and make the runner smoke comment of `ci.yml` name the image, not the loaded image
  - Verification: `$ uv run devops ci --check --only actionlint,zizmor`
- [x] 1.3 Delete the value test of the old service job, and make the smoke parity test, the attestation test and the release-please test read the new jobs. Remove the release step names from `RUNNER_STEPS`, and lower the count of `tests/commands/test_ci.py` in `config_reads.toml`
  - Verification: `$ uv run devops ci test tests/commands/test_ci.py tests/invariants/test_workflow_contracts.py tests/invariants/test_runner_image.py`

## 2. Documents

Kind: documents. Reads: `RELEASE_CYCLE.md`. Changes: `RELEASE_CYCLE.md`, `docs/SDLC.md`, `docs/CLUSTER.md`, `docs/guidelines/production-readiness.md`, `k8s/README.md`.

- [x] 2.1 Name the jobs of each image in RELEASE_CYCLE.md, and tell a person to re-run the `Build` job of an image to take a new package from outside the repository
  - Verification: `$ uv run devops ci --check --only docs`
- [x] 2.2 Describe the order build, push by digest, smoke test, scan, attest and tag in `docs/SDLC.md`, `docs/CLUSTER.md`, `docs/guidelines/production-readiness.md` and `k8s/README.md`
  - Verification: `$ uv run devops ci --check --only docs`

## Workflow follow-up

- Pending a person: in the first release after the merge, run `uv run devops gh run view <run_id> --log` and see that the `exporting manifest list` digest of each `Build` job is the digest that its `Verify` job pulled, and that `docker buildx imagetools inspect ghcr.io/dan-petty/devops-cli/<image>:<release tag>` gives the same digest.
- Pending a person: compare the job times of each image in that release with the means of 284, 341 and 338 s of the old jobs.
- #1858 replaces the three smoke steps of `Verify` with its image-smoke action.
