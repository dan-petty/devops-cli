# Proposal: #6423

## Why
`src/devops_cli/config/constants.py` holds a copy of the weaver version, `CONST_SEMCONV_WEAVER_VERSION = "0.26.1"`. Only the install hint of `devops telemetry semconv refresh` uses it. No Renovate manager updates this copy, so each weaver release makes the hint wrong. The owner rule of 2026-11-19 says that devops-cli is not a package manager: no tool version stays in `src/` that a dependency update must change. Closes #6423.

## What Changes
- Delete `CONST_SEMCONV_WEAVER_VERSION`.
- The hint of the `DependencyError` that `devops telemetry semconv refresh` raises when weaver is not on PATH names the devtools image `ghcr.io/dan-petty/devtools` and the weaver releases page, with no version number. The hint text moves to `MESSAGES.telemetry.weaver_missing_hint`, and the image name becomes the constant `CONST_DEVTOOLS_IMAGE`.
- `weaver_package_argv` and its test stay: they test the argv that the code builds, not a version value.
- The hint is a message that a user sees, so the change has a spec delta.

The change fits one pull request.

## Capabilities
- `telemetry-semconv` (new): the GenAI semantic conventions snapshot and its refresh command.

## Impact
- A user with no weaver on PATH gets a hint that stays correct after each weaver release.
- The weaver version lives only in `mise.toml` and `mise.lock` of dan-petty/devtools, which Renovate's `mise` manager bumps.

## Feasibility
- `git grep -n SEMCONV_WEAVER_VERSION origin/main -- src` finds the constant at `src/devops_cli/config/constants.py:2134` and its only use at `src/devops_cli/telemetry/semconv.py:207`.
- `mise.toml` of dan-petty/devtools holds `"github:open-telemetry/weaver" = "0.28.0"`, and its `mise.lock` holds the URL and checksum of weaver for `linux-x64` and `linux-arm64`. Its README names the image `ghcr.io/dan-petty/devtools` and lists weaver among the tools that Renovate's `mise` manager updates.
- An anonymous request for the manifest of `ghcr.io/dan-petty/devtools:latest` returns HTTP 200, so the image is public.
- dan-petty/devtools#1, the dependency of this item, is closed.

## Existing Tool Considered
Renovate's `mise` manager is the open, maintained tool that covers the need: it bumps weaver in `mise.toml` and `mise.lock` of dan-petty/devtools. This change builds nothing. It deletes the internal constant `CONST_SEMCONV_WEAVER_VERSION` and its use in the install hint.
