# Tasks

## 1. Only the limit stops a refine round

- [x] 1.1 Write `test_a_backlog_full_of_ready_items_stops_refine_from_no_new_item_up_to_the_limit` in `tests/test_roadmap_refine.py`, and verify that `uv run devops ci test tests/test_roadmap_refine.py -k backlog_full_of_ready` fails on the base: the model gets the milestone item and the backlog P1 item, and not the P2 and P3 items
- [x] 1.2 Delete the Ready count and the second pass of `select_candidates`, the `config` arguments of `plan_refine`, `refine_item` and `_run_refine_adapter`, and `test_backlog_p2_and_p3_wait_for_the_configured_ready_target`, and verify that `uv run devops ci test tests/test_roadmap_refine.py tests/test_roadmap_run.py tests/test_roadmap_intake.py tests/test_roadmap_dry_runs.py` passes
- [x] 1.3 Give the new order in the docstring of `refine.py` and in the help text of `devops roadmap refine`, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops docs check` passes

## 2. The roadmap configuration holds only the board

- [x] 2.1 Make `test_an_unknown_key_fails_and_names_it` set `refine_ready_target`, and verify that `uv run devops ci test tests/test_roadmap_config.py` fails on the base
- [x] 2.2 Delete the field `refine_ready_target` of `RoadmapConfig`, `DEFAULT_ROADMAP_REFINE_READY_TARGET`, the comment that named the key in `.github/roadmap.toml`, `test_omitted_keys_take_their_defaults` and `test_a_ready_target_below_one_fails_and_names_the_key`, add `test_a_board_below_one_fails_and_names_the_key`, and verify that `uv run devops ci test tests/test_roadmap_config.py tests/test_pr_cmd.py tests/test_gh_cmd.py` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
