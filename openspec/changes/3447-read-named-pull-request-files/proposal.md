# Proposal

## Why

The stage verification pass reads the issue, the plan and the files of the repository that the plan cites. It never reads a pull request or a plan that the issue or a plan line names. #3410 is the evidence. Its body says that "the plan of #3372 in pull request #3378 chose `! git grep -n -F devops_cli.roadmap.stage src/ tests/` as the whole-prefix check for a move of the `stage*` modules". Pull request #3378 holds no move group. Its plan adds the check to `src/devops_cli/roadmap/stage_move.py`, and its test uses the literal as a case. The refine job published the claim in the proposed design, and the plan of #3435 repeated it in Feasibility. The stage review made no read of the pull request, so it did not catch it. A plan can therefore open a draft on a premise that the named pull request contradicts (#3447).

## What Changes

- The verification input holds the changed files of each pull request that the issue body or a plan text names, read at the merge commit of that pull request (`src/devops_cli/roadmap/stage/stage_pull_files.py`, `src/devops_cli/roadmap/stage/stage_verify.py`).
- Only the phrase `pull request #` or `PR #` names a pull request. A bare `#` is an issue reference and reads nothing.
- A pull request that is not merged, or that cannot be read, gives no entry. The pass still runs, and the read never stops the plan.
- A quote from a named pull request file is a text of the request, so a `false_premise` finding with that quote is open.
- The read is bounded: at most `CONST_ROADMAP_STAGE_VERIFY_MAX_FILES` files, each cut to `CONST_ROADMAP_STAGE_VERIFY_FILE_MAX_TOKENS` tokens, the OpenSpec change folder first.
- The prompt `src/devops_cli/ai/tasks/roadmap_stage_verify.md` names the `pull_requests` key and tells the model to check a claim against its files.
- `PullRequest` in `src/devops_cli/github/client.py` gains `merged` and `merge_commit_sha`, so one REST read gives the merge commit of a named pull request.
- The `roadmap-stage/verification` capability gains the requirements of the read. The stage job reports a new input to the verifier, so it carries a delta.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage/verification`: A named pull request is read at its merge commit

## Impact

- Code: `src/devops_cli/roadmap/stage/stage_pull_files.py` (new), `src/devops_cli/roadmap/stage/stage_verify.py`, `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/roadmap/stage/stage_overlap.py`, `src/devops_cli/github/client.py`
- Prompts: `src/devops_cli/ai/tasks/roadmap_stage_verify.md`
- Tests: `tests/roadmap/stage/test_roadmap_stage_verify.py`, `tests/roadmap/stage/test_roadmap_stage_pull_files.py` (new), `tests/github/test_github_client.py`

## Feasibility

- The premise holds in the code at the staging commit. `VerificationInput` in `src/devops_cli/roadmap/stage/stage_verify.py` holds the issue, the plan and the cited files of the repository only, and `payload` sends those keys. No key holds the files of a pull request that the issue or the plan names.
- The read reuses code that exists. `GitHubClient.get_pull` reads one pull request (`src/devops_cli/github/client.py:498`), the `git` wrapper of `src/devops_cli/roadmap/clone_git.py:24` runs `git fetch` and `git show`, and `cited_files` and `_read` already cut a file to `CONST_ROADMAP_STAGE_VERIFY_FILE_MAX_TOKENS` tokens.
- The stage job holds the client and the clone that the read needs: `_Planner` gets `pull_reads` (`session_pull_reads`) and `pull_repo` (`src/devops_cli/roadmap/stage/stage.py:3324`), and `_input_of` already reads the cited files from `self._source`.
- The probes confirm that the two cited test modules and the prompt are files of the staging commit: `tests/roadmap/stage/test_roadmap_stage_verify.py`, `tests/roadmap/stage/test_roadmap_stage_pull_files.py` is new, and `src/devops_cli/ai/tasks/roadmap_stage_verify.md`.
- The recorded plan of #3378 at merge commit `6c15a64a614941629669a181e3220ae8bc7e27d0` is the archived change `openspec/changes/archive/2026-11-04-3372-the-stage-plan-of-a-module/`. It adds `move_prefix_problems` to `src/devops_cli/roadmap/stage_move.py` and holds no move group, so the regression case reads that folder and not the eval fixture `tests/fixtures/roadmap_eval/stage/3372-the-stage-plan-of-a-module/plan.json`, which holds a move group.
- The first check of the implementation against the real system is `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_verify.py tests/roadmap/stage/test_roadmap_stage_pull_files.py`, which runs the new cases beside the existing ones.
- The second check is `uv run devops openspec check`, which validates the added requirements and their scenarios.

## Existing Tool Considered

No open, maintained tool or library covers the read of the changed files of a pull request at its merge commit with the file and token bound of this project. `gidgethub` (the client of the session, `docs/adr/0006-github-session-requests-go-through-gidgethub.md`) gives the pull request and its merge commit, and the `git` wrapper of `src/devops_cli/roadmap/clone_git.py` gives a commit's tree. Neither gives the path-to-text map at the merge commit, the file and token bound, or the `false_premise` finding. `cli/cli` gives pull request metadata and a diff, not the merge-commit tree, and `guardrails-ai` checks the schema of a model answer and holds no repository evidence. The change adds that integration in-repo and no new dependency. It deletes no code. The written cost is about 5,000 tokens to build, keep and fix the code, and about 1 hour.

## Dependencies

None.
