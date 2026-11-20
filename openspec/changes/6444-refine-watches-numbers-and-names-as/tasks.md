# Tasks

## 1. Keep only the paths that the tree holds in a wait and in explain

Kind: behavior. Reads: `src/devops_cli/roadmap/refine/refine.py`, `src/devops_cli/roadmap/explain.py`, `src/devops_cli/roadmap/plan_read.py`, `src/devops_cli/config/constants.py`, `tests/support/roadmap_refine.py`, `tests/roadmap/refine/test_roadmap_refine_person_wait.py`, `tests/roadmap/refine/test_roadmap_refine_cited_paths.py`, `tests/roadmap/implement/test_roadmap_implement_plan_reason.py`. Changes: `src/devops_cli/roadmap/refine/refine.py`, `src/devops_cli/roadmap/explain.py`, `tests/roadmap/refine/test_roadmap_refine_person_wait.py`, `tests/support/roadmap_refine.py`.
Adds: `_tree_holds`

- [x] 1.1 `test_a_wait_text_keeps_only_the_paths_of_the_tree` in `tests/roadmap/refine/test_roadmap_refine_person_wait.py`: a wait text names `0.202`, `v1.37.2`, `ai.portkey_url` and `deps.dev` before two files of the clone, and `text_paths` through `plan_refine` records only the two files in `refine.wait_refs`; further cases give six real files, a period, a comma and a directory to `text_paths`, assert that `path_changed_at` records no read of a false value, and give `refine_left_out` the tree for the explain verdict
  - Verification: `$ uv run devops ci test tests/roadmap/refine/test_roadmap_refine_person_wait.py` fails on the base
- [x] 1.2 Write the failing case first. In `src/devops_cli/roadmap/refine/refine.py`, add a period and a comma to the trailing character class of `_CITED_PATH_RE` and keep the path group. Add `_tree_holds(path, tree)`, which reports that the tree holds the path as a file or holds a tracked path under it, and give `text_paths` the keyword `tracked_paths`, which keeps only the candidates that `_tree_holds` accepts and then takes the first `CONST_ROADMAP_REFINE_MAX_WAIT_CHECKS` of them; a call with no tree keeps every candidate. Give the keyword `tracked_paths` to `_select_round`, `_Selection`, `_still_waiting`, `_wait_state`, `_wait_refs`, `select_candidates` and `refine_left_out`, and pass it down. In `plan_refine`, after `sha = inspect_checkout(source_path, repo)`, read the tracked paths once with `tree_files` at `sha`, which the function imports inside its body because `plan_read` imports `stage_change`, which imports `refine`, and give the set to `_select_round`. In `src/devops_cli/roadmap/explain.py`, give `_refine_verdict` and `refine_left_out` the keyword `tracked_paths`. In `tests/support/roadmap_refine.py`, make `_answer_refine_git` answer the read of the whole tree, `ls-tree -r --name-only -z <sha>`, with the files of the clone. `tests/roadmap/test_roadmap_limit_classes.py` already registers `CONST_ROADMAP_REFINE_MAX_WAIT_CHECKS`, and the change adds no limit constant, so that file does not change. In `tests/roadmap/refine/test_roadmap_refine_person_wait.py`, add the cases of the four false values before two real files, the cap of six real files, the period, the comma, the directory, the commits read of a false value, and the explain verdict
  - Verification: `$ uv run devops ci test tests/roadmap/refine/test_roadmap_refine_person_wait.py tests/roadmap/refine/test_roadmap_refine_recorded_wait.py` passes

## 2. Filter the paths of a rejected plan's hold

Kind: behavior. Reads: `src/devops_cli/roadmap/refine/refine.py`, `src/devops_cli/roadmap/planned.py`, `src/devops_cli/roadmap/plan_read.py`, `src/devops_cli/roadmap/stage/stage.py`, `tests/support/roadmap_stage.py`, `tests/roadmap/stage/test_roadmap_stage_rejected.py`. Changes: `src/devops_cli/roadmap/stage/stage_rejected.py`, `src/devops_cli/roadmap/stage/stage.py`, `tests/roadmap/stage/test_roadmap_stage_rejected.py`.

