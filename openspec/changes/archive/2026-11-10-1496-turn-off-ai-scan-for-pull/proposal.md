# Proposal

## Why

Two GitHub settings spent the owner Copilot allowance within one week (#1496).

- AI Scan for pull requests was enabled in the repository settings. It ran on every pull request and on every commit. It consumed AI credits and caused HTTP 402 quota errors for workflows.
- The `main` ruleset had `review_on_push: true` for Copilot reviews. This caused re-reviews on every push to release pull requests.

The documentation in ADR 0004 already recorded `review_on_push: false`, but the settings did not follow. AI Scan for pull requests was never documented.

## What Changes

- Disable AI Scan for pull requests in the repository settings with `gh api --method PATCH repos/dan-petty/devops-cli/code-scanning/ai-scan -f pr_scan=disabled`.
- Update `docs/adr/0004-ci-is-the-authoritative-gate.md` (decision D6) to record the disabled AI Scan setting and the `gh api` commands that read back both settings.
- The change modifies repository settings and documentation. It modifies no CLI commands or capabilities, so it has no spec delta and sets `skip_specs: true`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- GitHub repository settings: AI Scan for pull requests is disabled.
- Documentation: `docs/adr/0004-ci-is-the-authoritative-gate.md`.

## Feasibility

- `gh api repos/dan-petty/devops-cli/code-scanning/ai-scan` returned `{"pr_scan":"enabled"}` before the change and `{"pr_scan":"disabled"}` after the PATCH request.
- `gh api repos/dan-petty/devops-cli/rulesets/21466414` shows the active rules of the `main` ruleset. Automatic Copilot reviews were removed under ADR 0014 and step 6 of #1864.
- `uv run devops docs check` verifies documentation freshness.

## Existing Tool Considered

GitHub REST API endpoints for repository code-scanning settings (`/repos/{owner}/{repo}/code-scanning/ai-scan`) manage the setting directly. No bespoke tooling is required. Cost: 0 tokens to build, 0 tokens to maintain, and under 5 minutes elapsed.
