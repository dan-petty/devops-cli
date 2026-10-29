# Proposal

## Why

Issue #2714. A person merged the draft pull request that the stage job opened for #2656 (pull request 2697). The squash commit on `main` is `676d505e`, "fix: report a clear error for a merge-key unset (#2697)". It holds only the plan files of the change `openspec/changes/2656-devops-config-unset-stops-with-a/`, and no code. Three faults follow.

1. The plan ships as a fix. The stage job gives its pull request the type of the issue. release-please reads the squash commit and lists the plan under Bug Fixes in the release pull request, although no fix is in the release. CONTRIBUTING.md, section 5, says that only the first five types add a changelog line, so a plan-only pull request has the type `docs(openspec)`.
2. Stage stages the item a second time. The held-issue rule sees a branch of `origin` only. The branch is deleted after the merge, so the item is free, and a second run writes the same change folder in a second pull request.
3. Implement cannot use the merged plan. It takes an item only when its staged branch is on `origin`. The item stays Ready, with a plan on `main`, and nothing implements it.

The cause is that the roadmap jobs know one place for a plan: the staged branch. A plan can also be on the default branch, because a person can merge the staging pull request at any time.

## What Changes

- Stage leaves out an item whose change folder `openspec/changes/<issue>-*` is on `origin/<default branch>`, with the reason "Its plan is on <default branch>". It also leaves out an item whose change is archived there (`openspec/changes/archive/<date>-<issue>-*`), because that work is done. A round reads the two directories of the tree of `origin/<default branch>` once, with `git ls-tree`, and matches an item by the issue number only. A read that fails fails the run with the reason of git, and stages no item.
- The staging pull request has the title `docs(openspec): plan #<issue> <summary>`. Its squash commit has the same type. The summary is shortened so that the part after the colon has at most 60 characters. The branch keeps the type of the issue. The reply of the model no longer holds a `scope`, because the scope of the title is always `openspec`.
- The pull request that delivers the code has the type of the issue. A Staged item reuses the staging pull request, so the implement job sets its title to the title of the issue. A Planned item gets a new pull request with that title.
- Implement takes a Planned item as well as a Staged one. A Planned item is open, Ready, opened by a trusted author, not stopped and not held, and its change folder is on `origin/<default branch>`. The job makes the branch `<type>/<issue>-<slug>` at `origin/<default branch>`, with the slug of the change folder. It runs the groups with an unticked task, regenerates the documentation, archives, pushes, opens a draft pull request, sets the body `Closes #<issue>`, watches the checks, runs one fix step, and marks the pull request ready. A Planned item whose tasks are all ticked is left out. A Staged item whose branch is on `origin` takes the Staged path, as before.
- The job record gets `implement.branch`. A retry of a Planned item then finds its pushed branch and its open draft, and takes the branch over.
- `CONTEXT.md` gets the term "Planned". `k8s/README.md` and `docs/ROUTINE_TASKS.md` say that the jobs take a Planned item. The generated documents are regenerated.
- A consumer observes the pull request title, the plan of both commands and the records, so the change carries spec deltas on `roadmap-stage` and `roadmap-implement-job`.
- This change fits one pull request. Its task groups follow the urgency: G1, the stage side, comes first.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage`: the plan on the default branch, the title of the staging pull request, and the read of the tree.
- `roadmap-implement-job`: the Planned item, the delivery title, the new record key and the Service round.

## Impact

- `src/devops_cli/roadmap/planned.py` (new), `stage.py`, `stage_change.py`, `implement.py`, `implement_run.py`, `implement_submit.py`, `request_plan.py`, `store.py`.
- `src/devops_cli/github/client.py` (one call sets the title and the body of a pull request), `src/devops_cli/config/constants.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/ai/tasks/roadmap_stage_change.md`.
- `CONTEXT.md`, `k8s/README.md`, `docs/ROUTINE_TASKS.md`, and the documents that `devops docs generate --sync-readme` writes.

## Feasibility

- The case is real and read-only. `git ls-tree --name-only origin/main openspec/changes/` lists `openspec/changes/2656-devops-config-unset-stops-with-a`, and `git ls-remote --heads origin 'fix/2656-*'` lists nothing. So the folder is on the default branch and the staged branch is gone.
- The code paths follow from the source. `stage._Judge._held` calls `issue_holder`, which reads a worktree of the clone and the pushed branches only. `implement._Judge._branch_reason` leaves the item out with "Its staged branch ... is not on origin". The first tests of each group run a fake of that state (a clone with a plan on `main` and no branch) against `plan_stage` and `plan_implement`, and fail on the base for these reasons.
- `git ls-tree --name-only origin/<default> openspec/changes/ openspec/changes/archive/` lists the folders of both directories in one call. The names follow the grammar of `CONST_OPENSPEC_CHANGE_NAME_RE` and the archived grammar of `CONST_OPENSPEC_ARCHIVED_FOLDER_RE`. The archived grammar needs a date first, because the active grammar would read the year as the issue.
- `worktree_add.add_worktree` already creates `<type>/<issue>-<slug>` at the fetched default branch when `origin` has no branch for the issue. A Planned item needs no new git code for the worktree. `GitHubClient.create_draft_pull` already opens a draft.
- A pull request needs at least one commit past its base, so the draft opens after the first commit. The job publishes the branch at its first push, and the pull request follows at once.
- The check `Semantic PR title` matches `^.{1,60}$` against the summary only (`.github/workflows/pr-title.yml`), so `plan #<issue> <summary>` must have at most 60 characters.
- release-please lists only the types `feat`, `fix`, `perf`, `refactor` and `revert` (`release-please-config.json`), so `docs(openspec)` adds no changelog line.

## Existing Tool Considered

`git ls-tree` reads the folders of the tree of the default branch, with no checkout. `add_worktree`, `create_draft_pull`, `parse_task_groups`, `branch_form` and the grammar constants for OpenSpec folders cover the rest. `textwrap.shorten` shortens the summary. release-please and its Conventional Commit types give the changelog rule, and the change builds no tool for it. Nothing new is built except the two checks: the read of the plans on the default branch (about 60 lines) and the Planned path of the implement run (about 80 lines). The cost of the change is estimated at 300k tokens of agent work and one day of elapsed time.

The change deletes the `scope` field of the reply of the stage model and the scope of the staging title. It replaces `update_pull_body` by one call that sets the title and the body.
