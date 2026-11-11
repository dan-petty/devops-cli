# Proposal: #4508

## Why
Closes #4508. A Ready item whose title has a type that `CONST_BRANCH_TYPES` does not list waits for ever. The stage job leaves it out ("The title has no Conventional Commit type"), the retitle job selects only titles with a listed type, and intake returns early from its summary check. Three items in the managed repositories wait this way: dotfiles #1, homelab #1 and homelab #2, each with a title `security(<scope>): ...`. No job comments, so nobody acts.

## What Changes
- `commit_title.py` reads a title type that `CONST_BRANCH_TYPES` does not list (`unlisted_type`) and gives its correction (`corrected_title`). The one correction is in `CONST_ROADMAP_TITLE_TYPE_CORRECTIONS`: `security(<scope>): <summary>` becomes `fix(security): <summary>`.
- The retitle job selects an open item with an unlisted type, also when its summary is short (`retitle_items`, which replaces `long_title_items`). It writes the corrected title with no model call. When the corrected summary is too long, it shortens it in the same round; when that fails, it writes the corrected type with the old summary, and a later round shortens it.
- An unlisted type with no correction, or a person's title with an unlisted type, gets one comment that names the type, the types and the correction, and the skip mark. Each skip of the job writes one log line with a reason key (`invalid-title-type` or `long-title`). The skip mark makes the line come once.
- Intake refuses a new candidate with an unlisted type (`NewCandidate.refuse_title`, which replaces `refuse_long_summary`). The message names the type, the types and the correction.
- The stage reason for a title with no listed type names `devops roadmap retitle`.

The retitle command, its messages and the intake refusal are observable, so the change has a spec delta.

## Capabilities
- `roadmap-retitle`: ADDED requirements for the type correction, the comment on a type with no correction, the log line of a skip, and the intake refusal.

## Impact
- The next retitle round of the Service writes `fix(security): ...` on dotfiles #1, homelab #1 and homelab #2, and the stage row of the same round can take them.
- No new branch type: `CONTRIBUTING.md` (Naming) and `release-please-config.json` list the same eleven types, and neither has `security`.
- No setting, metric or manifest changes. Fits one pull request.

## Feasibility
- `uv run python -c "from devops_cli.roadmap.commit_title import commit_type; print(repr(commit_type('security(ssh): verify node host keys')))"` printed `None` on origin/main (devops-cli 0.111.0).
- `devops roadmap explain 1` for the dotfiles repository printed "Stage job: no. The title has no Conventional Commit type, so the branch has no type."
- The `changelog-sections` of `release-please-config.json` are feat, fix, perf, refactor, revert, docs, test, build, ci, style and chore. `CONTRIBUTING.md` (Naming) lists the same types. So `security` cannot become a type, and `fix(security)` is the standard form: a fix with the scope `security`, which gives the label `scope/security` (#2768).

## Existing Tool Considered
No maintained Python package reads the Conventional Commit head of an issue title and maps a type to the list of one project: commitizen and python-semantic-release parse commit messages with their own type lists, and pulling either in for one regular expression adds a dependency tree. The change extends the parser that `commit_title.py` already holds. Cost: about 25,000 tokens to build, about 1,000 tokens a month to keep, and half a day. The change deletes `long_title_items` and `refuse_long_summary`, which the new names replace.
