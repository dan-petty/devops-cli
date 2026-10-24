# Design

## Context

devops-cli contains several internal inspection mechanisms such as `devops ci`, static code analysis, and test suites. However, the tool lacks outward-facing capabilities to verify dependency vitality and outward feature parity. Pinned dependencies can become abandoned even if they match current version pins.

## Goals / Non-Goals

**Goals:**
- Provide automated inspection of all pinned runtime dependencies for last commit date, release cadence, archival status, and licence.
- Provide capability comparison against configured comparable tools with citations and epistemic honesty (unknown status for unassessed features).
- Provide integration with `devops_cli.roadmap.intake.intake_candidate` to file capability gaps as roadmap candidates.
- Provide output in machine-readable JSON and formatted terminal tables.

**Non-Goals:**
- Automatically bumping versions or modifying `pyproject.toml`.
- Scraping arbitrary web pages without structured configuration or APIs.

## Decisions

- **Dependency signals collection**: Inspect PyPI JSON API and GitHub REST API via `devops_cli.http.client.new_http_client` and `devops_cli.github.session.get_github_session`.
  - *Rejected alternative*: Calling `uv tree --outdated`.
  - *Evidence for rejection*: `uv tree --outdated` does not report repository commit timestamps, release cadence, archival status, or licence metadata.
- **Comparable tool configuration**: Use `.devops/survey.toml` to declare comparable tools, assessed capabilities, and citations.
  - *Rejected alternative*: Hardcoding comparable tool metrics in Python source files.
  - *Evidence for rejection*: Hardcoded configurations prevent users and operators from customizing benchmark targets or updating citations without code changes.
- **Intake integration**: Use `devops_cli.roadmap.intake.intake_candidate` to hand identified gaps to the roadmap system.
  - *Rejected alternative*: Calling GitHub Issues API directly via `gh issue create`.
  - *Evidence for rejection*: Direct GitHub API calls bypass the roadmap intake quota governor, duplicate detection, and project board placement.

## Risks / Trade-offs

- [External API rate limits] → Use existing token-bucket pacing from GitHub session and cache dependency metadata in the user data root.
- [Offline environments] → Provide offline mock resolvers for hermetic tests and graceful degradation on network errors.
