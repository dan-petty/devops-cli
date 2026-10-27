# Proposal

## Why

Issue #1979: the defect classifier still counts `AGENTS.md` as the place where a defect pull request records its lesson. This behavior conflicts with the router rule of #1961: `AGENTS.md` routes to the document that owns each subject. Defect pull requests must record lessons and guardrails in the owning documents or in checks, not in `AGENTS.md`.

## What Changes

- Update `CONST_HARDENING_SURFACES` to remove `AGENTS.md` and add the owning documents: `docs/TESTING.md`, `ARCHITECTURE.md`, `SECURITY.md`, and `CONTRIBUTING.md`.
- Update `match_hardening_surface` and its docstrings in `src/devops_cli/github/defect_classifier.py` to match the owning documents and stop matching `AGENTS.md`.
- Update `.github/workflows/defect-pr-hardening-audit.yml` to declare the updated hardening surfaces.
- Update tests in `tests/test_defect_classifier.py` and `tests/test_pr_hardening_report.py`.
- The change sets `skip_specs: true` in `.openspec.yaml`: no command, option, or message changes.
- This change fits in one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- Constants: `src/devops_cli/config/constants.py`.
- Classifier: `src/devops_cli/github/defect_classifier.py`.
- Workflows: `.github/workflows/defect-pr-hardening-audit.yml`.
- Tests: `tests/test_defect_classifier.py`, `tests/test_pr_hardening_report.py`.

## Feasibility

- Source inspection: `CONST_HARDENING_SURFACES` in `src/devops_cli/config/constants.py` and `match_hardening_surface` in `src/devops_cli/github/defect_classifier.py` still reference `AGENTS.md`.
- Workflow inspection: `.github/workflows/defect-pr-hardening-audit.yml` lists `AGENTS.md` as a declared hardening surface.
- Upstream document inspection: #1961 established `AGENTS.md` as a pure router capped at 6,500 characters, moving domain rules and lessons into owning documents (`docs/TESTING.md`, `ARCHITECTURE.md`, `SECURITY.md`, `CONTRIBUTING.md`).
- Replacement feasibility: `match_hardening_surface` directly checks file path equality for root documents, requiring no additional libraries or complex parsing.

## Existing Tool Considered

None needed. The change modifies an internal constant, its readers, and tests.
