# Tasks

## 1. List the referencing test cases in the probe

Reads: `src/devops_cli/roadmap/stage/stage_probe.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/stage/test_roadmap_stage_probe.py`, `tests/support/roadmap_stage.py`. Changes: `src/devops_cli/roadmap/stage/stage_probe.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/stage/test_roadmap_stage_probe.py`.

- [ ] 1.1 Add `test_the_probe_lists_the_test_cases_that_name_a_symbol_of_a_cited_source_file` and `test_the_bound_names_the_test_module_and_the_source_it_left_unlisted` to `tests/roadmap/stage/test_roadmap_stage_probe.py`: the first probes a body that cites `src/devops_cli/roadmap/stage/stage_probe.py` and `tests/roadmap/stage/test_roadmap_stage_probe.py` through `probe_premise` and asserts that the line names `test_missing_path_an_open_plan_creates_is_a_dependency`, which calls `blocked_by`, and does not name `test_the_probe_stops_at_the_bound_and_lists_the_items_it_skipped`; the second cites the two files first and then eight present paths under `docs/`, so the ten commands of the probe end before the pairing, and asserts that the line that reports the reached bound names the test module and the source of the pair it could not read
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_probe.py` fails on the base
- [ ] 1.2 Add a cached read of a cited file's text to the per-run state of the probe in `src/devops_cli/roadmap/stage/stage_probe.py`: one `git cat-file -p <sha>:<path>` for each path, kept for the rest of the run, and a step that takes a cited test module and a cited source file, takes the names that the source binds at module level (the `def`, `class` and assignment targets of the top of its text, read with `ast`; a class attribute, a parameter, a local name and a dunder such as `__all__` are no bound name), keeps the `def test_...` cases of the module whose body holds one of those names as a word, and appends the new message with the module, the source and the cases, or the message that says the module holds no such case. In `probe_premise`, after the paths, the class fields and the identifiers, pair each cited test module that the commit holds with each cited source file that the commit holds, in the order of the cited paths, and list each pair; when no command is left for a pair, append one skipped item that names that test module and each source of the pairs that stay unlisted, and stop the pairing. Add `stage_probe_cases` and `stage_probe_cases_none` to `MESSAGES.roadmap` in `src/devops_cli/lang/en/messages.py` beside `stage_probe_skipped`. Group 1 adds its two cases and updates no existing test case of `tests/roadmap/stage/test_roadmap_stage_probe.py`: the listing reads with `cat-file`, which the pinned set of `test_every_command_reads_and_the_checkout_does_not_change` already holds, and the two bound cases cite no test module
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_probe.py` passes

## 2. State the invalidated test case in the planner prompt

Reads: `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`, `docs/roadmap/stage.md`. Changes: `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`, `docs/roadmap/stage.md`.

- [ ] 2.1 Add `test_the_prompt_names_the_test_case_that_a_change_invalidates` to `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`: it loads `src/devops_cli/ai/tasks/roadmap_stage_change.md` and asserts both rules, and asserts that `docs/roadmap/stage.md` holds the same rules
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_prompt_rules.py` fails on the base
- [ ] 2.2 Add two rules to the list of rules of `src/devops_cli/ai/tasks/roadmap_stage_change.md` after the bullet that chooses the kind of a group: a behavior group that changes a source file and names an existing test module in `reads` or `changes` names each test case of that module whose assertion the change invalidates, and a group that names an existing test module and invalidates no assertion in it states that it updates no existing test case. Add the matching sentence to the section of `docs/roadmap/stage.md` that describes the plan request. Group 2 adds its case and updates no existing test case of `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_prompt_rules.py` passes
- [ ] 2.3 Edit `docs/roadmap/stage.md` to state that the probe lists the referencing test cases and that the planner names each invalidated case or states that it updates no existing test case
  - Verification: `$ uv run devops ci docs` passes
- [ ] 2.4 Run `uv run devops roadmap eval stage --replay` on the base commit and on the change with the same model, and state the score before and after the change in a pull request comment
  - Verification: `$ uv run devops roadmap eval stage --replay` prints a score for the base commit and for the change

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
