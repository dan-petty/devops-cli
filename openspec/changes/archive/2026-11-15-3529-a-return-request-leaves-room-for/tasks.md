# Tasks

## 1. Bound the earlier plan in the gate return request

Kind: behavior. Reads: `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/roadmap/stage/stage_request.py`, `src/devops_cli/roadmap/stage/stage_change.py`, `src/devops_cli/ai/context_budget.py`, `src/devops_cli/roadmap/refine/refine_investigation.py`, `tests/roadmap/stage/test_roadmap_stage_window.py`, `tests/support/roadmap_stage.py`, `tests/support/scripted_model.py`, `tests/support/builders.py`. Changes: `src/devops_cli/roadmap/stage/stage_return.py` (new), `src/devops_cli/roadmap/stage/stage.py`, `tests/roadmap/stage/test_roadmap_stage_window.py`.

- [x] 1.1 Write `test_a_gate_return_with_the_full_earlier_plan_leaves_room_for_the_tools` and `test_a_return_request_keeps_the_full_earlier_plan_when_it_fits` in `tests/roadmap/stage/test_roadmap_stage_window.py` first: the first names the scenario A gate return with a long earlier plan, prints the count and the limit of 49,152 tokens, and asserts that the return request counts under the limit with `read_spec` offered and `problem` in the request; the second names the scenarios The full earlier plan fits and The keys of the earlier plan stay, and asserts that `previous` is the whole earlier plan and holds every key when the request fits
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_window.py` fails on the base
- [x] 1.2 Write the two tests in `tests/roadmap/stage/test_roadmap_stage_window.py` beside `_first_request_tokens`, each with `monkeypatch` of `stage.task_window` to `WINDOW`, a script of `call("list_files", directory="src")` and then the plan, and an item whose body cites the sample module that `tests/support/roadmap_stage.py` writes, so the content gate refuses the plan because its `feasibility` quotes no probe line. The long earlier plan is `make_stage_proposal(why=_words(20_000))`, and each test measures `script.seen[2]` as the run hook counts it. Add `src/devops_cli/roadmap/stage/stage_return.py` with `request_tokens` and `bound_previous`: `request_tokens` counts the JSON text that `_ask_plan` sends, and `bound_previous` cuts the texts of `previous` with `truncate_to_token_limit` only when that count passes `tool_stop(window)` less `CONST_ROADMAP_STAGE_TOOL_RESERVE_TOKENS`, keeping every key and every path. The change adds no constant, so the `CONST_ROADMAP_` entry that `tests/roadmap/test_roadmap_limit_classes.py` declares stays as it is, and this task names that declared path. Change `src/devops_cli/roadmap/stage/stage.py` so `returned` takes the window and both call sites pass `self._window`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_window.py` passes

## 2. Bound the earlier plan in the review repair request

Kind: behavior. Reads: `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/roadmap/stage/stage_return.py`, `src/devops_cli/roadmap/stage/stage_verify.py`, `tests/roadmap/stage/test_roadmap_stage_window.py`, `tests/roadmap/stage/test_roadmap_stage_repair_return.py`, `tests/support/roadmap_stage.py`, `tests/support/fakes/model.py`. Changes: `src/devops_cli/roadmap/stage/stage.py`, `tests/roadmap/stage/test_roadmap_stage_window.py`.

- [x] 2.1 Write `test_a_repair_return_request_of_a_large_plan_leaves_room_for_the_tools` in `tests/roadmap/stage/test_roadmap_stage_window.py` first: it names the scenarios A review repair with a long earlier plan and The full earlier plan passes the limit, gives the verifier one open finding on the plan whose `why` is 20,000 words, and asserts that the repair return request counts under 49,152 tokens with `read_spec` offered and `problem` kept
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_window.py` fails on the base
- [x] 2.2 Write the test first, with the verifier of `tests/support/fakes/model.py` routed to one open finding on group 1 of the plan and then to the later review that marks it gone, a script that lists the files of `src` and answers the plan of 20,000 words, and a measure of `script.seen[2]` as the run hook counts it. Then replace the dictionary that `_repaired` builds in `src/devops_cli/roadmap/stage/stage.py` with `bound_previous` over the request, the earlier plan, the problem of the open findings and `self._window`, so the review repair measures and bounds the earlier plan as the gate return does
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_window.py` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
