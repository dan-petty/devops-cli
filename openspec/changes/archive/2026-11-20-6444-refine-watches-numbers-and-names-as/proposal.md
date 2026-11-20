# Proposal

## Why

Refine records the paths of a person wait in `refine.wait_refs`, and `text_paths` takes every dotted token of the wait text as a path (#6444). A decimal, a version, a dotted setting, a Python name or a domain then fills one of the 5 slots of `CONST_ROADMAP_REFINE_MAX_WAIT_CHECKS`, so a real file that the text names later is not watched and a change of that file ends no wait. Each false path also costs one GitHub commits read in each round that checks the wait, and the hold of a rejected plan reads the same extractor, so it has the same defect.

## What Changes

- `text_paths` keeps a candidate only when `tracked_paths`, the set of files that its caller gives, holds it as a file or as a directory that holds a tracked file. A call that gives no set keeps every candidate.
- `text_paths` applies `CONST_ROADMAP_REFINE_MAX_WAIT_CHECKS` after the filter, so the first five real paths take the slots.
- `_CITED_PATH_RE` accepts a period or a comma after a path, so a file that ends a sentence is a candidate. Its trailing boundary is a lookahead, so the space after one path can start the next path: `text_paths('Read a.py b.py c.py d.py')` gives the four paths, and not only `a.py` and `c.py`.
- `plan_refine` reads the tracked paths once with `tree_files` at the commit of the round and gives the set to the selection. It imports `tree_files` inside the function, because `plan_read` imports `stage_change`, which imports `refine`.
- `_select_round`, `_Selection`, `_still_waiting`, `_wait_state`, `_wait_refs`, `select_candidates` and `refine_left_out` take the keyword `tracked_paths`, which defaults to None, as `frames` and `graph` already do. The name is not `tree`: `DependencyGraph.tree` is an `ItemTree` (#6450), and `_still_waiting` holds a local `tree` of that type.
- A record of `refine.wait_refs` that holds a path that `tracked_paths` lacks is not current. The round reads the comments of the item once, with no model call, and writes the filtered references. The wait check also removes each recorded path that `tracked_paths` lacks before it reads commits. So a record that a round wrote before this change loses its false values in the first round after the release, and a false value costs no commits read in that round.
- `explain_item` reads the tracked paths with `tree_files` at `origin/<default>`, which `read_planned_changes` fetched, and gives them to `_refine_verdict` and to `refine_left_out`, so `devops roadmap explain` uses the tree of the default branch, as a round of the Service does.
- `ClosedPlan.rejection` takes the tracked paths of the default branch and gives them to `text_paths`, so the record of a rejected plan holds no decimal, version, dotted setting or domain.
- `_rejections` reads the tracked paths once with `tree_files` at `origin/<default>`, the ref that the module already fetched for the planned changes.
- The dry runs of `devops roadmap stage` and `devops roadmap explain` list the new read of the tracked paths of the default branch.
- The stage hold test cites `CONTEXT.md`, which its clone writes, and seeds the commits of the hold case on that file.
- The git fake of the refine tests answers the read of the whole tree (`ls-tree -r --name-only -z <sha>`) with the files of the clone.
- A value that the tree does not hold never reaches `refine.wait_refs` or `path_changed_at`, so the wait check reads no commits for it.
- Trade-off: a file that the tree of the round does not hold ends no wait. So a file that a later commit creates, or that a commit deleted after the record, no longer ends a wait. A person who expects such a file replies in a comment, which ends the wait.
- `docs/roadmap/refine.md` states that a wait records only the paths that the tree of the round holds, that the five slots go to the first five real paths, that a record with a false path is read again once, and the trade-off. `docs/roadmap/stage.md` states that the record of a rejected plan holds only the files that the default branch holds.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-refine/waits`: MODIFIED A wait on a person ends when a cause that its text names ends, A read of the comments of a waiting item is recorded, An unchanged waiting item costs no comment read; ADDED A wait records only the paths that the tree holds, The five-path cap counts only the paths that the tree holds, A path that a period or a comma follows is kept, Each path of a run of paths is kept, A value that the tree does not hold costs no commits read, A record that holds a path that the tree lacks is read again, A directory that the tree holds is a watched path, The explain verdict reads the tree of the default branch, A file that the tree of the round does not hold ends no wait
- `roadmap-stage/returns`: A rejected plan's hold keeps only the paths that the tree holds

## Impact

- Code: `src/devops_cli/roadmap/refine/refine.py`, `src/devops_cli/roadmap/explain.py`, `src/devops_cli/roadmap/stage/stage_rejected.py`, `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/roadmap/request_plan.py`, `src/devops_cli/lang/en/messages.py`
- Documents: `docs/roadmap/refine.md`, `docs/roadmap/stage.md`, `docs/ROADMAP_WORKFLOW.md`
- Tests: `tests/roadmap/refine/test_roadmap_refine_person_wait.py`, `tests/roadmap/refine/test_roadmap_refine_recorded_wait.py`, `tests/roadmap/stage/test_roadmap_stage_rejected.py`, `tests/roadmap/test_roadmap_explain.py`, `tests/roadmap/test_roadmap_dry_runs.py`, `tests/support/roadmap_refine.py`

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
- The `search_code` call for `select_candidates(` lists the refine reader at src/devops_cli/roadmap/refine/refine.py:3127:`def select_candidates(` and the test modules that call it, so the keyword `tracked_paths` defaults to None and no test module changes.
- The `search_code` call for `candidates, waiting, queue = _select_round(` lists one place only, src/devops_cli/roadmap/refine/refine.py:3880:`candidates, waiting, queue = _select_round(`, so the round is the one production caller of the selection.
- The `search_code` call for `def refine_left_out` lists the definition at src/devops_cli/roadmap/refine/refine.py:3079:`def refine_left_out(store: RoadmapStore, item: Item) -> str | None:`, and the `read_file` call of `src/devops_cli/roadmap/explain.py:def _refine_verdict` showed its one production call, so the new keyword breaks no caller.
- The tree read is one local git call with no request: src/devops_cli/roadmap/plan_read.py:724:`def tree_files(source: Path, rev: str, *, operation: str) -> list[str]:` and src/devops_cli/roadmap/plan_read.py:726:`listing = git(source, "ls-tree", "-r", "--name-only", "-z", rev, operation=operation)`.
- The `read_file` call of `tests/support/roadmap_refine.py:def _answer_refine_git` showed the clone and its git answers: tests/support/roadmap_refine.py:148:`if "ls-tree" in argv:` answers the tree read, tests/support/roadmap_refine.py:165:`(repo / "CONTEXT.md").write_text(` writes a tracked file, and tests/support/roadmap_refine.py:171:`(repo / "src" / "sample.py").write_text(` writes a real file of the clone.
- The `read_file` call of `tests/support/roadmap_stage.py:def stage_repo` showed the files that the stage clone writes, and `CONTEXT.md` is the first: tests/support/roadmap_stage.py:181:`"CONTEXT.md": "# Context`.
- The `read_file` call of `tests/roadmap/stage/test_roadmap_stage_rejected.py:def test_a_commit_that_changed_a_file_the_reason_names_ends_the_hold` showed the constant and the two cases: tests/roadmap/stage/test_roadmap_stage_rejected.py:62:`EVIDENCE = (` names a path that the clone of `tests/support/roadmap_stage.py` does not write, and the record case at tests/roadmap/stage/test_roadmap_stage_rejected.py:def test_a_rejected_plan_returns_the_item_to_new_and_records_the_rejection expects that path, so the plan moves both to `CONTEXT.md`; the hold case at tests/roadmap/stage/test_roadmap_stage_rejected.py:def test_a_commit_that_changed_a_file_the_reason_names_ends_the_hold seeds the commits of that path.
- The `read_file` call of `tests/roadmap/refine/test_roadmap_refine_person_wait.py:def test_the_check_of_a_wait_text_reads_at_most_the_bound_of_issues_and_of_paths` showed the bound case, whose paths the clone does not hold and whose bound is tests/roadmap/refine/test_roadmap_refine_person_wait.py:167:`bound = constants.CONST_ROADMAP_REFINE_MAX_WAIT_CHECKS`, so a call with no tree keeps that case as it is.
- The `read_spec` calls of `roadmap-refine/waits` and `roadmap-stage/returns` gave 18 requirement names each, and none holds the seven names that the delta adds, so each added name is new to its capability.
- A top-level import of `tree_files` in `refine.py` makes an import cycle: src/devops_cli/roadmap/plan_read.py:55:`from devops_cli.roadmap.stage.stage_change import (` and src/devops_cli/roadmap/stage/stage_change.py:69:`from devops_cli.roadmap.refine.refine import sanitize_text`. So `plan_refine` imports it inside the function, as `stage.py` imports its late reads.
- After #6450, `_still_waiting` holds a local `tree` of another type: src/devops_cli/roadmap/refine/refine.py:2902:`tree = graph.tree if graph is not None else ItemTree(store.items)`, the field src/devops_cli/roadmap/refine/refine.py:1439:`tree: ItemTree = field(default_factory=ItemTree, compare=False, repr=False)`. A keyword `tree` of a set of paths gives `_wait_state` that `ItemTree` after a blocked wait, so the keyword is `tracked_paths`.
- The record is reused while the count of comments is the recorded one: src/devops_cli/roadmap/refine/refine.py:`def _recorded_reads` returns `record.get(RefineRecordKey.WAIT_REFS)` when `record.get(RefineRecordKey.COMMENTS_SEEN) == str(item.comments)`, and `_named_cause_ended` reads each recorded path. So a filter of the extractor alone leaves the records that a round wrote before this change.
- The trailing boundary of `_CITED_PATH_RE` consumes the separator: `uv run python -c "from devops_cli.roadmap.refine.refine import text_paths; print(text_paths('Read a.py b.py c.py d.py'))"` printed `['a.py', 'c.py']` at the staging commit.
- `tree_files` needs a checkout of the repository as a precondition, and the round gives it one at src/devops_cli/roadmap/plan_read.py:724:`def tree_files(source: Path, rev: str, *, operation: str) -> list[str]:`.
- `inspect_checkout` needs a checkout of the repository as a precondition: src/devops_cli/roadmap/refine/refine.py:3875:`sha = inspect_checkout(source_path, repo)`.
- `explain_item` needs a checkout of the repository as a precondition: src/devops_cli/roadmap/explain.py:285:`checkout = Path(source)`.
- `_rejections` needs a checkout of the repository as a precondition: src/devops_cli/roadmap/stage/stage.py:3091:`def _rejections(`.
- No call of the plan needs a client of a service or a network: the tree read is one local `git ls-tree`.
- The plan adds no command and no verify program of its own: each `verify` is `uv run devops ci test` with a test path, or `uv run devops ci docs`, whose failure classes are `test` and `lint`. The plan runs `git`, `python` and `uv` only, all three are in the runner image, and the pod settings (`readOnlyRootFilesystem: true`, `capabilities.drop: ALL`) change nothing.
- The filter reads the tree at run time and holds no list of dotted tokens, so the plan claims no member of a set and needs no census.
- The first check against the real system reproduces the premise: `uv run python -c "from devops_cli.roadmap.refine.refine import text_paths; print(text_paths('Edit AGENTS.md and 0.202 today.'))"`; the next checks are the failing cases `uv run devops ci test tests/roadmap/refine/test_roadmap_refine_person_wait.py` and `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_rejected.py`.
- The plan reads `CONST_ROADMAP_REFINE_MAX_WAIT_CHECKS` and changes no line of `src/devops_cli/config/constants.py`, the file that open pull request #6524 changes.
- A read-only count on the open items at origin/main (12446 tracked files, 799 open items) found 266 records with `refine.wait_refs`. 63 of them hold a value that the tree lacks (147 values), and 21 of those are person waits whose count of comments is the recorded one, so `_recorded_reads` keeps them until a new comment comes. Examples: #6365 records `v3.16.0,1.27.3,1.26.11,1.27.4,v0.62.0` and #4750 records `4.53,4.52,4.48,4.51,1.0.44` (5 of 5 false), and #4671 records `0.202,0.453` after three real files.
- The one `stage.rejected` record of the open items holds no path that the tree lacks, so the stage hold needs no change for the records that it wrote before.
- The live proof of the last criterion is no step of this plan: only a round of the Service after the release writes the new record value on #4671 (not checked).

## Existing Tool Considered

No open tool extracts repository paths from prose: pathvalidate checks the form of a path and dulwich reads a git tree, and neither knows this repository's tree, so the alternatives check of the issue records that no tool covers the need. The change builds about 40 lines of Python around `git ls-tree` through `tree_files`: about 3,000 tokens to build, keep and fix, and about 1 hour of elapsed time. It deletes no internal code.

## Dependencies

- PR #6524 changes `src/devops_cli/config/constants.py`, the file that holds `CONST_ROADMAP_REFINE_MAX_WAIT_CHECKS`; this plan reads that constant and changes no line of the file, so rebase the branch after #6524 merges.
