# Proposal

## Why

The alternatives check lets the model decide whether to search for open tools. In 14 days the model gave only the verdict `not-applicable`, and it searched about 4 times (#2946). This includes #886 and #1082, which are features. A fixed rule must name the classes of item that skip the search. Every other item must run at least one search before the check accepts a verdict.

## What Changes

- A closed list of skip classes decides which items skip the search. The classes are the Conventional Commit types `test`, `docs`, `refactor`, `chore`, `ci` and `perf`, and a `fix` whose body holds a stack trace. The list is one private constant of `src/devops_cli/roadmap/alternatives.py`.
- A skip-class item gets the verdict `not-applicable`. Its comment and block name the class. The job makes no model call and no search for it.
- For every other item, a reply that follows no search gets one more turn. The retry uses the pydantic-ai output validator and `ModelRetry`. `investigate` takes a new optional `output_check` argument for it. Refine passes none.
- A second reply that follows no search ends as a failed check. The job skips the item with a named reason, writes nothing for it, and reports it. This is the way the job already treats a refused reply.
- The model can no longer give the verdict `not-applicable`. The job sets it for a skip class only. The existing refusal of `not-applicable` after a search stays. The refusal now holds for every reply, because a non-skip item must search first.
- The prompt tells the model to search at least once and to give `none` when no tool covers the need.
- The tests that answer a non-skip item with no search now search first. One test that pinned the old rule is deleted.
- The docstring of `Verdict` in `src/devops_cli/roadmap/store.py` says that `NOT_APPLICABLE` means the item asks for no tool. It now means the item is in a skip class.
- The help text of the command, the paragraph of the row in `k8s/README.md` and the term in `CONTEXT.md` state the new rule.

The change alters a message and the result of the command, so it carries a spec delta. The delta only ADDS requirements to `roadmap-alternatives`. It does not MODIFY a requirement, because the plan of #2949 modifies the requirements that this change would touch.

The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-alternatives`: adds the requirements "A skip-class item is not-applicable with no model call" and "A non-skip item needs a search before any verdict".

## Acceptance

- "A table test covers each class with no model call and the reason in the comment" is delivered by group 1.
- "A scripted model that answers a `feat` item without a search gets one more turn, and its second answer without a search ends as a failed check" is delivered by group 2.
- "The Firecrawl counter rises for a `feat` item in a replay" is delivered by group 2. The same test as the retry asserts the counter. The counter code exists already, so a separate group would test nothing new.
- "`uv run devops ci` passes" is checked by the last task of group 3. The required checks of the pull request also gate the merge.

## Impact

- Code: `src/devops_cli/roadmap/alternatives.py`, `src/devops_cli/roadmap/refine_investigation.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/lang/en/help.py`, `src/devops_cli/ai/tasks/roadmap_alternatives.md`, and the docstring of `Verdict` in `src/devops_cli/roadmap/store.py`.
- Tests: `tests/roadmap/test_roadmap_alternatives.py`.
- Documents: `k8s/README.md` (step 14), `CONTEXT.md` (term Alternative), and the generated command documents.
- Reuse and keep passing: `commit_type` in `src/devops_cli/roadmap/commit_title.py` (it reads the type of a title), `_marker_problem` and `validate_reply` in `src/devops_cli/roadmap/alternatives.py`, the base requirements of `openspec/specs/roadmap-alternatives/spec.md`, the tests that call `investigate` directly in `tests/roadmap/test_roadmap_refine_investigation.py`, and the refine tests in `tests/roadmap/test_roadmap_refine.py`, which use it.
- Deletes: the test `test_a_not_applicable_verdict_with_no_tool_run_is_kept`, which pins the rule that this change removes.
- Overlap: the plan of #2949 edits the same file, the same paragraph of `k8s/README.md`, and the requirement "The job refuses a reply with a source no tool returned". This change leaves that requirement alone. The second pull request to merge rebases onto the first. #2951 can reuse the public function `skip_class_of` as its list of exempt classes.

## Feasibility

All commands ran on 2026-11-01 at `origin/main` 9f3b7010.

- The metrics of the issue are right. `sum by (verdict) (increase(devops_cli_roadmap_alternatives_total[14d]))` gave `not-applicable` 36.5, and `covers` and `partly` 0. `sum by (result) (increase(devops_cli_firecrawl_searches_total[7d]))` gave `ok` 4.7. The `increase` function extrapolates, so the counts are close to the "about 34" and "about 4" of the issue.
- The comments of #886, #1082 and #1329 read "Alternatives check: not-applicable", "Tool: none found", with no reason and no query. Their titles are `feat(cli)`, `feat(k8s)` and `test(ai)`. Under the new rule, #1329 is a `test` skip class. #886 and #1082 must search.
- The mechanism is as the issue says. `_check_one` (line 677 of `src/devops_cli/roadmap/alternatives.py`) calls `investigate` once. `_refusal` (line 517 of the same file) refuses `not-applicable` only when a search or a fact read ran. A `not-applicable` reply with no search is kept. No code makes the model search, and no code retries.
- The issue says a reply of `not-applicable` after a tool ran "is rejected today". It is, but as a failed check at once, with no extra turn. The plan keeps that refusal as it is for the case after a search.
- The new rule and the old refusal meet. A non-skip item needs a search, and `not-applicable` after a search is refused. So the model can never give `not-applicable`. The plan states this and makes the refusal unconditional. The skip classes are the only source of the verdict.
- The item has no type field. `Item` in `src/devops_cli/roadmap/store.py` holds the title, the labels and the body. `commit_type(title)` in `src/devops_cli/roadmap/commit_title.py` already reads the type of a title, and `CONST_ROADMAP_COMMIT_TYPE_LABELS` says the title is the only source of the type. The plan reuses `commit_type`.
- "A fix of an internal defect with a stack trace and no new capability" has no test for "no new capability" that needs no model. The plan reads it as: the type is `fix`, and the body holds the text `Traceback (most recent call last)`. A fix adds no capability by definition of the type. `git grep -n "Traceback" -- src/devops_cli/roadmap` finds no existing helper.
- The retry works. A throwaway script (not committed) built a pydantic-ai 2.59.0 agent with one tool and an `@agent.output_validator` that raises `ModelRetry` once when no search ran. It used the scripted model of `tests/support/scripted_model.py`. A reply with no search, then a search, then a reply printed `(Reply(verdict='none'), ['q'], 3)`: three model requests, one search. Two replies with no search printed `(Reply(verdict='none'), [], 2)`: the validator lets the second reply through, so the job can refuse it. `investigate` in `src/devops_cli/roadmap/refine_investigation.py` (line 231) builds the agent and has no output validator today.
- Nothing newer did this work. `git log origin/main -- src/devops_cli/roadmap/alternatives.py` shows the last change of the check is #2688. The issues #2944, #2947, #2949, #2950 and #2951 are open and ask for other changes: the reason in the comment, the first pass, the failed item, the gauge and the Ready gate. The plan of #2949 changes the same file, and the Overlap line above says how the two meet.
- The files that the tasks name exist at `origin/main`: `git ls-files` lists `tests/roadmap/test_roadmap_alternatives.py`, `src/devops_cli/roadmap/commit_title.py`, `src/devops_cli/roadmap/refine_investigation.py` and `src/devops_cli/ai/tasks/roadmap_alternatives.md`.

## Existing Tool Considered

pydantic-ai covers the retry. Its output validator and `ModelRetry` give the model one more turn with the message history kept. The plan uses them. They do not cover the rest: the closed list of skip classes, the stack-trace rule and the refusal of a second reply are code of this project. The title type comes from the existing `commit_type`. No open tool classifies an issue for "needs an open alternative", so that part is built.

Written cost of the built part, as an estimate: about 30,000 tokens to write and test it in one implementation step, about 5,000 tokens each quarter to keep the list and the tests, and about 10,000 tokens to fix a wrong class. The elapsed time is about 1 hour of agent time. This change deletes one test and the old wording of one refusal message.
