# Proposal: #4629

## Why

The stage job writes `openspec/changes/<issue>-<slug>/` in every repository of the Service. 0 of the 6 other repositories hold `openspec/config.yaml`, and none declares an archive step, so nobody archives these folders. On 2026-11-11, 9 draft plan pull requests are open in 3 of these repositories. Their tasks name `uv run devops ci docs` and `uv run devops docs generate`, which cannot run there. Owner decision 1 of 2026-11-11 says that a row in a repository that lacks a project-management dependency starts the onboarding of that repository, and owner decision 3 says that all 6 repositories get OpenSpec through onboarding (#3770). Closes #4629.

## What Changes

- A new helper, `uses_openspec(source, ref)` in `src/devops_cli/openspec/project.py`, is true when commit `ref` holds `openspec/config.yaml`. It reads the commit with one `git ls-tree`, not the files of a checkout. `devops pr create` (#3767) and the archive step of a toolchain preset can use the same helper, so the repository has one switch.
- The stage selection reads the helper once for each round at the staged commit. With no file, it leaves out every item with the new kind `no_openspec` and the reason "The repository has no openspec/config.yaml on <branch>, so the stage job writes no plan for it. Onboarding adds the file (#3770)." `--item` does not overrule the hold. The round writes no branch and calls no model.
- The stage plan holds the missing file in `StagePlan.missing`, and its report prints the reason under the staged commit.
- The stage row of the Service returns the missing file in `JobOutcome.missing`. A later row of the round reads the outcomes of the earlier rows, so this record can start the onboarding of the repository (#4664).
- `devops roadmap explain` prints the reason, because it judges the item through the same selection.
- The dry runs of `stage` and `explain` list the new read.
- A repository whose default branch holds the file, as devops-cli does, gets the same selection, plan and outcome as before.

The hold is a behavior that a consumer observes (a reason in the plan and in `explain`, a new metric reason label, a new field of the row outcome), so the change has a spec delta.

## Capabilities

- `roadmap-project-dependencies` (new): what the roadmap jobs do in a repository that lacks a project-management dependency, and how a row records the missing dependency for onboarding.

## Impact

- In the 6 other repositories, the stage row stops to open plan pull requests. The counter `devops_cli_roadmap_stage_total` counts each held Ready item as `skipped` with the reason `no_openspec`, and the Service logs the reason of each item once.
- Each stage round makes one more local `git ls-tree` in its clone. It makes no GitHub request.
- No setting, command option or manifest changes. The change fits one pull request.
- After the rollout, a person closes the 9 open draft plan pull requests (owner decision 2). The exact steps are in a comment of the pull request.

## Feasibility

- GitHub contents API, read on 2026-11-11 with `devops gh api repos/<owner>/<repo>/contents/openspec/config.yaml`: 404 for vibes, dreamscaper, dotfiles, danielpetty.com, homelab and devcontainer-features, and the file for devops-cli.
- GitHub pulls API, read on 2026-11-11 (`pulls?state=open`, drafts): vibes #173, #174, #175, dreamscaper #15, #16, #17 and dotfiles #6, #7, #8, each titled `docs(openspec): plan #<n> ...`.
- Source: `declared_steps` in `src/devops_cli/roadmap/implement/implement_steps.py` (lines 61-70) reads a project file at a commit with `git ls-tree --name-only <ref> -- <path>`, and gets an empty output when the commit holds no such file. The new helper uses the same read.
- Source: `read_stage_selection` in `src/devops_cli/roadmap/stage/stage.py` is the one selection that `plan_stage` and `explain_item` call, so one check there covers the job and `explain`.
- Source: `JobOutcome` in `src/devops_cli/roadmap/run.py` is the record that a later row of the round reads through `cross_job_predicate` (`_stage_cross_job` reads the outcome of refine).
- Test run: the new round test fails on `origin/main`: the round plans the item and fails on the scripted model reply.

## Existing Tool Considered

OpenSpec defines a project by `openspec/config.yaml`, which `openspec init` writes, and git reads a file at a commit with `git ls-tree`. No other tool is necessary. The change builds a 10-line helper, one selection rule and one outcome field. Cost: about 120,000 tokens and 1.5 hours to build, and no upkeep beyond the rule. The change deletes no internal code: a plan that stays only in the issue body is not built, because it is a second plan system with no user.
