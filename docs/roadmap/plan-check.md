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
measure counts. It builds no model client.

To measure the groups, the command makes a detached worktree of the head commit in a temporary
folder and removes it when the measure ends. The files that the tasks name are the files of the head
commit, whatever the working tree of the checkout holds.

## What it checks

- The stage gates: `check_proposal` and `validate_change`. The command reports each problem with
  the file and the words of the stage job.
- The read: the reader reports each change file that it cannot read, each task group that the
  model refuses and each `Verification:` command that the implement step cannot run, as a `read`
  problem. It never ends in a traceback.
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

## Output and exit code

The command prints one line for each problem, with the path, the rule and the message. It prints
nothing when the plan has no problem. It exits 1 when it finds one problem or more, and 0 when it
finds none.

| Option | What it does |
| :--- | :--- |
| `--repo <owner/name>` | The repository. Without it, the origin of the checkout. |
| `--json` | Print a JSON array of objects with `path`, `rule` and `message`. |
| `--dry-run` | Make no request: print the reads that a run makes, with placeholders. |

## Where the rules are

[roadmap-plan-check](../../openspec/specs/roadmap-plan-check/spec.md) holds the requirements.
[The stage job page](stage.md) tells what the gates check at stage time.
