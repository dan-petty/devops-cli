# Design

## Decisions

### The input holds a separate `pull_requests` key

The verification request gains `pull_requests`, a list of entries with `number`, `merge_commit` and `files`. A repository file and a pull request file stay apart, so a path stays exact and the model can tell where a quote comes from. A single merged `files` map would collide on a path and hide the pull request that the claim names.

### The reader takes only the `pull request #` and `PR #` phrases

A bare `#` is an issue, a commit or a cross-link. The reader matches `pull request #` and `PR #` with no regard to case, reads each number once in first-seen order, and drops a number below 1 or above 999999. The input is built before the model call, so the model chooses no number.

### GitHub gives the merge commit and git gives the text

The reader asks `get_pull_status` for the merge commit of each named pull request, then reads the changed paths of that commit against its first parent with one `git diff`, and the text of each path with one `git show`. The merge commit is the exact tree of the merged pull request. A GitHub request for each file would need one request per path and would give no tree of the merge commit, and a local merge ref can be absent for another merge method.

### A failed read adds no entry

A pull request with no merge commit, a checkout that holds no such commit, and a GitHub read that raises `GitHubOperationError` add no entry. The verification pass then runs on the input it has. A failed read is no reason to stop the item.

### The bound is one count over all named pull requests

The reader holds at most `CONST_ROADMAP_STAGE_VERIFY_MAX_FILES` files over all named pull requests, and cuts each file to `CONST_ROADMAP_STAGE_VERIFY_FILE_MAX_TOKENS` tokens. A plan folder path comes first, then a path that the claim names, then the other changed files. The plan of a named plan pull request is therefore in the input, and a claim about it can be checked.

### A quote from a pull request file is a quote from the request

`VerificationInput.request_texts` yields the text of each pull request file, so `contains` accepts a quote from one. A `false_premise` finding with such a quote returns the plan and is open. The existing finding types and the existing return path stay, so the nine-type schema and the golden set change not at all.

### The item-level return stays removed

The plan asked the planner to reply with `premise_failed` and return the item. #3478 removed that path on purpose: a filler reply returned many items to New, and the stage reply now has no key for a false premise. The change keeps that rule. A body claim that a named pull request contradicts is reported as a `false_premise` finding that returns the plan, and the planner states an unbuildable issue in `feasibility` and plans no code that compensates for it.

## Rejected alternatives

### Merge the pull request files into `files` with a prefix

A path such as `openspec/changes/3372-a-move/tasks.md` can also be a repository path, so a prefix collides and the model cannot tell the two apart.

### Read only the paths that the claim names

A plan file that the claim does not cite can contradict the claim. The #3410 case quotes a literal that the claim names, but the move group that is absent sits in a task that the claim does not cite.

### Let the model choose the pull request numbers

The input must be built before the model call, and a test must show the same numbers on each run. A model call to choose them adds a round that can fail and gives no stable input.

### A new defect type for a pull request claim

A new type changes the nine-type schema, the prompt, the golden set and the eval. `false_premise` already returns the plan and holds a quote rule, so the claim needs no new type.

### Read a GitHub file for each changed path

A GitHub contents read needs one request for each file and gives no tree of the merge commit. The git read of the merge commit gives each file and stays in one checkout.
