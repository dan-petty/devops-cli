# Proposal

## Why

Issue #3899: the findings of `devops research advisories` need a path to a person. Today a person must remember to run the command. A run on 2026-11-07 on this repository shows one critical advisory (`GHSA-6q48-6c7w-9gw2` for `certifi` 2026.7.22) and no issue for it. This change is the fourth slice of the research agent. It adds `devops research sweep`, which turns each actionable finding into one intake candidate, once.

## What Changes

- New command `devops research sweep`. It reads the inventory, finds the advisories of the pins, and leaves out each finding whose marker an issue already carries. It hands each other actionable finding to roadmap intake as one candidate, in process, with the same duplicate flag that `survey` and `review intake` use. Without `--confirm`, intake decides each candidate and writes nothing. With `--confirm`, it files and places each one. It prints a digest with one line for each finding and its result.
- A finding is actionable when its severity is critical or high. OSV matched the pinned version to the affected ranges, so each finding affects its pin.
- The candidate body ends with the marker `<!-- research-finding: <source id> -->`, where the source id is `<ecosystem>:<package>@<version>:<advisory id>`. One issue search for the phrase `research-finding` reads the markers of all issues, open and closed. Any match means the finding was filed before.
- The body is built from public advisory fields only: package, pinned version, severity, advisory id and aliases, one OSV URL for each id, affected range, fixed version and summary. It holds no path of the inventory. A body that looks like a secret stops the sweep before any request.
- The sweep never drops a candidate and never closes an issue. A candidate that intake skips stays in the digest with the reason, and a possible duplicate that intake flags stays in the entry.
- New gauge `devops_cli_research_open_findings` with the label `severity`. The sweep sets one value for each severity of the scale, with zero for a severity without a finding. It sets none when a lookup got no answer, because a count that is not complete could hide a finding. The gauge has a row in `docs/TELEMETRY.md`.
- New Alertmanager rule `ResearchCriticalFindings` (severity critical) in the new group `research`. Alertmanager routes critical alerts to the existing Mattermost receiver, so no new alert path exists. The rule has promtool unit tests.
- `--dry-run` makes no request. It returns a report of the same type as a real run, with no entry, and the list of requests that a real run makes: the OSV requests, the issue search, and the requests of intake for one candidate.
- Observable behavior changes (a command, a metric, an alert rule), so the change carries a spec delta: the new capability `research-sweep`.
- The change fits one pull request.

## Capabilities

### New Capabilities

- `research-sweep`: How `devops research sweep` files intake candidates for the actionable findings of the pins, once each.

### Modified Capabilities

None.

## Impact

- Code: `src/devops_cli/research/sweep.py`, `src/devops_cli/research/models.py`, `src/devops_cli/commands/research.py`, `src/devops_cli/telemetry/instruments.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/lang/en/`.
- Manifests: `k8s/monitoring/prometheus-values.yaml` (rule group `research`).
- Tests: `tests/research/test_sweep.py`, `tests/prometheus/test_k8s_monitoring_alerting.py`, `tests/fixtures/prometheus_rules/research_tests.yaml`.
- Documents: `docs/TELEMETRY.md`, `k8s/README.md`, and the generated `README.md`, `docs/CLI_REFERENCE.md` and `docs/commands/research.md`.
- No new dependency, no secret and no new host. The sweep reads GitHub through the GitHub session and OSV through `OSVClient`.

## Not in this change

Issue #3899 names two more conditions for an actionable finding: a finding that is exploited, and a pin past its end of life. Their data does not exist on `main`. The exploited flag comes from the CISA KEV list, which pull request #4032 for issue #3987 adds. The end-of-life date comes from the collectors of issue #3907. A flag without a source would be dead code, so each condition is added by the issue that adds its data, as one more condition of `is_actionable` and, for the alert rule, of `ResearchCriticalFindings`. Issues #3987 and #3907 hold these criteria.

## Feasibility

- Checked on 2026-11-07 on `origin/main` (d6c2297b). `devops research advisories --json` on this repository returns 7 findings: 1 critical (`certifi` 2026.7.22, `GHSA-6q48-6c7w-9gw2`), 5 medium and 1 with severity `UNKNOWN`. So the sweep files one candidate on the first run.
- The marker search is the one that `devops review intake` uses (`GitHubClient.search_issue_bodies`, issue #2419): GitHub issue search finds text inside an HTML comment of a body. A second sweep reads the marker and files nothing.
- Intake takes a `NewCandidate` in process (`intake_candidate`), as `survey --emit-candidates` and `review intake` do. `devops research sweep --dry-run` on this repository lists the 21 requests of a real run and sends none.
- The exploited and end-of-life conditions cannot be built on `main` (see "Not in this change").

## Existing Tool Considered

`devops roadmap intake` (`intake_candidate`) and `NewCandidate` cover the filing and the duplicate flag. The marker search of the review hand-off (`GitHubClient.search_issue_bodies`) covers the "filed before" check. The existing Alertmanager route to Mattermost covers the alert, and `emit()` covers the gauge. No open, maintained external tool combines the OSV findings of this repository with its intake path. Dependabot alerts are off for this repository, and a repository setting is a decision of a person. The new code is the candidate builder, the marker handling, the digest and the command (about 250 lines); it deletes no internal code.
