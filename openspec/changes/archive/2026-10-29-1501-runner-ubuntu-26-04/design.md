# Design

## Context

The workflows pinned `ubuntu-24.04` because the stale actionlint 1.7.12 rejected `ubuntu-26.04`. #1119 (#2687) replaced that linter with the maintained `kjanat/actionlint` v1.17.0, which accepts the label. GitHub moves `ubuntu-latest` to 26.04 from 2026-10-19, so the runners should name the explicit `ubuntu-26.04` label rather than the moving `-latest` alias.

## Goals / Non-Goals

**Goals:**

- Re-pin every CI job from `ubuntu-24.04` to `ubuntu-26.04`.
- Keep the runner label explicit (not `-latest`), so a GitHub image move cannot silently change what CI runs.
- Keep the workflow lint green under the maintained linter.

**Non-Goals:**

- Changing any step, action, secret or job behavior.
- Changing the devcontainer base image.
- Adding new checks to the gate.

## Decisions

- **Re-pin the label in the eight workflows.** Each `runs-on: ubuntu-24.04` becomes `runs-on: ubuntu-26.04`. Rejected: using `ubuntu-latest`. It is a moving alias; GitHub already moves it to 26.04 from 2026-10-19, so a job that names it would silently adopt a future image without review. The repository forbids `-latest` runners (`tests/test_ci.py::test_github_workflows_name_their_runner_and_use_managed_python`).
- **Remove the `# moves to ubuntu-26.04 in #1501` markers.** They pointed to this change; once it lands, they state a fact already done. Rejected: keeping them. A comment that says "moves to this label in this PR" is misleading after the merge.

## Risks / Trade-offs

- [`ubuntu-26.04` is not yet a stable GitHub-hosted label] → It is the target of the `ubuntu-latest` move that starts 2026-10-19, so GitHub provisions it on hosted runners. The branch's own CI run on the label is the acceptance check.
- [The service image and devcontainer must build on 26.04] → The acceptance criteria require the service image to build and pass its smoke test and Trivy scan, and the devcontainer to build. CI on the branch exercises both.
