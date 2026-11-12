# Proposal: #5016

## Why

Issue #5016: the Deadline bullet of the section Runner Jobs in `k8s/README.md` gives a stall default of 2400 s and a check watch of 1800 s. The code has 4200 s (`DEFAULT_ROADMAP_IMPLEMENT_DEADLINE_STALL_SECONDS`) and 3600 s (`DEFAULT_ROADMAP_IMPLEMENT_MONITOR_TIMEOUT_SECONDS`) in `src/devops_cli/config/defaults.py`. Item 16 of the Service rows also says that a Job with an empty log ends by its stall after 40 minutes, which is the old stall. So the document is wrong now (AGENTS.md rule 8), and no check finds the drift.

## What Changes

- The Deadline bullet gives the stall default of 4200 s and the check watch of 3600 s. The reason stays: the stall is 600 s above the longest wait in which the runner writes no line.
- Item 16 says that a Job with an empty log ends by its stall after 70 minutes.
- A test case in `tests/roadmap/implement/test_roadmap_implement_deadline_settings.py` reads `k8s/README.md` and fails when a stated stall, extension, ceiling, watch, margin or stall time in minutes differs from the defaults (AGENTS.md rule 11).
- The change alters no behavior that a consumer observes: it changes a document and adds a test. So it has no spec delta and sets `skip_specs: true`.

## Capabilities

None. The change adds no requirement and changes no requirement.

## Impact

- `k8s/README.md` (Runner Jobs, Deadline bullet; Service rows, item 16) and one test module. No code, setting or manifest changes.
- The change fits one pull request.

## Feasibility

- `git grep -n "DEADLINE_STALL_SECONDS: int\|MONITOR_TIMEOUT_SECONDS: int" src/devops_cli/config/defaults.py` gives 4200 and 3600 on `origin/main` (87ae9eefa).
- Commit bc0434eeb (#3223, which closes #3206) raised the stall to 4200 s and the watch to 3600 s. It changed only the extension default of the Deadline bullet (3600 to 5400), and kept the stall of 2400 s and the watch of 1800 s.
- The stall logic in `src/devops_cli/roadmap/implement/implement_deadline.py` ends a Job when the log stays the same for `deadline_stall_seconds`. An empty log never changes, so a Job that cannot pull its image ends after the stall, 4200 s (70 minutes).
- On the base, the new test fails for `watch` (1800 against 3600), `stall` (2400 against 4200) and `stall-minutes` (40 against 70). After the README edit, all 16 cases of the module pass.

## Existing Tool Considered

- No open tool in this project checks a number in a README against a code constant. A pytest case with `re` from the standard library does the check, as the test of the admission policy cap in the same module does.
- Cost: about 0.1M tokens and 1 hour to build; the test needs a change only when the README text of a value changes.
