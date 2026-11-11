# Proposal

## Why

52 `Trivy-config` code scanning alerts stay open on `main`, and no fix, dismissal or ignore names them. Other scanners get a fix in days. Nothing turns a new `Trivy-config` alert into work, and `SECURITY.md` names no judge and no time. Closes #4401.

## What Changes

- Add `src/devops_cli/security/alert_filer.py` and the command `devops scan alerts`. It reads the open `Trivy-config` alerts, groups them by rule and path, and files one issue for each group that no open issue names, at most 5 in one run, the worst severity first.
- Add the workflow `.github/workflows/trivy-config-alerts.yml`. It runs `devops scan alerts` each day, with `security-events: read` and `issues: write`.
- Add the section "Judging a Trivy-config Alert" to `SECURITY.md`: the owner judges a CRITICAL alert within 24 hours, an agent judges the others within 14 days, and an IaC ignore goes to `.trivyignore.yaml` with `statement` and `expired_at`.
- Make the `trivy config` scan name `.trivyignore.yaml` of its directory with `--ignorefile`, so the entry of that file has an effect.
- The 52 alerts that are open now stay for #4409. This change adds no ignore entry and dismisses no alert.
- The change fits one pull request.

## Capabilities

### New Capabilities

- `trivy-config-alerts`: The filer, its workflow, the policy rule and the ignore file of the IaC scan

### Modified Capabilities

None.

## Impact

- Code: `src/devops_cli/security/alert_filer.py`, `src/devops_cli/security/trivy.py`, `src/devops_cli/security/scan_plans.py`, `src/devops_cli/commands/scan.py`, constants and language entries
- Workflow: `.github/workflows/trivy-config-alerts.yml`
- Documents: `SECURITY.md`, the generated command pages
- Tests: `tests/security/test_alert_filer.py`, `tests/security/test_trivy_config_ignore.py`, `tests/commands/test_scan_alerts.py`, `tests/invariants/test_workflow_contracts.py`, `tests/invariants/test_agents_md.py`

## Feasibility

- The alerts exist now. `devops gh api 'repos/dan-petty/devops-cli/code-scanning/alerts?state=open&per_page=100' --paginate` on 2026-11-11 gave 52 open alerts of the tool `Trivy-config` (1 critical, 10 high, 19 medium, 22 low). The latest analysis of the category `/devops-scan` for `Trivy-config` reports 52 results, so the scan still finds them.
- The read path works on the real payload: `read_open_alerts` parsed the 52 alerts, `group_alerts` made 52 groups, and `plan_filing` with the 400 open issues of that day chose `AZU-0041` first and left 47 for later runs. No issue was filed in this check.
- The issue text proposes `.trivyignore.yaml`. The repository holds `.trivyignore` only, which `trivy` reads by default. A test with Trivy 0.75.0 shows that a `.trivyignore.yaml` entry with `paths`, `statement` and `expired_at` hides `DS-0002` only when `--ignorefile .trivyignore.yaml` is named, and that Trivy fails with `ignore file not found` when the file is missing. So the scan names the file only when it exists (task 1.3). The plain `.trivyignore` with `exp:` cannot name a path, so the IaC rule uses the YAML file.
- A new issue needs no intake label: `docs/ROADMAP_WORKFLOW.md` lists "a new issue on GitHub" as a way to capture, and the filer sets only `type/bug` and `scope/security`.
- The issue text asks for a `workflow_run` trigger after CI. `devops scan workflows` on 2026-11-11 reports that trigger as a HIGH zizmor finding (`dangerous-triggers`), and the project publishes such findings to code scanning, so the trigger would add one more alert with no judge. The workflow therefore runs on a daily schedule only. The CI run on `main` uploads the alerts, and the next daily run files their issues. A step of the CI workflow is no choice either: a pull request run must not write issues.

## Existing Tool Considered

Trivy covers the detection, and the scoped ignore with `statement` and `expired_at`, and this change uses both. The alerts API of GitHub covers the record. No open tool files an issue for a code scanning alert group: the alternatives check of 2026-11-11 found none. The code is about 190 lines on the GitHub session that exists. The cost is about 350k tokens to build, about 120k tokens a year to keep and fix, and about 6 hours of elapsed time.
