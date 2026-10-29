# Design

## Context

The `actionlint-py` PyPI wrapper is stalled at version 1.7.12, which rejects `ubuntu-26.04` as an unknown label, blocking the lint gate. The maintained upstream `actionlint` has reached v1.17.0. The devcontainer already provides other tools via `COPY --from` stages, and the CI workflow already uses `docker://` actions for other tools.

## Goals / Non-Goals

**Goals:**

- Replace `actionlint-py` (stalled PyPI wrapper) with `kjanat/actionlint` v1.17.0 (maintained upstream binary).
- Deliver the binary as a digest-pinned Docker image so the gate never depends on a mutable PyPI release.
- Keep the `actionlint` row of `devops ci` unchanged in name and behavior.
- Pass all existing tests without lowering any threshold.

**Non-Goals:**

- Changing the `actionlint` linter's behavior or configuration.
- Adding new checks to the CI gate.
- Changing the devcontainer's base image.

## Decisions

- **Use a digest-pinned Docker image.** The devcontainer `Dockerfile` adds a `FROM docker.io/kjanat/actionlint:1.17.0@sha256:d484ccca…` stage and `COPY --from` of the binary into the final image. This pins the exact binary by content hash, so a future registry update cannot change what the gate runs. Rejected: using a tag-pinned image. A tag can be moved to a different binary; a digest cannot.
- **Invoke `actionlint` bare on `PATH`.** The devcontainer provides the binary at `/usr/local/bin/actionlint`. The gate's `CheckSpec` command changes from `["uv", "run", "actionlint"]` to `["actionlint"]`. The `shutil.which` pre-check in the subcommand gives a clear message when the binary is absent (e.g. on a host without the devcontainer). Rejected: keeping `uv run actionlint`. This would require `actionlint-py` to remain in the dependency group, which this change removes.
- **Add a `docker://` step in CI.** The `Static Analysis` job of `ci.yml` adds a `docker://docker.io/kjanat/actionlint:1.17.0@sha256:d484ccca…` step that runs the linter in CI. The gate now skips `actionlint` (it runs as a separate `uses:` step). This mirrors the existing pattern for other tools delivered via `docker://`. Rejected: running `actionlint` inside the `devops ci` gate in CI. The binary would not be on `PATH` in the CI runner.
- **Add an offline digest-parity test.** `test_actionlint_digest_pinned_in_dockerfile_and_ci` asserts that the Dockerfile `FROM` and the CI workflow `uses:` reference the same digest-pinned image. This prevents the two from drifting apart.

## Risks / Trade-offs

- [The Docker Hub image is removed or the digest becomes unavailable] → The digest is content-addressed; as long as Docker Hub retains the blob, the build is reproducible. The repository pins the digest in both the Dockerfile and the CI workflow, and the digest-parity test holds them together.
- [A host without the devcontainer runs `devops ci actionlint`] → The `shutil.which` pre-check exits with a clear message naming the missing binary and the install source.
