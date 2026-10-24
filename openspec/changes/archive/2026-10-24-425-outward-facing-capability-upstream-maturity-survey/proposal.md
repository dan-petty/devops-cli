# Proposal

## Why

Issue #425 identifies that every work generator in devops-cli evaluates internal state and existing plans. The tool cannot detect when an upstream dependency is unmaintained or when an outward capability is missing compared to comparable tools.

## What Changes

This change adds an outward-facing survey command `devops survey` to the CLI:
- It scores upstream maintenance for each pinned runtime dependency from mechanical signals: last commit date, release cadence, archival status, and licence.
- It compares project capabilities against configured comparable tools, recording each capability as present, absent, or unknown.
- It requires citations for all comparable tool claims and records unassessed features as unknown rather than absent.
- It emits capability gaps into roadmap intake through `intake_candidate`.
- It outputs machine-readable reports in JSON or terminal table format.

This change fits in one pull request.

## Capabilities

### New Capabilities
- `survey`: Inspect upstream dependency maintenance and compare capabilities against comparable tools.

### Modified Capabilities
None.

## Impact

- CLI: Adds the top-level command `devops survey`.
- Configuration: Adds `.devops/survey.toml` for comparable tool definitions and capability declarations.
- Roadmap: Integrates capability gap findings with `devops_cli.roadmap.intake.intake_candidate`.
- Documentation: Adds CLI command reference documentation for `devops survey`.

## Feasibility

I confirmed the premise against the Python package ecosystem and GitHub API:
- PyPI provides package metadata, release timestamps, and repository links through `https://pypi.org/pypi/<package>/json`.
- GitHub REST API `GET /repos/{owner}/{repo}` provides repository archival status, license information, and the `pushed_at` timestamp.
- Direct runtime dependencies are pinned in `pyproject.toml` and locked in `uv.lock`.
- `devops_cli.roadmap.intake.intake_candidate` accepts `NewCandidate` instances and folds duplicates.

## Existing Tool Considered

`uv tree --outdated` reports version freshness, but it does not report project archival status or repository commit cadence. OpenSSF Scorecard inspects repository supply chain security, but it does not evaluate comparable CLI capabilities or generate roadmap backlog items. Building this survey directly in devops-cli requires approximately 600 lines of code, 120,000 tokens of agent context, and two hours of implementation time. The internal prototype deletes no existing code.
