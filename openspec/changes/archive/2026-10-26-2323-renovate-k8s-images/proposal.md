# Proposal

## Why

Issue #2323: Renovate never proposes an update for an image tag in a manifest under `k8s/`.
The `kubernetes` manager of Renovate has no default `managerFilePatterns`, and `.github/renovate.json` sets none.
A person must notice each new release of a pinned image.

## What Changes

- Add `kubernetes.managerFilePatterns` with `^k8s/.+\.ya?ml$` to `.github/renovate.json`.
- Add a package rule that gives the `kubernetes` manager the labels `type/chore` and `scope/infra`. The global `chore(deps):` prefix applies.
- Add `tests/test_renovate_config.py`. It checks that every manifest that pins an image tag matches a pattern.
- Update the Renovate paragraph of `docs/SDLC.md`.
- The change sets `skip_specs: true`: it changes no command, option, message, manifest or service behavior.
- Each image gets its own pull request. No group is set, because the issue leaves the count to a person.
- `tools.lock` stays a manual bump. A `sha256` change needs a post-upgrade task that Renovate cannot run on the hosted app.
- This change fits in one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- `.github/renovate.json`, `docs/SDLC.md`, `tests/test_renovate_config.py`.

## Feasibility

- The Renovate documents for the `kubernetes` manager (https://docs.renovatebot.com/modules/manager/kubernetes/) state that it has no default `managerFilePatterns`.
- `.github/renovate.json` before the change has no `kubernetes` key: the new test fails on it.
- The manager reads only a file that holds `apiVersion` and `kind`, so Helm values files under `k8s/` yield no update.
- The service image (`ghcr.io/dan-petty/devops-cli/service`) has no tag in the manifests, so Renovate skips it.

## Existing Tool Considered

Renovate, already in use. No code is built and no internal code is deleted.
