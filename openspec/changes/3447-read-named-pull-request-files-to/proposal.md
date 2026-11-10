# Proposal: #3447

## Why

The verification pass of the stage job accepts a claim about an earlier pull request without reading that pull request. #3410 is the evidence. Its body says that the plan of #3372 in pull request #3378 chose `! git grep -n -F devops_cli.roadmap.stage src/ tests/` as the whole-prefix check for a move of the `stage*` modules. Pull request #3378 holds no move group. Its plan adds the move-prefix check to `src/devops_cli/roadmap/stage/stage_move.py`, and its tests use the literal as a case. The refine job published the claim, and the plan of #3435 repeated it. The stage review made no tool call and did not catch it.

## What Changes

- The stage verification request gains the key `pull_requests`. Each entry holds the number of one pull request that the issue or the plan names, its `merge_commit`, and the text of each path the pull request changes at that commit.
- `src/devops_cli/roadmap/stage/stage_verify_pulls.py` reads the number of each named pull request from the phrases `pull request #` and `PR #`, reads the merge commit of the pull request with the GitHub session, and reads the changed files at that commit with one `git diff` and one `git show` for each file.
- The reader holds at most `CONST_ROADMAP_STAGE_VERIFY_MAX_FILES` files over all named pull requests and cuts each file to `CONST_ROADMAP_STAGE_VERIFY_FILE_MAX_TOKENS` tokens. It masks each secret. A pull request with no merge commit, and a read of GitHub that fails, add no entry and never stop the item.
- A file under `openspec/changes/` comes first, then a path that the claim names, then the other changed files.
- `VerificationInput.payload`, `.request_texts` and `.contains` in `src/devops_cli/roadmap/stage/stage_verify.py` hold the pull request files, so a `false_premise` finding that quotes one returns the plan to the planner and is open.
- The prompt `src/devops_cli/ai/tasks/roadmap_stage_verify.md` names `pull_requests`, its `number`, its `merge_commit` and its path to text map, and tells the model to check a claim about an earlier pull request against those files.
- `PullStatus` in `src/devops_cli/github/client.py` holds `merge_commit_sha`, which is empty for a pull request with no merge commit.
- The change has a spec delta, because the stage job reads a new input and reports a new kind of evidence to a person.
- The change fits one pull request.

The plan asks for a new `premise_failed` key of the planner reply, which returned the item when the issue body made the claim. That key no longer exists: #3478 removed the return path and the stage reply holds no key to report a false premise (`src/devops_cli/roadmap/stage/stage_change.py:637`). This change keeps the removal and reports a body claim through the verification finding, which returns the plan. A plan that still claims a fact that the pull request contradicts goes back to the planner, and the planner states an unbuildable issue in `feasibility` and plans no code that compensates for it, as `src/devops_cli/ai/tasks/roadmap_stage_change.md` says.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage`: the verification pass reads the files of each named pull request at its merge commit, and a quote from one of those files returns the plan.

## Impact

- Code: `src/devops_cli/roadmap/stage/stage_verify.py`, `src/devops_cli/roadmap/stage/stage_verify_pulls.py`, `src/devops_cli/roadmap/stage/stage_overlap.py`, `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/github/client.py`, `src/devops_cli/ai/tasks/roadmap_stage_verify.md`
- Tests: `tests/roadmap/stage/test_roadmap_stage_verify_pulls.py`, `tests/roadmap/stage/test_roadmap_stage_verify.py`
- GitHub: one GET for the status of each named pull request, on the client that the job already uses.

## Feasibility

- The premise holds in the code. `VerificationInput.of` reads only the cited files of the checkout (`src/devops_cli/roadmap/stage/stage_verify.py:def of`), and `_input_of` passes no pull request file (`src/devops_cli/roadmap/stage/stage.py:def _input_of`). The payload holds the keys `number`, `title`, `body`, `plan` and `files` and no other key (`src/devops_cli/roadmap/stage/stage_verify.py:def payload`).
- The named pull request of the #3410 case is merged, so GitHub gives its `merge_commit_sha`, and its merge commit is in the history of the fetched default branch. The reader reads that commit with the git commands of the process, as `stage_probe.py` reads the staging commit.
- The removed `premise_failed` path is confirmed in the source: "The reply has no key to report a false premise: an issue that cannot be built as written is" (`src/devops_cli/roadmap/stage/stage_change.py:637:The reply has no key to report a false premise: an issue that cannot be built as written is`).
- The first check of the implementation against the real system is `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_verify_pulls.py`, which reads a real merge commit of a test repository.
- The second check is `uv run devops openspec check`, which validates the added requirements and their scenarios.

## Existing Tool Considered

The stage probe already reads a commit with `git cat-file`, `git grep` and `git log` (`src/devops_cli/roadmap/stage/stage_probe.py`). It does not read the changed files of a named pull request at its merge commit, so this change extends the same read-only git path and adds no tool. It deletes no code. The written cost is about 5,000 tokens to build, keep and fix, and about 1 hour.

## Dependencies

None.
