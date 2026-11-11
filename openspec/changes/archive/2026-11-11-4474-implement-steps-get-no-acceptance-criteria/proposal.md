# Proposal: #4474

## Why

An implement step gives the Coder the problem and the acceptance criteria of the item (`issue_inputs` in `src/devops_cli/roadmap/implement/implement_step.py`). It takes the sections whose heading is `Acceptance criteria` with `section_text`, and a section ends at the next heading of its level or a higher one. The refine job writes each refined criterion as a `### Requirement: <name>` section with its `#### Scenario:` lines, after a `### Acceptance criteria` heading of the same level (`render_proposal_section` in `src/devops_cli/roadmap/refine/refine.py`). Thus the first `### Requirement:` heading ends the criteria section, and the step gets an empty heading. Of the last 30 implemented issues, 25 gave the step no criterion at all. When a person part of the body ends just before the refine block, the step also gets the HTML comments of the block: the start marker and the `checked-at` line. When an issue has neither section, the step gets the whole body with its comments. Closes #4474.

## What Changes

- `issue_inputs` adds each top-level `Requirement:` section of the body, with its scenarios, to the problem and criteria sections that it gives the step.
- `issue_inputs` removes each top-level HTML comment block of the body before it takes the sections, and also before the whole-body fallback.
- `section_text` in `src/devops_cli/roadmap/step_files.py` does not change, because five other modules use it (`adr.py`, `step_rules.py`, `pull_describe.py`, `repair.py` and `implement_run.py`).
- The text that a step gives the model is observable behavior of the step, so the change carries a delta of `roadmap-implement-step`.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-implement-step`: The issue section of a step holds the refined criteria and no HTML comment

## Impact

- Code: `src/devops_cli/roadmap/implement/implement_step.py` (`issue_inputs` and two private helpers).
- Tests: `tests/roadmap/implement/test_roadmap_implement_step.py`, three body fixtures in `tests/fixtures/roadmap/issue_bodies/`.
- Documents: `docs/roadmap/implement.md` (the list of step inputs).
- The issue section of a step grows. Over the last 30 implemented issues, its mean length goes from 966 to 3,374 characters, about 600 tokens more on each request of a step.

## Feasibility

- Premise checked in the code at `origin/main` (c653bde8): `issue_inputs` calls `section_text(item.body, wanted)` with the problem and criteria headings only, and `section_text` ends a section at the next heading of the same level.
- Premise checked on three real issues, read with `uv run devops gh api repos/dan-petty/devops-cli/issues/<n> --jq .body` and given to `issue_inputs` at c653bde8:
  - #3220 (`feat(k8s): deploy the MCP server for the roadmap jobs`): the body holds 5 `### Requirement:` sections. The step text ends with `### Acceptance criteria` and holds 0 of them.
  - #3593 (`fix(ci): the pytest step of devops ci exceeds the 5-minute budget`): the body holds 6. The step text ends with `### Acceptance criteria` and holds 0.
  - #4004 (`feat(roadmap): allow-list builder for planner read-only commands`): the body holds 8. The step text ends with `### Acceptance criteria` and holds 0.
- Measured over the bodies of the issues of the last 30 implement pull requests of the Service: at c653bde8, 5 of 30 step texts hold a criterion (a list item under an `Acceptance criteria` heading), 0 of 30 hold the refined requirements, and 3 of 30 hold an HTML comment. With the change, 30 of 30 hold every refined requirement and 0 of 30 hold a comment.
- The new tests fail at c653bde8: the requirement test on the two refined fixtures, the comment test on the form fixture and on the fixture with no section.

## Existing Tool Considered

markdown-it-py, which the project already uses through `MARKDOWN` of `step_files.py`, parses the body: its `heading_open` tokens give the `Requirement:` titles, and its `html_block` tokens give the comment blocks with their line ranges. No regular expression is added. The change adds about 30 lines. Cost: about 40,000 tokens to build, 2,000 to keep and 2 hours. It deletes no code.
