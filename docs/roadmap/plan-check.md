# The plan check

`devops roadmap plan-check <pull-request>` checks a plan pull request that already exists. It is
step 3 of [the roadmap workflow](../ROADMAP_WORKFLOW.md). It reads the change folder at the head of
the pull request, runs the gates of the stage job with no model, and checks the pull request
itself.

## What it reads

The command runs in a checkout of the repository. It fetches `refs/pull/<number>/head` and reads
the change folder of that commit. The folder is the one named `<issue>-<slug>`, where `<issue>` is
the issue in the `Plans #<issue>` line of the body. A pull request with no such folder, or with
more than one, is a problem.

The GitHub client gives the title, the body, the base and the check runs. The command reads the
issue that the body plans, for its acceptance criteria and for the text of the item that the size
measure counts. The command takes the body of the issue with no record block of the jobs, as the
stage job reads it. It builds no model client.

To measure the groups, the command makes a detached worktree of the head commit in a temporary
folder and removes it when the measure ends. The files that the tasks name are the files of the head
commit, whatever the working tree of the checkout holds.

## What it checks

- The stage gates: `check_proposal` and `validate_change`. The command reports each problem with
  the file and the words of the stage job.
- The read: the reader reports each change file that it cannot read, each task group that the
  model refuses, each criterion that the model refuses (such as `Group 0`) and each
  `Verification:` command that the implement step cannot run, as a `read` problem. It never ends in a traceback.
- The size of each task group (#3499): the command measures each group with `measure_groups`, the
  function of the stage job, on the tracked files of the head commit. The item and the files of the
  change folder are the shared text, as in the stage job. It reports a `group-over-budget` problem
  for a group above the setting `roadmap.stage.step_tokens`, and a `group-no-files` problem for a
  group that changes a file that exists and packs no file, because no code span in its tasks names
  one. A group that only creates files packs none by nature, and the command accepts it. The plan
  holds no estimate of the lines of a created file, so the command counts one line for each. For a
  group that creates files, its figure is lower than the stage figure by 32 tokens for each
  estimated line above the first. For any other group, the two figures are equal.
- The title: `docs(openspec): plan #<issue> <summary>`, with at most `SUMMARY_MAX_CHARS`
  characters after the colon.
- The body: at most `BODY_MAX_CHARS` characters, one `Plans #<issue>` line, and no closing keyword
  before an issue reference.
- The check `Semantic PR title`: it must exist and it must pass.
- A `MODIFIED` requirement whose text in the base spec changed, or went, since the plan commit.

## The job in CI

The job `Plan Check` of the workflow `.github/workflows/pr-title.yml` runs the command for each plan
pull request of the Service. Its condition selects a pull request that the bot of the Service App
opened (`service.github_app.bot_login`), whose title starts with `docs(openspec): plan #`, and whose
body starts with the line `Plans #<issue>`. The condition reads the author of the pull request, not
the actor of the event. It reads the body too, because the implement job changes the body of the
plan pull request to the delivery form, `Closes #<issue>`, when it marks the pull request ready, and
a delivery pull request can keep a title of the plan form (#3958). A job that its condition skips
reports Success, so the pull requests of a person, of another bot, of the release and of a delivery
pass.

The job needs `Semantic PR title` and runs after it, also when it failed, because the command then
reports that check as a problem. The job holds the permissions `checks`, `contents` and
`pull-requests`, all read. It posts no status and makes no review. A new push gives a new run.

The job is advisory. It shows form problems of the plan in its check run. It is not the independent
review of the Service pull request, which runs outside this repository, and its pass does not mean
that the plan is vetted. Only a person can make `Plan Check` a required check, in the ruleset of
`main` ([ADR 0014](../adr/0014-required-checks-gate-the-merge-and-the-pre-push-hook-runs-the-fast-static-checks.md)).
Make it required after the plan reader gives no false alarm.

## Output and exit code

The command prints one line for each problem, with the path, the rule and the message. It prints
nothing when the plan has no problem. It exits 1 when it finds one problem or more, and 0 when it
finds none.

| Option | What it does |
| :--- | :--- |
| `--repo <owner/name>` | The repository. Without it, the origin of the checkout. |
| `--json` | Print a JSON array of objects with `path`, `rule` and `message`. |
| `--dry-run` | Make no request: print the reads that a run makes, with placeholders. |

## A new gate gives its result

A plan or a pull request that adds a gate to the stage job gives two results before it merges:

- The refusals of the gate over the merged plans. Run [plan-recheck](plan-recheck.md) in the checkout
  of the branch: `uv run devops roadmap plan-recheck --source . --branch HEAD`. The new gate has its
  own name in `ProposalGate`, so the report lists its refusals under that name, for the branch and
  for the default branch. A person marks each refusal as a hit or as a false refusal. A refusal on a
  merged plan is a case to review, and no tool proves it false.
- A replay of the defect that the gate cites. `uv run devops roadmap eval stage --replay` shows that
  the gate catches the defect.

`plan-recheck` judges less than the stage job: it gives the gates no premise probe, no open pull
request, no recorded search and no plan of another open item, and it measures no group. A gate that
needs one of these has no hits in `plan-recheck`. [The plan-recheck page](plan-recheck.md) lists
the rest.

## Where the rules are

[roadmap-plan-check](../../openspec/specs/roadmap-plan-check/spec.md) holds the requirements.
[The stage job page](stage.md) tells what the gates check at stage time.
