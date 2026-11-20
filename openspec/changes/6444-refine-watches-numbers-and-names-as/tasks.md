# Tasks

## 1. Keep only the paths that the tree holds in a wait and in explain

Kind: behavior. Reads: `src/devops_cli/roadmap/refine/refine.py`, `src/devops_cli/roadmap/explain.py`, `src/devops_cli/roadmap/plan_read.py`, `src/devops_cli/config/constants.py`, `tests/support/roadmap_refine.py`, `tests/roadmap/refine/test_roadmap_refine_person_wait.py`, `tests/roadmap/refine/test_roadmap_refine_cited_paths.py`, `tests/roadmap/implement/test_roadmap_implement_plan_reason.py`. Changes: `src/devops_cli/roadmap/refine/refine.py`, `src/devops_cli/roadmap/explain.py`, `tests/roadmap/refine/test_roadmap_refine_person_wait.py`.
Adds: `_tree_holds`

- [x] 1.1 `test_a_wait_text_keeps_only_the_paths_of_the_tree` in `tests/roadmap/refine/test_roadmap_refine_person_wait.py`: a wait text names `0.202`, `v1.37.2`, `ai.portkey_url` and `deps.dev` before two files of the clone, and `text_paths` through `plan_refine` records only the two files in `refine.wait_refs`; further cases give six real files, a period, a comma and a directory to `text_paths`, assert that `path_changed_at` records no read of a false value, and give `refine_left_out` the tree for the explain verdict
  - Verification: `$ uv run devops ci test tests/roadmap/refine/test_roadmap_refine_person_wait.py` fails on the base
- [x] 1.2 Write the failing case first. In `src/devops_cli/roadmap/refine/refine.py`, add a period and a comma to the trailing character class of `_CITED_PATH_RE` and keep the path group. Add `_tree_holds(path, tree)`, which reports that the tree holds the path as a file or holds a tracked path under it, and give `text_paths` the keyword `tree`, which keeps only the candidates that `_tree_holds` accepts and then takes the first `CONST_ROADMAP_REFINE_MAX_WAIT_CHECKS` of them; a call with no tree keeps every candidate. Give the keyword `tree` to `_select_round`, `_Selection`, `_still_waiting`, `_wait_state`, `_wait_refs`, `select_candidates` and `refine_left_out`, and pass it down. In `plan_refine`, after `sha = inspect_checkout(source_path, repo)`, read the tracked paths once with `tree_files` at `sha` and give the set to `_select_round`. In `src/devops_cli/roadmap/explain.py`, read the tracked paths once with `tree_files` of the clone's `HEAD` in `explain_item` and give the set to `_refine_verdict` and to `refine_left_out`. In `tests/roadmap/refine/test_roadmap_refine_person_wait.py`, add the cases of the four false values before two real files, the cap of six real files, the period, the comma, the directory, the commits read of a false value, and the explain verdict
  - Verification: `$ uv run devops ci test tests/roadmap/refine/test_roadmap_refine_person_wait.py` passes

## 2. Filter the paths of a rejected plan's hold

Kind: behavior. Reads: `src/devops_cli/roadmap/refine/refine.py`, `src/devops_cli/roadmap/planned.py`, `src/devops_cli/roadmap/plan_read.py`, `src/devops_cli/roadmap/stage/stage.py`, `tests/support/roadmap_stage.py`, `tests/roadmap/stage/test_roadmap_stage_rejected.py`. Changes: `src/devops_cli/roadmap/stage/stage_rejected.py`, `src/devops_cli/roadmap/stage/stage.py`, `tests/roadmap/stage/test_roadmap_stage_rejected.py`.

- [x] 2.1 `test_a_rejected_plan_keeps_only_the_paths_of_the_tree` in `tests/roadmap/stage/test_roadmap_stage_rejected.py`: the reason of a rejected plan names `0.202` and `v1.37.2` before `CONTEXT.md`, and `text_paths` through the hold records `CONTEXT.md` alone in `stage.rejected`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_rejected.py` fails on the base
- [x] 2.2 Write the failing case first. Change `rejection` of `ClosedPlan` in `src/devops_cli/roadmap/stage/stage_rejected.py` to take the tree of the default branch and to give it to `text_paths` as its `tree` keyword. In `_rejections` of `src/devops_cli/roadmap/stage/stage.py`, read the tracked paths once with `tree_files` at `origin/<default>`, the ref that the module already fetched for the planned changes, and give the set to each `closed.rejection(tree)`. In `tests/roadmap/stage/test_roadmap_stage_rejected.py`, cite `CONTEXT.md` in the constant `EVIDENCE`, because the clone of `tests/support/roadmap_stage.py` writes `CONTEXT.md`; change the expected `paths` of the record case to `CONTEXT.md`; move both `seed_commit` calls of the hold case to `CONTEXT.md`; and add the case of the decimal and the version
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_rejected.py` passes

## 3. State the tree filter in the refine document

Kind: other. Reads: `src/devops_cli/roadmap/refine/refine.py`, `docs/roadmap/refine.md`. Changes: `docs/roadmap/refine.md`.

- [ ] 3.1 State in `docs/roadmap/refine.md` that a wait records only the paths that the tree of the commit of the round holds, that the five slots go to the first five real paths, and that a decimal, a version, a dotted setting or a domain takes no slot
  - Verification: `$ uv run devops ci docs` passes
- [ ] 3.2 Edit `docs/roadmap/refine.md` to state the tree filter of the wait paths and that the five slots go to the first five real paths. Update `tests/roadmap/test_roadmap_limit_classes.py`
  - Verification: `$ uv run devops ci docs` passes

## Criteria

- Group 1: A test: a wait text that names `0.202`, `v1.37.2`, `ai.portkey_url` and `deps.dev` before 2 real files gives a `refine.wait_refs` with the 2 real files and none of the 4 tokens.
- Group 1: A test: a wait text that names 6 real files keeps the first 5, as today.
- Group 1: A test: a real path that a period or a comma follows ("Read src/devops_cli/commands/ai.py.") is in `refine.wait_refs`.
- Group 2: A test: the stage hold of a rejected plan (`stage_rejected.py:172`) keeps no number or setting key as a path.
- Group 1: A test: a false path makes no commits read (`path_changed_at`).
- Pending person: Live proof: after the merge and the release, the next round that reads the comments of #4671 records no `0.202` or `0.453`. A comment gives the new record value., Only a round of the Service after the release writes the new record value on #4671, and a person reads it and comments it.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
