# Design

## Decisions

- Keep the existing `plan-request` example (`path`) in `src/devops_cli/ai/tasks/roadmap_implement_step.md` and concisely list every supported `kind` (`path`, `add_path`, `command`, `task`, `group`, `premise`, `scope`) plus the required keys for `add_path` (`header`: `"Changes"` or `"Reads"`, `new` tracked outside `openspec/`, no `old`) and `group` (`new`: smaller group with the same number and existing paths).
- Synchronize `docs/ROADMAP_WORKFLOW.md` and `docs/roadmap/implement.md` with `openspec/specs/roadmap-plan-amendment/spec.md` instead of documenting only `add_path` in the prompt.
- Add dedicated new test functions in `tests/roadmap/implement/test_roadmap_implement_prompt.py` and `tests/invariants/test_roadmap_workflow_doc.py` without removing the existing five-kind check.

## Rejected alternatives

- **Document only `add_path` and leave `group` undocumented**: rejected because `implement_amend.py:26,281-315` and `openspec/specs/roadmap-plan-amendment/spec.md:93-114` already implement and specify `group` as a deterministic amendment kind, so omitting it leaves the prompt and docs incomplete.
- **Alter `implement_amend.py` rules to auto-accept `scope`**: rejected because `openspec/specs/roadmap-plan-amendment/spec.md:82` and owner boundaries require requirement/criterion scope changes to wait for a person, whereas documenting `add_path` and `group` immediately unlocks the existing bounded mechanisms.