- [x] 2.1 `test_a_rejected_plan_keeps_only_the_paths_of_the_tree` in `tests/roadmap/stage/test_roadmap_stage_rejected.py`: the reason of a rejected plan names `0.202` and `v1.37.2` before `CONTEXT.md`, and `text_paths` through the hold records `CONTEXT.md` alone in `stage.rejected`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_rejected.py` fails on the base
- [x] 2.2 Write the failing case first. Change `rejection` of `ClosedPlan` in `src/devops_cli/roadmap/stage/stage_rejected.py` to take the tree of the default branch and to give it to `text_paths` as its `tracked_paths` keyword. In `_rejections` of `src/devops_cli/roadmap/stage/stage.py`, read the tracked paths once with `tree_files` at `origin/<default>`, the ref that the module already fetched for the planned changes, and give the set to each `closed.rejection(tree)`. In `tests/roadmap/stage/test_roadmap_stage_rejected.py`, cite `CONTEXT.md` in the constant `EVIDENCE`, because the clone of `tests/support/roadmap_stage.py` writes `CONTEXT.md`; change the expected `paths` of the record case to `CONTEXT.md`; move both `seed_commit` calls of the hold case to `CONTEXT.md`; and add the case of the decimal and the version
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_rejected.py` passes

## 3. Read a wait record again when it holds a path that the tree lacks

Kind: behavior. Reads: `src/devops_cli/roadmap/refine/refine.py`, `tests/support/roadmap_refine.py`, `tests/roadmap/refine/test_roadmap_refine_recorded_wait.py`. Changes: `src/devops_cli/roadmap/refine/refine.py`, `tests/roadmap/refine/test_roadmap_refine_recorded_wait.py`.

- [x] 3.1 `test_a_record_written_before_the_tree_filter_gets_the_paths_of_the_tree` in `tests/roadmap/refine/test_roadmap_refine_recorded_wait.py`: an item waits on a person with no `refine.block_paths`, and its record, which a round wrote before the change for the comments that the issue holds now, holds `refine.wait_refs` `0.202,src/sample.py`. A round records `src/sample.py` alone, reads no commits of `0.202`, and makes no model call. On the base, `_recorded_reads` gives the record as it is, so the record keeps `0.202,src/sample.py` and `path_changed_at` reads `0.202`
  - Verification: `$ uv run devops ci test tests/roadmap/refine/test_roadmap_refine_recorded_wait.py` fails on the base
- [ ] 3.2 Write the failing case first. In `src/devops_cli/roadmap/refine/refine.py`, give `_recorded_reads` the set `tracked_paths` and return None when the recorded `refine.wait_refs` holds a path that the set lacks, so `_wait_state` reads the comments once and `_read_marks` gives the filtered references. Give `_named_cause_ended` and `_person_wait_over` the set too, and remove each recorded path that the set lacks before the read of its commits
  - Verification: `$ uv run devops ci test tests/roadmap/refine/test_roadmap_refine_recorded_wait.py tests/roadmap/refine/test_roadmap_refine_person_wait.py` passes

## 4. Keep each path of a run of paths

Kind: behavior. Reads: `src/devops_cli/roadmap/refine/refine.py`, `tests/roadmap/refine/test_roadmap_refine_person_wait.py`, `tests/roadmap/refine/test_roadmap_refine_cited_paths.py`. Changes: `src/devops_cli/roadmap/refine/refine.py`, `tests/roadmap/refine/test_roadmap_refine_person_wait.py`.

- [x] 4.1 `test_a_run_of_paths_keeps_each_path` in `tests/roadmap/refine/test_roadmap_refine_person_wait.py`: `text_paths('Read a.py b.py c.py d.py')` gives `a.py`, `b.py`, `c.py` and `d.py`. On the base, the trailing boundary of `_CITED_PATH_RE` consumes the space before `b.py` and `d.py`, so the call gives `['a.py', 'c.py']`
  - Verification: `$ uv run devops ci test tests/roadmap/refine/test_roadmap_refine_person_wait.py` fails on the base
