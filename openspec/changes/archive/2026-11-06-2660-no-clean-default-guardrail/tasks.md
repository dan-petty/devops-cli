# Tasks

## 1. Add the guardrail bullet to ARCHITECTURE.md

Reads: `ARCHITECTURE.md`, `src/devops_cli/models/vulnerability.py`, `tests/security/test_vulnerability_lookup.py`, `tests/models/test_resource_schemas.py`. Changes: `ARCHITECTURE.md`.

- [x] 1.1 In `ARCHITECTURE.md`, section 7.2, add the bullet `**No Clean Default on a Result**` after the `Strict Typing` bullet. It states that a lookup or check result model names how the lookup ended, that the field has no default that reads as clean, that a missing value raises a `ValidationError`, which models follow the rule (#2504, #2636), and which two tests fail if a default returns. Verify that `grep -n "No Clean Default on a Result" ARCHITECTURE.md` finds the line and that `uv run devops docs check` passes

## Criteria

- `ARCHITECTURE.md` section 7.2 SHALL hold a bullet that says a lookup or check result model has no default that reads as clean and that a missing value is an error.: group 1
- The bullet SHALL cite #2504 and #2636 and name the two tests that guard the rule.: group 1
- The documentation checks SHALL pass after the edit.: group 1

## Workflow follow-up

- No work is left for a follow-up issue.
