# `devops roadmap consolidate`

The command proposes groups of open items that share a root cause, and writes the proposal to a
local plan. It changes nothing on GitHub. A person reads the plan, and the apply step of #3743 will
act on it.

## What a run does

1. It builds the shortlists of the open items with tools only (`consolidate_shortlist.py`): shared
   paths, shared identifiers, links and the nearest embeddings.
2. It removes what a rule excludes (see below), and asks the judge about each shortlist that no
   earlier plan judged, at most `--limit` of them (default 10).
3. The judge makes two tool-less `chat_structured` calls with the client of
   `ai.for_task("analysis")`: a proposal, then a refutation that sees the proposal and the member
   bodies. The refutation returns `kept`, `weakened` or `dropped`, with reasons.
4. Code checks the answer. A model verdict only flags a group.
5. It writes `.data/roadmap/consolidate/<date>.json` and prints a summary.

## Rules in code

| Rule | Effect |
| :--- | :--- |
| A member or an anchor outside the shortlist | Dropped. A proposal with an unknown shape fails for that shortlist. |
| A cited `#N` or `path:line` that does not exist | Dropped and listed in the group as rejected. A line is checked with `git show <sha>:<path>` at the commit of `--ref`. |
| The status In Progress or In Review | Never a member. An anchor only for a `link-only` group. |
| A milestone | The item is never merged, never made a child and never closed with its anchor. It can be an anchor or a link. No job writes a milestone, so a person set it. |
| A group that is not `kept` | `weakened` makes it `link-only` with the action `link` for each member. `dropped` leaves it out. |
| Members that link to the anchor already | The group is not proposed. |
| A member that a person reopened after a close as a duplicate of the anchor | Not proposed for that anchor again. |
| A declined group | Not proposed until its members change. |

## The plan

Each group has an id (`g<anchor>-<hash of the members>`), a theme, a root cause, an anchor, a shape
(`merge-into-anchor`, `parent-task-with-children`, `close-as-duplicate` or `link-only`), the
consistency gained, the risks and a confidence. Each member has an action (`merge`, `child`,
`link` or `close-when-anchor-merges`), a reason and its evidence.

- `close-when-anchor-merges` stays in `pending_closes` while the anchor is open, and leaves the plan
  when the anchor is closed as completed.
- A group that an earlier plan held too is marked `carried`. A second run over an unchanged board
  has no new group and makes no model call.
- The plan keeps the judgement of each shortlist under a hash of its case. A run saves each
  judgement at once in `<date>.progress.json`. The plan file exists only when the run is done.
- A shortlist whose reply fails the schema is listed under `failures` with the failure class and
  the step `judge`. The run goes on with the next one.

## Options

| Option | Meaning |
| :--- | :--- |
| `--repo`, `-R` | The repository as `owner/name` (default: the origin of this checkout). |
| `--ref` | The commit that cited paths are checked at (default: the default branch of origin). |
| `--limit` | The most shortlists that one run judges with the model. |
| `--dry-run` | Make no request: print the requests of a run. |
| `--decline <group-id>` | Decline a group of the last plan. |
| `--confirm` | Write the decline to the job record of the anchor. It applies to `--decline` only. |

## Failures

- A gateway that does not answer ends the run with no plan, a non-zero exit and a message that
  names the gateway. The progress file keeps the shortlists that were done.
- `--decline` without `--confirm` prints what it would write.

## MCP tool

The MCP tool `roadmap_consolidate` runs the plan path of the command. It publishes `repo`, `ref`,
`limit` and `dry_run` only, so its argv never holds `--decline` or `--confirm`, and it is
read-only. It waits at most 900 s: a run of 10 shortlists takes about 10 minutes. Pass `limit` for
a shorter run. A run that stops keeps its judgements in the progress file.

No row of the Service run starts the job. Item #4687 plans a daily consolidate step in a
CronWorkflow, out of the Service pod.

## The judge

The judge is one function, `ShortlistJudge.judge`, in `src/devops_cli/roadmap/consolidate_judge.py`.
It takes a shortlist and returns a verdict for each member. Another judge can replace the model
judge without a change to the rules in code.
