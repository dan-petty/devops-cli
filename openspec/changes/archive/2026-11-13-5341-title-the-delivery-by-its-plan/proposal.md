# Proposal: #5341

## Why

The implement job copies the summary of the issue title into the title of the delivery pull request, and the squash commit and the changelog line take that title (#5341). An issue title often states a goal, and the plan often states a smaller change. For #3785 the issue title is `fix(k8s): find the source of the <gpu-node> host crashes`, but #5336 only removes a profiler exclusion. Its squash commit and its changelog line say that the change found the source of the crashes. The plan of each item already has a short summary of the change: the stage job writes it in the title of the plan pull request, `docs(openspec): plan #<issue> <summary>`.

## What Changes

- Add `plan_summary` to `src/devops_cli/roadmap/stage/stage_change.py`, beside `staging_title`: it reads the summary of the plan of an item from the subject of the commit that adds its change folder. It removes the end `(#<pull>)` that GitHub adds to a squash commit. It gives None for a subject that is no plan title of the item.
- Give `delivery_title` an optional `summary`, the summary of the plan. The title keeps the type and the declared scope of the issue title. With no `summary`, the title keeps the summary of the issue title.
- Add `_plan_summary` to `src/devops_cli/roadmap/implement/implement_run.py`: one `git log -1 --diff-filter=A` on `HEAD` for `openspec/changes/<issue>-*/proposal.md`. On a staged branch that commit is the commit of the stage job. On the default branch it is the squash commit of the plan pull request.
- `_delivery_title` uses the summary of the plan when the form accepts the title. Else it uses the summary of the issue title, and a title that the form refuses still stops the item. The body keeps `Closes #<issue>`.
- Add tests with the real issue titles and plan subjects of #5336, #5324, #5355 and #4980, and tests of a Staged item, a Planned item and a plan summary that the form refuses.
- Update `docs/roadmap/implement.md`, step 6.
- The change carries a spec delta: the title of the delivery pull request is behavior that a person and release-please observe.
- The type of the title stays the type of the issue. #4127 asks also for a type from the changed paths. This change does not do that part, and it does not close #4127.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-implement-job/pull-request`: The pull request that delivers the code has the type of the issue, The summary of the delivery title comes from the plan

## Impact

- Code: `src/devops_cli/roadmap/stage/stage_change.py`, `src/devops_cli/roadmap/implement/implement_run.py`
- Documents: `docs/roadmap/implement.md`
- Tests: `tests/roadmap/stage/test_roadmap_stage_title.py`, `tests/roadmap/implement/test_roadmap_implement_job.py`, `tests/support/roadmap_implement.py`
- Release: the implement job runs in the runner image, and `release.yml` builds that image only when release-please makes a release. The fix takes effect after the next release.

## Feasibility

- `git show origin/main:src/devops_cli/roadmap/implement/implement_run.py` at `f299667c9`: `_delivery_title` calls `delivery_title(self.target.item.title, declared)`, and `delivery_title` in `stage_change.py` keeps `issue_title.partition(":")[2]` as the summary. The job reads no part of the plan for the title.
- `devops gh api repos/dan-petty/devops-cli/pulls/<n>` for #5336, #5324, #5355 and #4980: each title is the title of its issue (#3785, #4697, #5107 with the undeclared scope `tools` removed, and #2530).
- `git log --diff-filter=A --format=%s origin/main -- openspec/changes/<change>/proposal.md` gives the plan titles: `docs(openspec): plan #3785 Remove the profiler exclusion of the <gpu-node> node (#5182)`, `docs(openspec): plan #4697 Keep one metric stream for each workload (#5283)` and `docs(openspec): plan #5107 Read the OpenSpec version on PATH in the check (#5333)`. The first commit of #4980 is the stage commit `docs(openspec): plan #2530 Fix readiness files and merged monitor output`. Each summary states the change, and the stage schema limits it to 47 characters, under the 60 of the title.
- Later commits change the folder and do not add it: the plan fix `docs(openspec): plan #3785 name the renamed profiler test (#5310)` changes `proposal.md`, so `--diff-filter=A` skips it. The step `fix-plan` writes the plan as one new commit with the plan title (`src/devops_cli/roadmap/steps/fix_plan.py`, `_push`).
- The first "What Changes" bullet is no usable title: for #3785 it has 169 characters, over the limit of 60. So the job uses the summary of the plan title, which the issue calls the summary of the plan.
- A miss of `git log -1 --diff-filter=A` with the path glob takes about 2.5 s on the 1,657 commits of `origin/main`, and a hit takes 0.14 s. The job calls it at most twice in a run.
- `.github/workflows/release.yml`: the job `runner-image` runs only `if: needs.release-please.outputs.release_created == 'true'`, so a merge alone does not change the runner Jobs.

## Existing Tool Considered

- No tool reads the summary of a plan from the project's own plan title. `devops roadmap retitle` already reads a plan summary from the title of the plan pull request (`retitle._plan_title`), through `stage.pr` and a GitHub request. The implement job cannot use that source: on a Staged item the plan pull request becomes the delivery pull request, so after the first title write it holds no plan title.
- commitizen (MIT) checks and writes Conventional Commit messages, but it does not read an OpenSpec plan or a squash subject.
- Cost to build: about 40,000 tokens to write and test, about 2,000 tokens a year to keep, 1 hour of elapsed time. The change deletes no internal code: `delivery_title` stays and gets one optional argument.
