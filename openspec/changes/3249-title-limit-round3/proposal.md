# Proposal

## Why

Issue #3249: the review of the follow-up found gaps in the limit of the summary of a plan title.

- The limit counted code points, and the check `Semantic PR title` counts UTF-16 code units. Its pattern `^.{1,60}$` has no `u` flag (`subjectPattern` in `.github/workflows/pr-title.yml`, run as `new RegExp(pattern)` in JavaScript), so a character outside the Basic Multilingual Plane, such as an emoji, counts as two. A summary of 47 emoji passed the schema and `title_problems` (60 code points) but has 107 units, so the Service would open a plan pull request that the check refuses. `title_problems` had the same difference for every pull request.
- The lower bound counted the raw text, so a summary of spaces or new lines passed and the title ended with the issue number and nothing else.
- Six changes of one line each in the new text left every test green: the prompt sentence, the two parts of the title error, the hint about the code span and the lower bound of the schema.

## What Changes

- A function `summary_length` in `pull_form.py` counts a text as the check does (UTF-16 code units). `title_problems`, the limit of the plan summary and `staging_title` all use it, so one measure serves the schema, the form check and the title. The prompt says that an emoji counts as two characters.
- The schema refuses a summary with no text once the title shows it, with a message of its own.
- Tests pin the prompt sentence, both numbers of the title error, the hint about the code span and the bounds of the JSON schema.
- CONTRIBUTING.md says that an emoji counts as two in the summary.
- The change alters what a consumer sees (the form check and the schema), so it carries spec deltas. It fits one pull request.

Findings that this change does not fix:

- The pull request body of the follow-up said `Refs #3249`, so `body_problems` finds no `Closes` line. That is the known gap that #3215 closes, when the jobs build text with `pull_form`.
- The stop for an item of 7 digits comes after the model call. It needs one million issues, so a check before the call is not worth its code.
- The plan of issue #3200 (PR #3260) says to build `staging_title` from `safe_text(summary)` as it is, and its scenarios assume a bound of 40. See the note to the maintainer in the pull request.
- `delivery_title` cuts the title of an issue at a word with code points. It belongs to #3215.

## Capabilities

### Modified Capabilities

- `pull-request-form`: the summary limit counts UTF-16 code units.
- `roadmap-stage`: the schema counts the same units, and refuses a blank summary.

## Impact

- Code: `src/devops_cli/roadmap/pull_form.py`, `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/ai/tasks/roadmap_stage_change.md`.
- Documents: `CONTRIBUTING.md`, `openspec/specs/pull-request-form/spec.md` and `openspec/specs/roadmap-stage/spec.md` (by archive).
- Tests: `tests/roadmap/test_roadmap_stage_title.py`, `tests/roadmap/test_roadmap_stage_prompt_rules.py`, `tests/roadmap/test_roadmap_pull_form.py`.

## Feasibility

- The pattern of the check is in `.github/workflows/pr-title.yml`: `subjectPattern: ^.{1,60}$`. The action `amannn/action-semantic-pull-request` builds the pattern with `new RegExp(subjectPattern)` and no flags, so `.` is one UTF-16 code unit and an astral character is two. The review ran the pattern in Node: 47 emoji give `false`.
- On `origin/main`, `title_problems("feat(pr): " + 31 emoji)` finds no problem although the summary has 62 units, and `make_stage_proposal(summary=" ")` is accepted. The new tests fail on the base for these reasons.
- `str.split()` folds `\u2028`, `\u2029`, `\x85` and the no-break space, which JavaScript `.` does not match (it stops at line terminators), so `safe_text` leaves no character that the pattern refuses.

## Existing Tool Considered

The standard library gives `str.encode("utf-16-le")`, and the length in units is half of the bytes. No library is needed. Written cost: about 30 000 tokens and 50 minutes to write and test; about 1 000 tokens a year to keep, as the function has one line; about 3 000 tokens to fix a drift, because a test names the unit. The change deletes no code.
