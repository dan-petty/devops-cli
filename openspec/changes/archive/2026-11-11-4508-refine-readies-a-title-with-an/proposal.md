# Proposal: #4508

## Why
Closes #4508. A Ready item whose title has a type that `CONST_BRANCH_TYPES` does not list waits for ever. The stage job leaves it out ("The title has no Conventional Commit type"), the retitle job selects only titles with a listed type, and refine sets such an item Ready with no check of the type. Three items in the managed repositories wait this way: dotfiles #1, homelab #1 and homelab #2, each with a title `security(<scope>): ...`. No job comments, so nobody acts.

## What Changes
- `commit_title.py` reads a title type that `CONST_BRANCH_TYPES` does not list (`unlisted_type`) and gives its correction (`corrected_title`). The one correction is in the table `_TITLE_TYPE_CORRECTIONS` of the same module: `security(<scope>): <summary>` becomes `fix(security): <summary>`.
- The retitle job selects an open item with an unlisted type, also when its summary is short (`retitle_items`, which replaces `long_title_items`). It writes the corrected title with no model call. When the corrected summary is too long, it shortens it in the same round; when that fails, it writes the corrected type with the old summary, and a later round shortens it.
- An unlisted type with no correction, or a person's title with an unlisted type, gets one comment that names the type, the types and the correction, and the skip mark. Each skip of the job writes one log line with a reason key (`invalid-title-type` or `long-title`). The skip mark makes the line come once.
- Refine does not refine an item with an unlisted type, also with `--item`, and makes no model call for it, so the item does not become Ready. The report and `devops roadmap explain` give the type and `invalid-title-type`. The first round after a title with a listed type refines the item.
- The reason of the stage job and the implement job for an unlisted type names the type and `devops roadmap retitle`, with the corrected title when the type has a correction (`unlisted_type_reason`). A title with no type keeps its reason, which does not name the retitle job.
- Intake keeps its early return: it does not refuse a new candidate for an unlisted type, because the retitle job corrects it.

The retitle command, the refine selection and the stage reason are observable, so the change has spec deltas.

## Capabilities
- `roadmap-retitle`: ADDED requirements for the type correction, the comment on a type with no correction, the log line of a skip, the intake that keeps the candidate and the stage reason. MODIFIED "Confirmed repair keeps type and scope", which now holds for a listed type only.
- `roadmap-refine`: ADDED "Refine leaves an item with an unlisted title type". MODIFIED "A round leaves an item from an account without write access to a person", because `--item` does not refine an item with an unlisted type.

## Impact
- The next retitle round of the Service writes `fix(security): ...` on dotfiles #1, homelab #1 and homelab #2, and the stage row of the same round can take them.
- A new item with an unlisted type stays New until its title has a listed type.
- No new branch type: `CONTRIBUTING.md` (Naming) and `release-please-config.json` list the same eleven types, and neither has `security`.
- No setting, metric or manifest changes. Fits one pull request.

## Feasibility
- `uv run python -c "from devops_cli.roadmap.commit_title import commit_type; print(repr(commit_type('security(ssh): verify node host keys')))"` printed `None` on origin/main (devops-cli 0.111.0).
- `devops roadmap explain 1` for the dotfiles repository printed "Stage job: no. The title has no Conventional Commit type, so the branch has no type."
- The `changelog-sections` of `release-please-config.json` are feat, fix, perf, refactor, revert, docs, test, build, ci, style and chore. `CONTRIBUTING.md` (Naming) lists the same types. So `security` cannot become a type, and `fix(security)` is the standard form: a fix with the scope `security`, which gives the label `scope/security` (#2768).
- Three acceptance criteria of #4508 are not built as written:
  - "Retitle leaves no invalid title type" (`foo(bar): do work` gets a listed type) cannot be built as written. The requirement "A person's edit is kept" of `roadmap-retitle` says that the job MUST NOT change a title that a person changed after the last job comment, and the job knows that only after it selects the item. No rule gives a listed type for an unknown type: the label `type/infra` comes from `perf`, `build` and `ci` (`CONST_ROADMAP_COMMIT_TYPE_LABELS`), and #4508 itself rejects a type that a model chooses ("Refine is model-driven and may invent a type"). So the job comments once and a person edits the title, and refine does not set the item Ready until then.
  - "Refine comments the refusal": the retitle job writes that comment. In each round of the Service, the retitle row runs after the refine row (`MODEL_LANE_ROWS` of `src/devops_cli/roadmap/run.py`) and selects each open item with an unlisted type. Its one comment names the type, the types and `fix(security): <summary>`. A refine comment would be a second comment on the same cause in the same round. Refine gives its reason in the report and in `devops roadmap explain`.
  - "Stage records the left-out reason": #4521 (PR #4541) added the reason of each left-out rule to the log line and the metric of the stage job, with the kind `title_type` for this rule. This change does not build it a second time. The text of that reason now names the unlisted type.

## Existing Tool Considered
No maintained Python package reads the Conventional Commit head of an issue title and maps a type to the list of one project: commitizen and python-semantic-release parse commit messages with their own type lists, and pulling either in for one regular expression adds a dependency tree. The change extends the parser that `commit_title.py` already holds. Cost: about 40,000 tokens to build, about 1,000 tokens a month to keep, and one day. The change deletes `long_title_items`, which `retitle_items` replaces.
