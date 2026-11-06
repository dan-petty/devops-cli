# Proposal

## Why

Issue #2944 says that a verdict of the alternatives check is hard to audit. A person cannot tell what the model searched, how many results each search gave, which tools it read, or why it gave the verdict. The comment of a check already lists the queries and the sources (#2650). It does not give the result count of a query, the tools that the run read, or a reason. It shows every source, with no bound.

## What Changes

- The reply of the model holds a new key `reason`: one or two sentences that say why the verdict fits. The job refuses a reply with no reason.
- The tools keep a `Search` for each search that ran: the query and the number of results with an http or https URL. A failed search has no result.
- The comment of a check gains a `Reason:` line, a `Tools considered:` list and a result count on each query. The list holds every tool whose facts a tool read, each with its URL, license and last activity. A skip-class check keeps its `Class:` line and gains none of these, because it makes no model call and no search.
- The comment shows at most `CONST_ROADMAP_ALTERNATIVES_MAX_COMMENT_SOURCES` (5) sources, and a line that says how many it leaves out. GitHub shows each URL on its own line as a link.
- The prompt `roadmap_alternatives.md` asks for `reason`.
- The change has a spec delta: the comment is an observable output of a `devops` command.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-alternatives`: the comment gives the reason, the tools considered and the result count of each search, and bounds its sources.

## Impact

- Code: `src/devops_cli/roadmap/alternatives.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/ai/tasks/roadmap_alternatives.md`.
- Tests: `tests/roadmap/test_roadmap_alternatives.py`.
- Spec: `openspec/specs/roadmap-alternatives/spec.md`.

## Acceptance

| Criterion of the issue | Delivered by |
| :--- | :--- |
| A test with a scripted model and a fake search shows the queries and the reason in the comment | Group 1: the tests for the result counts, the reason and the tools considered |
| A comment of an old check is not rewritten | Group 1: the test `test_a_later_check_adds_a_comment_and_leaves_the_comment_of_the_first_unchanged`. A check only adds a comment, and the code has no path that edits one |
| The text cites no more than a bounded number of results, and a result URL is shown as a link | Group 1: the sources bound and the test for it. GitHub shows a bare URL as a link |
| `uv run devops ci` passes | Group 2 |

The marker that the check keeps is `CONST_ROADMAP_ALTERNATIVES_COMMENT_MARKER`, `<!-- devops roadmap alternatives -->`. The refine question of 2026-11-01 asks for it, and the code already has the answer.

## Feasibility

All commands ran on `origin/main` at `bc5f2412`, in the worktree of this change.

- The comment builder exists. `_comment_of` in `src/devops_cli/roadmap/alternatives.py` writes the marker, the verdict, the tool, `Covers:`, `Lacks:`, `Searches run:` and `Sources:`. It writes no reason, no result count and no list of the tools read.
- The facts exist already. `AlternativesTools.facts` holds a `ToolFacts` (name, URL, license, last activity) for each repository or package that the run read, so the list of tools needs no new read and no new request.
- The result count is known where the search runs. `cited_web_search` adds each http or https URL of a result to the set it gets, and that set is empty at the start of a search, so its size is the count.
- The comment is never edited. `apply_alternatives` calls `store.comment_on` for a new comment. It has no call that edits one. The test pins this.
- The skip class and the `not-applicable` text exist (#2946): the comment already gives `Class: <class>`. This change adds nothing to it.
- Nothing newer did this. No open pull request touches `alternatives.py`, and the plan of the issue names no other file.

## Existing Tool Considered

The alternatives check of 2026-11-04 on the issue found no open tool that writes this internal comment. The comment is the output of one project job, with a marker, a fixed sentence about what the check does not do, and URLs that only the job's own tools returned. The cost of building it: about 150 lines of code and 140 lines of test, about 30,000 tokens to write and review, in one session. Keeping it costs one new key in the reply and a few message strings. The change deletes no internal code.

## Workflow follow-up

None. The change fits one pull request.
