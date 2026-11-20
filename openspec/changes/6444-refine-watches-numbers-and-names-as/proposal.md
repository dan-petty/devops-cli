# Proposal

## Why

Refine records the paths of a person wait in `refine.wait_refs`, and `text_paths` takes every dotted token of the wait text as a path (#6444). A decimal, a version, a dotted setting, a Python name or a domain then fills one of the 5 slots of `CONST_ROADMAP_REFINE_MAX_WAIT_CHECKS`, so a real file that the text names later is not watched and a change of that file ends no wait. Each false path also costs one GitHub commits read in each round that checks the wait, and the hold of a rejected plan reads the same extractor, so it has the same defect.

## What Changes

- `text_paths` keeps a candidate only when the tree that its caller gives holds it as a file or as a directory that holds a tracked path, and a call that gives no tree keeps every candidate.
- `text_paths` applies `CONST_ROADMAP_REFINE_MAX_WAIT_CHECKS` after the tree filter, so the first five real paths take the slots.
- `_CITED_PATH_RE` accepts a period or a comma after a path, so a file that ends a sentence is a candidate.
- `plan_refine` reads the tracked paths once with `tree_files` at the commit of the round and gives the set to the selection.
- `_select_round`, `_Selection`, `_still_waiting`, `_wait_state`, `_wait_refs`, `select_candidates` and `refine_left_out` take the keyword `tree`, which defaults to None, as `frames` and `graph` already do.
- `explain_item` reads the tree of the clone's `HEAD` with `tree_files` and gives it to `_refine_verdict` and to `refine_left_out`, so `devops roadmap explain` uses the tree that a round reads.
- `ClosedPlan.rejection` takes the tree of the default branch and gives it to `text_paths`, so the record of a rejected plan holds no decimal, version, dotted setting or domain.
- `_rejections` reads the tracked paths once with `tree_files` at `origin/<default>`, the ref that the module already fetched for the planned changes.
- The stage hold test cites `CONTEXT.md`, which its clone writes, and seeds the commits of the hold case on that file.
- A value that the tree does not hold never reaches `refine.wait_refs`, so the wait check reads no commits for it.
- `docs/roadmap/refine.md` states that a wait records only the paths that the tree of the round holds and that the five slots go to the first five real paths.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-refine/waits`: A wait records only the paths that the tree holds, The five-path cap counts only the paths that the tree holds, A path that a period or a comma follows is kept, A value that the tree does not hold costs no commits read, A directory that the tree holds is a watched path, The explain verdict reads the same tree as a round
- `roadmap-stage/returns`: A rejected plan's hold keeps only the paths that the tree holds

## Impact

- Code: `src/devops_cli/roadmap/refine/refine.py`, `src/devops_cli/roadmap/explain.py`, `src/devops_cli/roadmap/stage/stage_rejected.py`, `src/devops_cli/roadmap/stage/stage.py`
- Documents: `docs/roadmap/refine.md`
- Tests: `tests/roadmap/refine/test_roadmap_refine_person_wait.py`, `tests/roadmap/stage/test_roadmap_stage_rejected.py`

## Feasibility

- The probes answer holds this line word for word: The path `src/devops_cli/roadmap/refine/refine.py` is a file of the staging commit. The `read_file` call of that file at lines 770-830 showed src/devops_cli/roadmap/refine/refine.py:780:`_CITED_PATH_RE = re.compile(`, whose trailing boundary is a space, a bracket, a backtick, a colon or the end of the text, and no tree check.
- The probes answer holds this line word for word: The path `refine.wait_refs` is no file of the staging commit. No commit in the history deleted or renamed it. So `refine.wait_refs` is the key of the job record, and the premise is the code that writes it.
- The probes answer holds this line word for word: The path `ai.portkey_url` is no file of the staging commit. No commit in the history deleted or renamed it. So it is the dotted setting that the issue reports, and no commit removed it.
- The `read_file` call of `src/devops_cli/roadmap/refine/refine.py:def text_paths` showed the cap after the unfiltered candidates: src/devops_cli/roadmap/refine/refine.py:2525:`def text_paths(text: str) -> list[str]:` and src/devops_cli/roadmap/refine/refine.py:2533:`return paths[:CONST_ROADMAP_REFINE_MAX_WAIT_CHECKS]`.
- The bound is 5 at the staged commit: src/devops_cli/config/constants.py:3474:`CONST_ROADMAP_REFINE_MAX_WAIT_CHECKS: Final[int] = 5`.
- The record joins the issues and the paths: src/devops_cli/roadmap/refine/refine.py:2601:`return ",".join([*(f"#{number}" for number in _text_issues(text, own)), *text_paths(text)])`, which `_wait_state` fills at src/devops_cli/roadmap/refine/refine.py:2784:`refs = _wait_refs(_wait_text(item.body, comments), item.number)`.
- The wait check reads the commits of each recorded path: src/devops_cli/roadmap/refine/refine.py:2513:`changed = store.path_changed_at(path)` inside src/devops_cli/roadmap/refine/refine.py:2604:`def _named_cause_ended(store: RoadmapStore, refs: str, since: datetime) -> bool:`.
- The stage hold calls the same extractor: src/devops_cli/roadmap/stage/stage_rejected.py:172:`paths = text_paths(_reason_text(self.reason)) if self.reason is not None else []` in src/devops_cli/roadmap/stage/stage_rejected.py:168:`def rejection(self) -> tuple[RejectedPlan, str]:`.
- The round that calls the hold already holds the checkout and the default branch: src/devops_cli/roadmap/stage/stage.py:3091:`def _rejections(` and src/devops_cli/roadmap/stage/stage.py:3109:`plan, comment = closed.rejection()`, with the branch in src/devops_cli/roadmap/planned.py:41:`class PlannedChanges:`.
- The `read_file` call of `src/devops_cli/roadmap/explain.py:def explain_item` showed the explain path: src/devops_cli/roadmap/explain.py:285:`checkout = Path(source)` and src/devops_cli/roadmap/explain.py:305:`_refine_verdict(store, item),`, whose reader is src/devops_cli/roadmap/explain.py:152:`def _refine_verdict(store: RoadmapStore, item: Item) -> JobVerdict:` with src/devops_cli/roadmap/explain.py:155:`why = refine_left_out(store, item)`.
- The round reads the commit and then selects: src/devops_cli/roadmap/refine/refine.py:3875:`sha = inspect_checkout(source_path, repo)` and src/devops_cli/roadmap/refine/refine.py:3880:`candidates, waiting, queue = _select_round(`.
- The keyword reaches the wait reader through src/devops_cli/roadmap/refine/refine.py:3005:`class _Selection:`, src/devops_cli/roadmap/refine/refine.py:3062:`waits = _still_waiting(`, src/devops_cli/roadmap/refine/refine.py:2753:`def _wait_state(` and src/devops_cli/roadmap/refine/refine.py:2820:`def _still_waiting(`.
- The two public readers are src/devops_cli/roadmap/refine/refine.py:3127:`def select_candidates(` and src/devops_cli/roadmap/refine/refine.py:3079:`def refine_left_out(store: RoadmapStore, item: Item) -> str | None:`, which builds src/devops_cli/roadmap/refine/refine.py:3088:`selection = _Selection(store)`.
- The `search_code` call for `select_candidates(` lists the refine reader at src/devops_cli/roadmap/refine/refine.py:3127:`def select_candidates(` and the test modules that call it, so the keyword `tree` defaults to None and no test module changes.
- The `search_code` call for `candidates, waiting, queue = _select_round(` lists one place only, src/devops_cli/roadmap/refine/refine.py:3880:`candidates, waiting, queue = _select_round(`, so the round is the one production caller of the selection.
- The `search_code` call for `def refine_left_out` lists the definition at src/devops_cli/roadmap/refine/refine.py:3079:`def refine_left_out(store: RoadmapStore, item: Item) -> str | None:`, and the `read_file` call of `src/devops_cli/roadmap/explain.py:def _refine_verdict` showed its one production call, so the new keyword breaks no caller.
- The tree read is one local git call with no request: src/devops_cli/roadmap/plan_read.py:724:`def tree_files(source: Path, rev: str, *, operation: str) -> list[str]:` and src/devops_cli/roadmap/plan_read.py:726:`listing = git(source, "ls-tree", "-r", "--name-only", "-z", rev, operation=operation)`.
- The `read_file` call of `tests/support/roadmap_refine.py:def _answer_refine_git` showed the clone and its git answers: tests/support/roadmap_refine.py:148:`if "ls-tree" in argv:` answers the tree read, tests/support/roadmap_refine.py:165:`(repo / "CONTEXT.md").write_text(` writes a tracked file, and tests/support/roadmap_refine.py:171:`(repo / "src" / "sample.py").write_text(` writes a real file of the clone.
- The `read_file` call of `tests/support/roadmap_stage.py:def stage_repo` showed the files that the stage clone writes, and `CONTEXT.md` is the first: tests/support/roadmap_stage.py:181:`"CONTEXT.md": "# Context`.
- The `read_file` call of `tests/roadmap/stage/test_roadmap_stage_rejected.py:def test_a_commit_that_changed_a_file_the_reason_names_ends_the_hold` showed the constant and the two cases: tests/roadmap/stage/test_roadmap_stage_rejected.py:62:`EVIDENCE = (` names a path that the clone of `tests/support/roadmap_stage.py` does not write, and the record case at tests/roadmap/stage/test_roadmap_stage_rejected.py:def test_a_rejected_plan_returns_the_item_to_new_and_records_the_rejection expects that path, so the plan moves both to `CONTEXT.md`; the hold case at tests/roadmap/stage/test_roadmap_stage_rejected.py:def test_a_commit_that_changed_a_file_the_reason_names_ends_the_hold seeds the commits of that path.
- The `read_file` call of `tests/roadmap/refine/test_roadmap_refine_person_wait.py:def test_the_check_of_a_wait_text_reads_at_most_the_bound_of_issues_and_of_paths` showed the bound case, whose paths the clone does not hold and whose bound is tests/roadmap/refine/test_roadmap_refine_person_wait.py:167:`bound = constants.CONST_ROADMAP_REFINE_MAX_WAIT_CHECKS`, so a call with no tree keeps that case as it is.
- The `read_spec` calls of `roadmap-refine/waits` and `roadmap-stage/returns` gave 18 requirement names each, and none holds the seven names that the delta adds, so each added name is new to its capability.
- `tree_files` needs a checkout of the repository as a precondition, and the round gives it one at src/devops_cli/roadmap/plan_read.py:724:`def tree_files(source: Path, rev: str, *, operation: str) -> list[str]:`.
- `inspect_checkout` needs a checkout of the repository as a precondition: src/devops_cli/roadmap/refine/refine.py:3875:`sha = inspect_checkout(source_path, repo)`.
- `explain_item` needs a checkout of the repository as a precondition: src/devops_cli/roadmap/explain.py:285:`checkout = Path(source)`.
- `_rejections` needs a checkout of the repository as a precondition: src/devops_cli/roadmap/stage/stage.py:3091:`def _rejections(`.
- No call of the plan needs a client of a service or a network: the tree read is one local `git ls-tree`.
- The plan adds no command and no verify program of its own: each `verify` is `uv run devops ci test` with a test path, or `uv run devops ci docs`, whose failure classes are `test` and `lint`. The plan runs `git`, `python` and `uv` only, all three are in the runner image, and the pod settings (`readOnlyRootFilesystem: true`, `capabilities.drop: ALL`) change nothing.
- The filter reads the tree at run time and holds no list of dotted tokens, so the plan claims no member of a set and needs no census.
- The first check against the real system reproduces the premise: `uv run python -c "from devops_cli.roadmap.refine.refine import text_paths; print(text_paths('Edit AGENTS.md and 0.202 today.'))"`; the next checks are the failing cases `uv run devops ci test tests/roadmap/refine/test_roadmap_refine_person_wait.py` and `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_rejected.py`.
- The plan reads `CONST_ROADMAP_REFINE_MAX_WAIT_CHECKS` and changes no line of `src/devops_cli/config/constants.py`, the file that open pull request #6524 changes.
- The live proof of the last criterion is no step of this plan: only a round of the Service after the release writes the new record value on #4671 (not checked).

## Existing Tool Considered

No open tool extracts repository paths from prose: pathvalidate checks the form of a path and dulwich reads a git tree, and neither knows this repository's tree, so the alternatives check of the issue records that no tool covers the need. The change builds about 40 lines of Python around `git ls-tree` through `tree_files`: about 3,000 tokens to build, keep and fix, and about 1 hour of elapsed time. It deletes no internal code.

## Dependencies

- PR #6524 changes `src/devops_cli/config/constants.py`, the file that holds `CONST_ROADMAP_REFINE_MAX_WAIT_CHECKS`; this plan reads that constant and changes no line of the file, so rebase the branch after #6524 merges.
