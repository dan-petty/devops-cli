# Proposal

## Why

Issue #3262, second follow-up. A review of the first follow-up found a blocker, a major fault and five smaller ones.

1. A `criterion` still adds a group. The criteria section wrote `- ## 2. X: group 1`, and a heading in a list item is a heading for `parse_task_groups`, so the step read a group 2 with its own tasks and no gate. The text of a criterion comes from the issue, and `criterion_problems` makes the model copy it, so a person's criterion `## 2. Cleanup` reaches the file with no bad model.
2. The text of a requirement is not folded. A line break and `## REMOVED Requirements` in it passes `openspec validate --strict`, and `openspec archive` then deletes a requirement of the base spec.
3. The tests do not pin the fold: six changes to the fold left every test green.
4. The fold turned `'a  b'` into `'a b'` inside a command.
5. `group_text` trusts the schema.
6. The backtick problem hid the form problem, and the job asks the model once.

## What Changes

- `step_files._headings` takes a heading at the top level only.
- The criteria section writes `Group <n>: <criterion>` and `Pending person: <criterion>, <reason>`, so a criterion is never at the start of a line.
- Every text of the reply that a file of the change holds is folded to one line: `why`, `what_changes`, `feasibility`, `existing_tool`, the decisions, the rejected alternatives, and the purpose, names, texts and scenario lines of the spec deltas. The texts that stand at the start of a line (`why`, `existing_tool`, `purpose`, the requirement `text`) are refused when they start with a mark of markdown (a heading, a quote, a list marker, a box, a rule, a fence or a comment). The structure of the reply (`added`, `modified`) is the only way to write a section: the planner cannot write `REMOVED`, `RENAMED` or `Purpose` as text.
- `verify` is joined by line breaks with one space and keeps its other spaces (`str.splitlines`), so a quoted word with two spaces keeps its meaning. The other texts fold every run of white space.
- The reply models validate an assignment (`validate_assignment`), so a text set after validation is folded too. `group_text` documents that it renders a validated group; `model_construct` is the one way around the schema and no caller renders such a group.
- `form_problems` gives the backtick problem and the form problem of one command together, and the backtick problem writes the command in a double code span.
- The tests go through every character of `str.isspace()` and the pair `\r\n`. Each of the six changes of the fold that the review made fails a test (see Feasibility).
- Spec: `roadmap-implement-step` gets one ADDED requirement. `roadmap-stage` gets two ADDED and three MODIFIED requirements.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-implement-step`: A group is a heading at the top level of the file
- `roadmap-stage`: A text of the proposal, the design and the spec delta stays on one line, A verify command keeps its spaces, A text of a group stays on one line (MODIFIED), Criteria section in tasks.md (MODIFIED), A verify command holds no backtick (MODIFIED)

## Impact

- Code: `src/devops_cli/roadmap/step_files.py`, `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/roadmap/stage_form.py`, `src/devops_cli/lang/en/messages.py`.
- Tests (new): `tests/roadmap/test_roadmap_stage_text_lines.py`. Tests (changed): `tests/roadmap/test_roadmap_stage_task_verification.py`, `tests/roadmap/test_roadmap_stage_plan.py` (the new text of a criteria line).
- Audit of the model texts that land in a file, a title, a body or a comment (each one is on one line, or cannot hold markup):

  | Text | Lands in | State |
  | :--- | :--- | :--- |
  | `title`, `test`, `implementation`, `documentation`, `process` | `tasks.md` | folded (first follow-up) |
  | `verify` | `tasks.md` | joined by line breaks, backtick refused |
  | `reads`, `changes`, `creates` | `tasks.md` | `_repository_path` refuses a control character and a backtick |
  | `criterion` | `tasks.md` | folded, after a fixed word (this change) |
  | `reason` of a criterion | `tasks.md` | folded, after a fixed word |
  | `why`, `existing_tool` | `proposal.md` | folded, mark at the start refused (this change) |
  | `what_changes`, `feasibility` | `proposal.md` | folded (this change), after `- ` |
  | decisions, rejected alternatives | `design.md` | folded (this change), after `- ` |
  | `purpose`, requirement `text` | `spec.md` | folded, mark at the start refused (this change) |
  | requirement name, scenario name, WHEN, THEN | `spec.md` | folded (this change), after a fixed prefix |
  | `capability` | `spec.md` path and `proposal.md` | `is_valid_slug` |
  | change name and branch | folder name, branch | derived from the issue title: ASCII letters and digits only (`_slug_of`) |
  | `.openspec.yaml` | file | no model text: the date and `skip_specs` (a bool) |
  | `summary` | pull request title | `safe_text`, one line, counted |
  | `pull_request_body` | pull request body | `safe_text`, one line, closing keywords refused |
  | `premise_failed` | issue comment | `safe_text` and `mask_secrets` |
  | group titles and findings | issue comment | `safe_text` |
  | a model error | issue comment | the count of violations only, never the reply |

## Dependencies

None open.

## Feasibility

Checked on `origin/main` 0b6d3db6, on 2026-11-02, in a plain clone, with `openspec` 1.14.3.

1. The blocker reproduces end to end. With the issue body `## Acceptance criteria` and an item `- [ ] ## 2. Cleanup`, `acceptance_criteria` gives `## 2. Cleanup`, `criterion_problems` asks the model to copy it, and the rendered `tasks.md` holds `- ## 2. Cleanup: group 1`. `parse_task_groups` gave a group 2. The test `test_a_criterion_of_the_issue_body_that_looks_like_a_heading_adds_no_group` fails on the base, and 13 of the criterion and parser tests fail.
2. The major fault reproduces with the real tool. A scratch project with a spec of two requirements and a rendered change whose requirement `text` holds a line break, `## REMOVED Requirements` and a requirement `Protect the secret`: on the base `openspec validate 1-x --strict` printed `Change '1-x' is valid`, `openspec archive 1-x --yes` printed `Totals: + 1, ~ 0, - 1, → 0`, and `spec.md` lost `Protect the secret`. After the change the schema folds the text, the archive prints `+ 1, - 0`, and the requirement stays.
3. The fold is pinned. I changed the fold in a scratch copy and ran the two test files: an LF-only fold failed 43 tests, `splitlines` failed 23, a regex for `\r` and `\n` failed 29, an ASCII-space fold failed 23, a backtick test `count > 1` failed 1, an unfolded `criterion` failed 5, a `verify` joined at LF only failed 10, a `verify` folded at every space failed 11, and a parser that takes a heading at any level failed 5. On the base of the first follow-up each of the first six passed.
4. The structure of the reply gives only `ADDED` and `MODIFIED` sections (`_spec_file`), and no field writes a `REMOVED` or `RENAMED` heading. `config.yaml` of the change rules has no kind that allows a planner to remove a requirement. So no check of the rendered headings is added: the fold and the start rule make a second heading impossible, and a test reads the headings of the rendered files with the parser of markdown.

Not verified: a live stage run, and a step on a plan folded this way.

## Existing Tool Considered

None covers it: this is the schema of the project's own reply. `pydantic` validators do the folding, and `markdown-it-py` (already the parser of `tasks.md`) reads the headings in the tests. Cost to build: about 40,000 tokens and about 1 hour. Cost to keep: about 2,000 tokens each quarter; the tests fail if a text can add a heading again. The change deletes nothing.
