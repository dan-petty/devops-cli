# Design

## Decisions

- **Keep a candidate path only when the tree of the commit that the round reads holds it, as a file or as a directory that holds a tracked path.**: A decimal, a version, a dotted setting, a Python name and a domain use the same characters as a file name, so no pattern tells them apart. Tree membership does, and the project already drops a cited path that a commit does not hold.
- **Read the tree once for each round with `tree_files` of the checkout and give the set to the wait path reader.**: It is one local `git ls-tree`, which makes no GitHub request, and the round already holds the commit from `inspect_checkout`.
- **Apply `CONST_ROADMAP_REFINE_MAX_WAIT_CHECKS` after the tree filter.**: The documented limit counts the files that a round reads, so the first five real paths take the slots.
- **Add a period and a comma to the trailing boundary of `_CITED_PATH_RE` and keep the path group as it is.**: The pattern then accepts a path that ends a sentence, and the group still gives the path without the punctuation.
- **Give the keyword `tree` to `_select_round`, `_Selection`, `_still_waiting`, `_wait_state`, `_wait_refs`, `select_candidates` and `refine_left_out`, defaulting to None, and read None as no filter.**: `select_candidates` and `refine_left_out` hold no clone of their own, and the test modules that call them with no clone keep their result, as the bound case of `tests/roadmap/refine/test_roadmap_refine_person_wait.py` does.
- **Pass the tree at every production caller: the round in `plan_refine`, the explain verdict in `explain_item`, and the stage hold in `_rejections`.**: The three callers hold a checkout, so no production path reaches the extractor with no tree, and the defect that the issue reports stays out of the Service.
- **Read the tree of the clone's `HEAD` in `explain_item` and give it to `_refine_verdict` and to `refine_left_out`.**: `devops roadmap explain` must give the answer that a round gives (#3483), and it already holds the clone that it reads the heads and the plans from.
- **Give `rejection` of `ClosedPlan` the tree of the default branch, and read that tree in `_rejections` from the ref that the module already fetched for the planned changes.**: That is the branch whose commits the wait check reads, the stage round already fetched it, and one shared extractor keeps the two callers from drifting apart.
- **Filter the candidate before the round writes `refine.wait_refs`.**: The record stays right, and a value that the tree does not hold never reaches `path_changed_at`, so it costs no commits read.
- **Move the cited path of the stage hold test to `CONTEXT.md`, which the clone of `tests/support/roadmap_stage.py` writes, and seed the commits of the hold case on that file.**: The clone writes `CONTEXT.md` as a tracked file, so the record of that case keeps one path under the tree filter and the commit that the reason names ends the hold.

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

## Unchanged references

- `tests/roadmap/refine/test_roadmap_refine_authors.py` (call with no tree): The keyword `tree` defaults to None, which keeps the candidates as they are today, so this call gives the same verdict.
- `tests/roadmap/refine/test_roadmap_refine_failure_class.py` (call with no tree): The keyword `tree` defaults to None, so these calls read no tree and keep their result.
- `tests/roadmap/refine/test_roadmap_refine_selection.py` (call with no tree): The keyword `tree` defaults to None, so the calls of this module keep their result.
- `tests/roadmap/refine/test_roadmap_refine_title_type.py` (call with no tree): The keyword `tree` defaults to None, so this call keeps its result.
- `tests/roadmap/test_roadmap_trust.py` (call with no tree): The keyword `tree` defaults to None, so these two calls keep their result.
