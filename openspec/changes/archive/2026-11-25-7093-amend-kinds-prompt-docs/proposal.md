# Proposal: #7093

## Why

In `#7093`, `src/devops_cli/roadmap/implement/implement_amend.py` and `openspec/specs/roadmap-plan-amendment/spec.md` already accept `add_path` (`#5937`) and `group` (`#3576`) `plan-request` amendments, yet the coder prompt (`src/devops_cli/ai/tasks/roadmap_implement_step.md`), `docs/ROADMAP_WORKFLOW.md`, and `docs/roadmap/implement.md` still list only `path`, `command`, `task`, `premise`, and `scope`. Because implement step agents are unaware of `add_path` and `group`, they get blocked in `status/blocked` (`outside_plan` or `scope`) instead of sending a bounded `add_path` or `group` amendment request.

## What Changes

- Document `add_path` (with `header` set to `"Changes"` or `"Reads"`, `new` tracked outside `openspec/`, and no `old`) and `group` (`new` holding one smaller group with the same number and no unlisted paths) in `src/devops_cli/ai/tasks/roadmap_implement_step.md`.
- Document `add_path` and `group` alongside `path`, `command`, and `task` in `docs/ROADMAP_WORKFLOW.md` and `docs/roadmap/implement.md`.
- Add prompt and doc tests in `tests/roadmap/implement/test_roadmap_implement_prompt.py` and `tests/invariants/test_roadmap_workflow_doc.py`.
- No CLI runtime code changes; this change updates prompt text, documentation, and tests (`skip_specs: true`).

## Capabilities

None (`docs`, prompt data, and `tests` only).

## Impact

- Autonomous implement step agents see every deterministic amendment kind (`path`, `add_path`, `command`, `task`, `group`) before triggering avoidable `outside_plan` or `scope` stops.
- Fits in one pull request.

## Feasibility

Confirmed against `origin/main:src/devops_cli/roadmap/implement/implement_amend.py:26` (`Kind = Literal["path", "add_path", "command", "task", "premise", "scope", "group"]`), `openspec/specs/roadmap-plan-amendment/spec.md:93-162`, `src/devops_cli/ai/tasks/roadmap_implement_step.md:12`, `docs/ROADMAP_WORKFLOW.md:238,250-254`, and `docs/roadmap/implement.md:89`.

## Existing Tool Considered

Reuses the existing amendment judge (`implement_amend.py`), task prompt loader, and pytest prompt/doc invariant suites; no new runtime code or external tool is needed.
