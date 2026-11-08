# Proposal

## Why

A search outage gives a false "no tool" verdict in the alternatives check (#4044). `AlternativesTools.search_web` in `src/devops_cli/roadmap/alternatives.py` records a `Search` for every query, also when no provider answered. `cited_web_search` answers a failed search with the text "The search failed: no provider answered." and gives the caller no signal. `_refusal` accepts a verdict when the tools recorded one query. So the model can give the verdict `none` after searches that all failed, and the check writes a false "no tool" result that stands for `DEFAULT_ROADMAP_ALTERNATIVES_RECHECK_DAYS` (30 days).

## What Changes

- `cited_web_search` in `src/devops_cli/roadmap/refine/refine_investigation.py` returns a small frozen result with the `text` of the answer and the flag `answered`. `answered` is true for a result list and for a real empty answer. It is false when no provider answered (`SearchFailed`). It is also false when the guard refused the query (`SearchQueryRefused`), because no search ran. This last point is a choice: the issue names only `SearchFailed`. The refine tool uses `text` and its text does not change.
- `AlternativesTools.search_web` records a `Search` only when `answered` is true. A separate counter holds the attempts, so a failing provider cannot let the model call the tool without limit. `CONST_ROADMAP_ALTERNATIVES_MAX_SEARCHES` limits the attempts.
- `_refusal` and `_search_missing` read the answered searches. A reply that follows no answered search gets one more turn. A second such reply ends as a `CheckFailure` of the class `RefusedReply`, so the retry delay applies and nothing is written for the item.
- The histogram `devops_cli_roadmap_alternatives_searches` and the comment list count the answered searches. The counter `devops_cli_web_searches_total` still counts every attempt by its backend and result, because it counts requests to providers.
- The failure reason and the retry message say "no answered search". The prompt of the check, `docs/roadmap/alternatives.md` and `docs/TELEMETRY.md` say the same.
- The change alters a message and the behavior of the Service row, so the spec carries a delta. The order rule of #2951 does not change. The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-alternatives`: Only an answered search counts as a search

## Impact

- Code: `src/devops_cli/roadmap/refine/refine_investigation.py`, `src/devops_cli/roadmap/alternatives.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/ai/tasks/roadmap_alternatives.md`
- Tests: `tests/roadmap/test_roadmap_alternatives_search.py`, `tests/roadmap/test_roadmap_alternatives.py`, `tests/roadmap/refine/test_roadmap_refine_investigation.py`
- Documents: `docs/roadmap/alternatives.md`, `docs/TELEMETRY.md`
- Settings: none. The change adds, removes, renames or tightens no setting. `k8s/devops/configmap.example.yaml` and the live ConfigMap stay as they are, so the change needs no ConfigMap-load test.

## Feasibility

- I read the code at origin/main. `cited_web_search` returns `str`. `SearchQueryRefused` and `SearchFailed` both answer as text with no flag. `AlternativesTools.search_web` appends `Search(query, len(found))` after every call. `queries` lists them. `_search_missing` and `_refusal` accept a verdict when `queries` is not empty. `validate_reply` turns a refusal that remains after the retry into a `CheckFailure` with the class `RefusedReply`.
- `web_search` in `src/devops_cli/ai/web_search.py` raises `SearchFailed` only when no provider answered, and returns `[]` when some provider answered with no hit. So the flag has a source and needs no new probe.
- The new tests ran against origin/main. The tests of the result (`shared_text`, `empty_answer`, the refused query) fail there because the function returns `str`. The tests of the check (`all_searches_failed`) fail there: a run whose searches all fail gives a written check with the verdict `none`, and a failed search is in `tools.searches`. `devops ci fail-to-pass --base origin/main` runs them.
- One test is a guard that passes on origin/main: the verdict after an empty answer, which stays accepted.
- No merged change, no open issue and no open pull request does this work, and no ADR replaces it. #4034 (merged) is the base. #4049 and #4054 change the same file and come after this item.

## Existing Tool Considered

Existing project code. `SearchFailed` and `web_search` already are the source of the failure signal, so no library is needed. The change adds one small frozen dataclass and deletes nothing. The written cost is about 30k tokens and 1.5 hours to build with the tests, about 2k tokens a quarter to keep, and about 8k tokens and 0.5 hours to fix.

## Dependencies

None.
