# Design

## Decisions

- **Keep a candidate path only when the tree of the commit that the round reads holds it, as a file or as a directory that holds a tracked path.**: A decimal, a version, a dotted setting, a Python name and a domain use the same characters as a file name, so no pattern tells them apart. Tree membership does, and the project already drops a cited path that a commit does not hold.
- **Read the tree once for each round with `tree_files` of the checkout and give the set to the wait path reader.**: It is one local `git ls-tree`, which makes no GitHub request, and the round already holds the commit from `inspect_checkout`.
- **Apply `CONST_ROADMAP_REFINE_MAX_WAIT_CHECKS` after the tree filter.**: The documented limit counts the files that a round reads, so the first five real paths take the slots.
- **Add a period and a comma to the trailing boundary of `_CITED_PATH_RE`, make that boundary a lookahead, and keep the path group as it is.**: The pattern then accepts a path that ends a sentence, and the group still gives the path without the punctuation. The lookahead leaves the space after a path to the next match, which uses it as its leading boundary, so `Read a.py b.py c.py d.py` gives four paths and not `a.py` and `c.py` alone.
- **Give the keyword `tracked_paths` to `_select_round`, `_Selection`, `_still_waiting`, `_wait_state`, `_wait_refs`, `select_candidates` and `refine_left_out`, defaulting to None, and read None as no filter.**: `select_candidates` and `refine_left_out` hold no clone of their own, and the test modules that call them with no clone keep their result, as the bound case of `tests/roadmap/refine/test_roadmap_refine_person_wait.py` does.
- **Name the keyword `tracked_paths` and not `tree`.**: `DependencyGraph.tree` is an `ItemTree` (#6450), and the blocked case of `_still_waiting` binds a local `tree` of that type, so a keyword `tree` gives the `ItemTree` to `_wait_state` after a blocked wait.
- **Import `tree_files` inside `plan_refine`.**: `plan_read` imports `stage_change`, which imports `refine`, so a top-level import makes an import cycle.
- **Read a record of `refine.wait_refs` that holds a path that `tracked_paths` lacks as not current.**: `_recorded_reads` reuses the record while the count of comments is the recorded one, so the records that a round wrote before this change keep their false values until a person comments. The round reads the comments of the item once, finds no reply, and writes the filtered references with the marks of the wait. It makes no model call, because the item still waits.
- **Remove each recorded path that `tracked_paths` lacks before `_named_cause_ended` reads commits.**: The round that reads a record again must not read the commits of its false values, and the check holds for each caller that gives a record.
- **Pass the tree at every production caller: the round in `plan_refine`, the explain verdict in `explain_item`, and the stage hold in `_rejections`.**: The three callers hold a checkout, so no production path reaches the extractor with no tree, and the defect that the issue reports stays out of the Service.
- **Read the tree of `origin/<default>` in `explain_item` and give it to `_refine_verdict` and to `refine_left_out`.**: `devops roadmap explain` must give the answer that a round gives (#3483). The round of the Service reads the commit of the default branch, and `read_planned_changes` already fetched `origin/<default>` for explain, while the `HEAD` of a person's clone can be any branch.
- **List the read of the tracked paths of the default branch in the dry runs of stage and explain.**: Each dry run lists the git reads of its command in order, and the new read is one of them.
- **Give `rejection` of `ClosedPlan` the tree of the default branch, and read that tree in `_rejections` from the ref that the module already fetched for the planned changes.**: That is the branch whose commits the wait check reads, the stage round already fetched it, and one shared extractor keeps the two callers from drifting apart.
- **Filter the candidate before the round writes `refine.wait_refs`.**: The record stays right, and a value that the tree does not hold never reaches `path_changed_at`, so it costs no commits read.
- **Move the cited path of the stage hold test to `CONTEXT.md`, which the clone of `tests/support/roadmap_stage.py` writes, and seed the commits of the hold case on that file.**: The clone writes `CONTEXT.md` as a tracked file, so the record of that case keeps one path under the tree filter and the commit that the reason names ends the hold.
- **Answer the read of the whole tree in the git fake of the refine tests with the files of the clone.**: The fake answered `ls-tree -r --name-only -z <sha>` with no file, so the filter removed each path in each `plan_refine` test, and `test_the_round_that_reads_the_comments_of_a_waiting_item_records_what_they_gave` and `test_a_person_wait_whose_text_names_a_path_that_changed_gets_a_new_look_with_no_block_paths` failed.
- **Accept that a file that the tree of the round does not hold ends no wait.**: A value with no file and a file that a later commit creates, or that a commit deleted, look the same to the tree, and only a commits read of each value tells them apart, which is the cost that the issue removes. A person who expects such a file replies in a comment, which ends the wait.

## Rejected alternatives

- **A regex allowlist of known file extensions.**: The false tokens use the same characters as real paths: the record of #4671 holds `0.202` and `0.453` beside `AGENTS.md`, so a fixed set of extensions covers none of them.
- **A new library that parses paths out of prose.**: The alternatives check of the issue records that no tool covers the need: pathvalidate checks the form of a path and dulwich reads a git tree, and neither knows this repository's tree.
- **Test the working tree with `Path.exists()`.**: A file of a local checkout can pass while the default branch lacks it, and a directory of the default branch can be absent from the checkout.
- **Read the GitHub contents API for each candidate.**: It adds one request for each candidate, which is the cost that the issue removes.
- **Apply the five-path cap before the tree check.**: False tokens fill the cap and real files drop out, which is the defect of #6444.
- **Remove the five-path cap.**: The spec and the document set five, and each recorded path costs one commits read in a round.
- **Strip punctuation from a match after the pattern finds it.**: The pattern rejects `src/devops_cli/commands/ai.py.` before any strip runs, because the character after the path is a period.
- **Match all dotted tokens and split them afterwards.**: It adds ambiguity for a real file name that holds a period, and the tree check still decides every token.
- **Filter the candidates inside `path_changed_at`.**: The value already took a slot of the cap and the record of the wait still holds it.
- **Cache the negative reads of `path_changed_at`.**: The first GitHub read still costs and the cap stays full, so the real file that the text names last is still unwatched.
- **A stage-only filter beside the refine one.**: It duplicates the code and the two filters can drift, and both callers take their paths from the same extractor today.
- **Make the tree a required argument of the extractor and of the selection.**: The `search_code` call for `select_candidates(` lists the test modules that call the reader with no clone, so a required argument breaks them and the group would change more than the five files that one step allows.
- **Read a call with no tree as a tree that holds no path.**: The bound case at tests/roadmap/refine/test_roadmap_refine_person_wait.py:160:`paths = [f"src/gone_{index}.py" for index in range(12)]` names twelve paths that the clone does not hold and expects five reads, so the case would fail on its own expectation.
- **Keep the extractor unfiltered for the stage hold and filter only the refine wait.**: Both callers read the same text with the same pattern, so the stage hold would keep `0.202` as a path and the issue would stay open for one of its two defects.

- **Read the recorded references once more with no filter, and write the filtered ones after that round.**: That round still reads the commits of each false value, 52 reads on the 21 person waits that the live count found, and the requirement says that a false value costs no commits read.
- **A command that rewrites the records of the open items once.**: A round already reads the comments and writes the marks of a wait, so the first round after the release rewrites each record for one comments read, and a new command adds code that runs one time.
- **Keep the keyword `tree`.**: After #6450 the blocked case of `_still_waiting` binds `tree` to an `ItemTree`, and mypy refuses the second type of the name.
- **Read the tree of the clone's `HEAD` in explain.**: The `HEAD` of a person's clone can be a topic branch whose files the default branch does not hold, so explain and the round would disagree.

## Unchanged references

- `tests/roadmap/refine/test_roadmap_refine_authors.py` (call with no tree): The keyword `tracked_paths` defaults to None, which keeps the candidates as they are today, so this call gives the same verdict.
- `tests/roadmap/refine/test_roadmap_refine_failure_class.py` (call with no tree): The keyword `tracked_paths` defaults to None, so these calls read no tree and keep their result.
- `tests/roadmap/refine/test_roadmap_refine_selection.py` (call with no tree): The keyword `tracked_paths` defaults to None, so the calls of this module keep their result.
- `tests/roadmap/refine/test_roadmap_refine_title_type.py` (call with no tree): The keyword `tracked_paths` defaults to None, so this call keeps its result.
- `tests/roadmap/test_roadmap_trust.py` (call with no tree): The keyword `tracked_paths` defaults to None, so these two calls keep their result.
