# Proposal

## Why

#2526: five defect PRs merged on 2026-10-28 added no root-cause guardrail to a declared hardening surface. The audit workflow found each one, but its intake step crashed before filing the finding. This change adds the missing guardrails so the defect classes do not return.

## What Changes

- Add a frozen-lockfile guardrail to SECURITY.md item 7 for tool adapter execution (#2446).
- Add a CVE-check guardrail to CONTRIBUTING.md section 1 for pinned sub-chart versions (#2470).
- Add a userinfo-exclusion guardrail to SECURITY.md item 1 for display strings (#2488).
- Add a one-time-resolution guardrail to SECURITY.md item 2 for NetworkPolicy and scrape targets (#2521).
- Add an automountServiceAccountToken guardrail to SECURITY.md item 5 for pods (#2522).
- The change fits one pull request.

## Capabilities

### New Capabilities

- `hardening-surface-guardrails`: guardrail_per_defect, guardrail_names_defect_class, guardrail_in_best_fit_surface

### Modified Capabilities

None.

## Impact

- Documents: `SECURITY.md`, `CONTRIBUTING.md`

## Feasibility

- The audit workflow .github/workflows/defect-pr-hardening-audit.yml confirms the premise: it runs `uv run devops pr hardening-report --pr <number> --fail-on-missing` and the five PRs are reported as unhardened.
- SECURITY.md exists with numbered items 1 through 11. Items 1, 2, 5 and 7 hold the rules that the four guardrails extend.
- CONTRIBUTING.md exists with sections 1 through 6. Section 1 holds the development philosophy and process rules that the Loki CVE guardrail extends.
- The change adds sentences to existing numbered items and sections. It creates no file and changes no code under src/.
- First checks the implementation runs: `grep -n 'frozen' SECURITY.md` to confirm item 7 context; `grep -n 'sub-chart\|CVE' CONTRIBUTING.md` to confirm the dependency section context.

## Existing Tool Considered

No open, maintained tool or library covers the need of writing prose guardrails into project documents. The project writes its own guardrail text into its declared surfaces. The cost is the tokens to write, keep and fix five guardrail entries across two documents, and the elapsed time for a person to review each entry.
