# Design

## Decisions

- **Keep the default tree in the judge.** `plan_implement` builds one `_Judge` for each run. A field of the judge lives for one run and is gone after it. The code of #3393 keeps the base facts in the judge the same way (`_base_facts`). A test counts the reads of one run without a hook in the readers.
- **List the default tree with `_default_files`.** `_default_files` is a `cached_property` of the judge. The first plan check that needs the tree reads it. Every later check of the run reuses it. A run with no item to check lists nothing. A read that fails is not kept. The next item tries it again and gets its own reason, as it does before this change.
- **Pick the tree of a revision with `_tree`.** The revision `origin/<default>` gets the kept list. Any other revision gets a listing for that item. The branch of a Staged item is its own, so it is the case of any other revision. One method keeps the choice in one place. The check cannot hand a Staged item the tree of the default branch.
- **Give `specs_at` an optional `files` argument.** `specs_at` lists the tree of its revision to find the spec files. The base facts would list the default tree a second time. With the list given, the run uses one `git ls-tree` for the tree and one `git show` for each spec file. `plan_check` and `plan_recheck` keep the call that lists for itself.
- **Count the git commands at the process edge in the test.** The job tests run git for real behind the fake process runner. `programs.calls` records each command. The count shows that the real readers run one time.

## Rejected alternatives

- **Read the default tree and the base specs in `plan_implement`, and pass them to `_Judge`.** `_plan_reason` catches `GitOperationError` for each item. It leaves that item out with the reason, and the run goes on after a failed read. A read in `plan_implement` runs before any item. A failure there ends the whole run. A run with no plan to check also pays for the read. The test `test_a_default_tree_that_git_cannot_list_leaves_each_planned_item_out_and_ends_no_run` holds the first behavior.
- **Cache the readers in `plan_read.py`, by revision or with `functools.lru_cache`.** The revision `origin/main` is the name of a ref that a fetch moves. A cache keyed by that name outlives the run. It returns the old tree after the next fetch. A cache in the reader also hides the read from the caller. A test cannot then count the reads of one run.
- **Keep every revision that a run reads.** Each Staged branch is read for one item in a run. A cache of branches saves no read. It adds a key and a lifetime for no gain.
- **Count the reads with a spy on `tree_files` in the test.** The spy replaces the reader under test. The test would not show that the real reader runs one time. The count of git commands at the process edge shows it.