- [ ] 4.2 Write the failing case first. In `src/devops_cli/roadmap/refine/refine.py`, make the trailing boundary of `_CITED_PATH_RE` the lookahead `(?=[\s\)\]`:.,]|$)`, and keep the path group and the line groups
  - Verification: `$ uv run devops ci test tests/roadmap/refine` passes

## 5. Read the tree of the default branch in explain, and list the tree reads in the dry runs

Kind: behavior. Reads: `src/devops_cli/roadmap/explain.py`, `src/devops_cli/roadmap/planned.py`, `src/devops_cli/roadmap/request_plan.py`, `tests/roadmap/test_roadmap_explain.py`, `tests/roadmap/test_roadmap_dry_runs.py`, `tests/roadmap/implement/test_roadmap_implement_amend.py`. Changes: `src/devops_cli/roadmap/explain.py`, `src/devops_cli/roadmap/request_plan.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_explain.py`, `tests/roadmap/test_roadmap_dry_runs.py`.

- [x] 5.1 `test_the_refine_verdict_reads_the_tree_of_the_default_branch` in `tests/roadmap/test_roadmap_explain.py`: a wait names a file that `origin/main` holds and the `HEAD` of the clone does not, and a commit changed that file after the start of the wait, so explain says that refine takes the item. `test_the_stage_and_explain_plans_list_the_read_of_the_tree_of_the_default_branch` in `tests/roadmap/test_roadmap_dry_runs.py`: the dry runs of stage and explain list `git -C <model-clone> ls-tree -r --name-only -z origin/main`. On the base, explain reads the tree of `HEAD`, and no dry run lists the read
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_explain.py tests/roadmap/test_roadmap_dry_runs.py` fails on the base
- [ ] 5.2 Write the failing case first. In `explain_item` of `src/devops_cli/roadmap/explain.py`, read the tracked paths with `tree_files` at `origin/<default>` after `read_planned_changes` fetched it. In `src/devops_cli/roadmap/request_plan.py`, list that read in `stage_requests`, under the condition of a closed plan pull request, and in `explain_requests`, with its text in `src/devops_cli/lang/en/messages.py`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_explain.py tests/roadmap/test_roadmap_dry_runs.py` passes

## 6. State the tree filter in the refine and stage documents

Kind: other. Reads: `src/devops_cli/roadmap/refine/refine.py`, `src/devops_cli/roadmap/stage/stage_rejected.py`, `docs/roadmap/refine.md`, `docs/roadmap/stage.md`. Changes: `docs/roadmap/refine.md`, `docs/roadmap/stage.md`.

- [ ] 6.1 State in `docs/roadmap/refine.md` that a wait records only the paths that the tree of the commit of the round holds, that the five slots go to the first five real paths, that a decimal, a version, a dotted setting or a domain takes no slot, that a round reads the comments once for a record that holds a path that the tree lacks, and that a file that the tree does not hold ends no wait
  - Verification: `$ uv run devops ci docs` passes
- [ ] 6.2 State in `docs/roadmap/stage.md` that the record of a rejected plan holds only the files of the reason that the default branch holds
  - Verification: `$ uv run devops ci docs` passes

## Criteria

- Group 1: A test: a wait text that names `0.202`, `v1.37.2`, `ai.portkey_url` and `deps.dev` before 2 real files gives a `refine.wait_refs` with the 2 real files and none of the 4 tokens.
- Group 1: A test: a wait text that names 6 real files keeps the first 5, as today.
- Group 1: A test: a real path that a period or a comma follows ("Read src/devops_cli/commands/ai.py.") is in `refine.wait_refs`.
- Group 2: A test: the stage hold of a rejected plan (`stage_rejected.py:172`) keeps no number or setting key as a path.
- Group 1: A test: a false path makes no commits read (`path_changed_at`).
- Group 3: A test: a record written before the change, with `0.202` and a real file, gets the real file alone and makes no `path_changed_at` read for `0.202`.
- Group 4: A test: a run of four paths gives the four paths.
- Pending person: Live proof: after the merge and the release, the next round that reads the comments of #4671 records no `0.202` or `0.453`. A comment gives the new record value., Only a round of the Service after the release writes the new record value on #4671, and a person reads it and comments it. Group 3 makes that round read the comments with no new comment.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
