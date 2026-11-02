# Proposal

## Why

Issue #3202: the prompt of the stage planner, `src/devops_cli/ai/tasks/roadmap_stage_change.md`, restates rules that other files hold: the keys of the reply, the limits of the summary and of the body, the forms of `verify`, the paths that need no spec delta and the words that close an issue. The planner gets no `AGENTS.md`, `CONTRIBUTING.md` or `docs/TESTING.md`, so this copy is the only way it learns a rule. When the code or a document changes a rule, the prompt can stay old. #3015 added one test of this kind (the example test paths). The other rules had none.

## What Changes

- A new test module, `tests/roadmap/test_roadmap_stage_prompt_rules.py`, reads the prompt and fails when it disagrees with the source of a rule. A rule with a machine form is read from that form: the fields of `StageProposal`, `StageGroup` and the other reply models, `SUMMARY_MAX_CHARS`, `BODY_MAX_CHARS`, `PURPOSE_MIN_CHARS`, `GroupKind`, `PENDING_PERSON`, `staging_title`, `closing_keyword_in`, `form_problems`, `check_proposal` and the command tree of `devops`. A rule with no machine form is held by a phrase that the prompt and the document must both keep.
- The test found one disagreement. The check of the body refuses nine closing keywords, and the prompt names six. The prompt now names `closed`, `fixed` and `resolved` too.
- The summary limit of the prompt is 40 and the limit of the schema is 60. They agree: the job writes the title as `docs(openspec): plan #<number> <summary>`, and the part after the colon has at most 60 characters. The test holds the 40 under 60 minus the longest lead, so the job never cuts the summary.
- The change alters no behavior that a consumer observes. It adds tests and changes the wording of one prompt line to match a check that exists, so it has no spec delta and sets `skip_specs: true`.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- Code: `src/devops_cli/ai/tasks/roadmap_stage_change.md`.
- Tests: `tests/roadmap/test_roadmap_stage_prompt_rules.py`.

## Feasibility

Checked on 2026-11-02 at `origin/main` (19a08788).

- The prompt exists and holds the rules the issue names: `git grep -n -e "at most 40 characters" -e "at most 800 characters" -e "at least 50 characters" -e "is refused" -- src/devops_cli/ai/tasks/roadmap_stage_change.md` lists each line.
- The premise "limits match `CONST_*` values" is partly wrong. The limits of the plan are module constants of `src/devops_cli/roadmap/stage_change.py`: `SUMMARY_MAX_CHARS = 60`, `BODY_MAX_CHARS = 800` and `PURPOSE_MIN_CHARS = 50`. Only the body limit of the delivery pull request is a `CONST_`: `CONST_ROADMAP_IMPLEMENT_BODY_MAX_CHARS = 1000` in `src/devops_cli/config/constants.py`. `CONTRIBUTING.md` section 4 says the summary has "at most 60 characters" and the body "at most 1,000 characters before the trailers". The tests read the module constants for the plan and the `CONST_` for the delivery.
- The prompt says 40 and 800, the schema says 60 and 800. The draft body is `Plans #<number>`, the body and the `Change:` line, and with 800 characters it stays under 1,000: the test builds the longest one with `pull_request_body`.
- The form check exists: `src/devops_cli/roadmap/stage_form.py` accepts `uv run devops` and `! git grep ` and refuses `uv run pytest` (merged #3015 and #3189). `docs/TESTING.md` and `openspec/config.yaml` give the same forms.
- The paths that need no spec delta are `("tests/", ".github/workflows/", "docs/", "openspec/")` in `stage_change.py`, and the prompt lists the same four. The problem text of `check_proposal` names them, so the test reads them from that text and imports no private name.
- Run on the base: of 67 test cases, 64 pass and the cases for `closed`, `fixed` and `resolved` fail with `assert None` on the sentence of the prompt. So the prompt and the code disagreed on one rule.
- Not confirmed: the issue says the planner budget is about 65,000 tokens in the example config. `git grep -n "65000\|65,000" -- config.example.yaml src/devops_cli/config/defaults.py` finds no such value; the nearest, `DEFAULT_ROADMAP_STAGE_STEP_TOKENS`, is 40,000 and is the budget of an implementation step. The size figures below come from `count_tokens`.

## Existing Tool Considered

No open tool compares a prompt with project documents. promptfoo and similar tools assert on the answers of a model, which needs a model call and a network, and the tests of this project reach neither. `devops roadmap eval` already scores the planner on a golden set, but it does not read the documents. So the change builds a small test. Cost to build: about 60,000 tokens and 1.5 hours. Cost to keep: one test file, plus an edit of it when a rule gains a machine form (about 2,000 tokens each). Cost to fix a break: the break names the rule, the prompt line and the other source, so about 3,000 tokens. The change deletes no internal code.
