# Proposal

## Why

Issue #3625: defect pull request #3615 (#3393) merged without a guardrail on a declared hardening surface. The post-merge audit `.github/workflows/defect-pr-hardening-audit.yml` reports it as missing. The fix of #3393 makes the implement job refuse a plan that fails the plan check. A later change could drop that rule without any test or document that names the defect class.

## What Changes

- Add one guardrail sentence to section 7.4, "Multi-Stage Workflow Architecture", of `ARCHITECTURE.md`. The sentence names the defect class and cites #3393.
- The change sets `skip_specs: true` in `.openspec.yaml`, because it alters no behavior.
- This change fits in one pull request.

## Feasibility

The premise holds at origin/main. `uv run devops pr hardening-report --pr 3615` reports `Missing` with `no additions on declared hardening surfaces`. The audit reads only the declared surfaces, and `ARCHITECTURE.md` is one of them (`src/devops_cli/github/defect_classifier.py`, `match_hardening_surface`). Pull request #3607 adds the same kind of sentence, and its audit reports `Hardened`.

## Existing Tool Considered

No open tool covers this need. The hardening rule is a repository convention, and the audit already reads the declared surfaces. The change adds text only, so it builds nothing new.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.
