# Proposal

## Why

#2504 found that `NetworkReputationRecord.outcome` defaulted to `ok`. A client that forgot the outcome gave a record that read as verified. The fix made the field required (#2647). #2636 removed the same clean default from `NetworkReference.security_status` and `PackageLookupResult.status` (PR #3807). No document tells the next author of a lookup result model to give it no clean default (#2660).

## What Changes

- `ARCHITECTURE.md` section 7.2 (`End-to-End Pydantic Resource Model Interoperability`) gets one bullet, `No Clean Default on a Result`, after the `Strict Typing` bullet.
- The bullet states the rule: the result model of a lookup or a check names how the lookup ended, the field has no default that reads as clean, and a missing value is a validation error.
- The bullet names the merged checks that fail if a clean default returns: `tests/security/test_vulnerability_lookup.py::test_reputation_record_needs_a_known_outcome` and `tests/models/test_resource_schemas.py::test_vulnerability_result_fields_are_required`. The rule is not prose alone.
- The change alters no behavior that a consumer observes (documentation only), so it sets `skip_specs: true` and adds no spec delta.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- Documents: `ARCHITECTURE.md`

## Feasibility

- The premise of the issue was that the hardening audit reports PR #2647 as `Missing`. That premise is out of date: #3684 made the audit count additions under `tests/` and `openspec/specs/`. `uv run devops pr hardening-report --pr 2647 -f json` on `origin/main` prints `"is_hardened": true` with the hardened surfaces `tests/` and `openspec/specs/`. The issue still stands for its other need: no document states the rule for the next author. `rg -n "clean default|No Clean" ARCHITECTURE.md CONTRIBUTING.md SECURITY.md docs/TESTING.md` finds no such line on `origin/main`.
- `src/devops_cli/models/vulnerability.py` shows `outcome: LookupOutcome` with no default, and `NetworkReference.security_status` and `PackageLookupResult.status` as required fields (delivered by PR #3807).
- `uv run devops ci test tests/models/test_resource_schemas.py tests/security/test_vulnerability_lookup.py` runs the two checks that the bullet names.
- `ARCHITECTURE.md` is a declared hardening surface (`CONST_HARDENING_SURFACES` in `src/devops_cli/config/constants.py`).
- The review comment of 2026-11-04 on #2526 asked that the sentence be kept. #2526 is closed, and its plan is not in the repository, so the sentence stays with this issue.

## Existing Tool Considered

None. No open tool writes a project rule into the architecture document of the project. The change is one bullet in an existing Markdown file. Cost: about 3,000 tokens to write, about 500 tokens per quarter to keep, and about 20 minutes of elapsed time. It deletes no internal code.
