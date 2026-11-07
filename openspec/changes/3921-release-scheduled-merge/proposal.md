# Proposal

## Why

Issue #3921: a person merges the release pull request that release-please opens, except for an urgent fix (#1966). Merged work stays unreleased until then, and the images of the cluster do not move. On 2026-11-07 the owner asked: "I also want to enable automerge release please pull requests every 6 hours."

## What Changes

- A new workflow `.github/workflows/release-merge.yml` runs on `cron: "0 */6 * * *"` and on `workflow_dispatch`. It has one job, one concurrency group, and read-only `GITHUB_TOKEN` permissions (`contents`, `pull-requests`, `checks`).
- A new module `devops_cli.release.merge_candidate` reads the open pull requests with the label `autorelease: pending` and picks the first one, by number, that passes every guard. It prints `number=` and `sha=` on standard output for `$GITHUB_OUTPUT`, and it prints the reason of each refusal on standard error. It writes nothing to GitHub. The workflow runs it with `uv run --locked --no-dev python -m devops_cli.release.merge_candidate`, as the image build runs `devops_cli.roadmap.runner_tools`. No `devops` command is added.
- The guards: the pull request is open and not a draft; the release App opened it from a `release-please--branches--main` branch of this repository into `main`; it has `autorelease: pending` and not `hold-release`; its title is `chore(main): release <version>` with a version that `packaging` parses; it changes only `.release-please-manifest.json`, `CHANGELOG.md`, `pyproject.toml` and `uv.lock`, and adds, removes and renames none of them; every check that the ruleset of `main` requires passed on its head; no other check failed on its head; no required check failed on the head of `main`; GitHub reports it as mergeable.
- The next step of the workflow squash-merges the picked commit with `gh pr merge --squash --match-head-commit <sha>` and the release App token. A mint step gives the token only `contents: write` and `pull-requests: write`, and only that step gets it. The pick step gets `GITHUB_TOKEN`.
- `.github/labels.yml` declares `hold-release`. `RELEASE_CYCLE.md` states the schedule, the guards, how to hold a release and how to turn the schedule off. `AGENTS.md` names the release pull request as the one exception to "only a person merges pull requests", in one sentence that points to `RELEASE_CYCLE.md`. The file is at its cap of 6,500 characters, so the sentence "It holds the rules for every task and sends each kind of task to the document that owns it." goes from the header, because the table "Where to look" says the same. ADR 0013 records the amendment. `ARCHITECTURE.md`, `CONTEXT.md`, `docs/ROADMAP_WORKFLOW.md`, `docs/ROUTINE_TASKS.md`, `docs/SDLC.md`, `k8s/README.md` and the GitHub CLI page of the knowledge base no longer say that only a person merges it.
- The workflow is observable to the person who releases, and the guards are logic that a consumer relies on, so the change carries a spec delta: the new capability `release-scheduled-merge`.
- This change fits one pull request.

## Capabilities

### New Capabilities

- `release-scheduled-merge`: when the release pull request merges by itself on a schedule, which guards it must pass, and with which token.

## Impact

- `.github/workflows/release-merge.yml`, `.github/workflows/release.yml` (one comment), `.github/labels.yml`.
- `src/devops_cli/release/`, `src/devops_cli/lang/en/messages.py`, `tests/release/`, `tests/invariants/test_workflow_contracts.py`, `tests/commands/test_ci.py`.
- `RELEASE_CYCLE.md`, `AGENTS.md`, `ARCHITECTURE.md`, `CONTEXT.md`, `docs/ROADMAP_WORKFLOW.md`, `docs/ROUTINE_TASKS.md`, `docs/SDLC.md`, `docs/adr/0013-releases-use-release-please-as-it-ships-and-agents-stay-out.md`, `k8s/README.md`, `src/devops_cli/ai/knowledge_base/it_domains/tools/github_cli.md`.
- Consequence for the cluster: each merge makes a release, each release builds the service, runner and DevContainer images, and Argo CD Image Updater moves the cluster onto them. The schedule allows up to 4 releases a day.

## Feasibility

All facts below were read on 2026-11-07 with `devops gh api` (read only) and against the open release pull request.

- **The ruleset of `main`** (`repos/dan-petty/devops-cli/rulesets`, one active ruleset, no bypass actor): `required_approving_review_count: 0`, `allowed_merge_methods: ["squash"]`, required checks `Static Analysis`, `Tests & Coverage` and `Semantic PR title`, strict up-to-date off, plus code scanning, code quality and code coverage rules. `branches/main/protection` answers 404: `main` has no classic protection. So the merge needs no approval, and the release App needs no bypass. The monitor line that says an approval is required does not come from the ruleset.
- **Repository settings:** `allow_auto_merge: true`, `allow_squash_merge: true`, merge commits and rebase off, `squash_merge_commit_title: PR_TITLE`, `squash_merge_commit_message: PR_BODY`. The merge step passes no title or message, so the squash commit keeps the settings.
- **The release App can merge:** `release.yml` already runs `gh pr merge --auto --squash` with its token (#1966), and the token holds `contents`, `issues` and `pull-requests` write. The merge step asks for `contents: write` and `pull-requests: write`, a subset. The `release` environment has a branch policy for `main` only, and a scheduled run uses the default branch, so the job can use the environment secrets. No new secret, variable or App permission is needed.
- **The release pull request** (number 3888 on 2026-11-07): author `dan-petty-release[bot]` (type `Bot`; the output `app-slug` of `actions/create-github-app-token` v3.3.0, read from the pinned SHA, gives `dan-petty-release`), label `autorelease: pending`, branch `release-please--branches--main--components--devops-cli`, title `chore(main): release 0.77.0`, not a draft, files `.release-please-manifest.json`, `CHANGELOG.md`, `pyproject.toml` and `uv.lock` (all `modified`), `mergeable: true` with state `unstable`. `release-please-config.json` names `uv.lock` as its one extra file, and a test compares the guard with it.
- **Run against the real repository:** `python -m devops_cli.release.merge_candidate --repo dan-petty/devops-cli --app-login 'dan-petty-release[bot]'` with a read-only token, with runtime dependencies only (`uv run --locked --no-dev`). It refused pull request 3888 because the checks `Service Image` and `Runner Image` failed on its head, and passed every other guard.
- **Why a failed check that no rule requires also refuses:** the jobs `service-image` and `runner-image` of `release.yml` run the same Trivy scan as those checks. A merge with a failing scan tags a version and publishes no image. The owner asked for the required checks; this guard is stricter on purpose, and a person can still merge by hand.
- **`--match-head-commit`** (`gh pr merge`): the merge fails when the head moved after the pick. release-please rewrites the pull request on each push to `main` (`always-update: true`), so this keeps GitHub from merging a commit that the guards did not judge.
- **What only a person changes:** nothing, for the merge to work. Two steps belong to a person: `devops gh labels sync` after the merge, so `hold-release` exists in the repository, and the first scheduled run (or **Run workflow**) to confirm that the merge starts the `Release` run.

## Existing Tool Considered

GitHub auto-merge (`gh pr merge --auto --squash`, already used for an urgent fix) merges when the checks pass, at once and with no schedule, no check of files and no label. Renovate's `automerge` merges only its own pull requests. A third-party release-please auto-merge action would hold the release App token and fix the guards in code that this project does not own, so it is rejected. The change builds a small guard module on the open tools that exist (`packaging` for the version, the GitHub session and `read_check_runs` of devops-cli for the reads, `gh pr merge` for the merge, `actions/create-github-app-token` for the token).

Cost to build, keep and fix, written as AGENTS.md rule 3 asks: about 150,000 tokens to build (module, 43 tests, workflow, 11 documents) and about 2 hours elapsed; keeping it costs a few thousand tokens a year, because the guards read the ruleset and the release configuration and so follow them; a fix is one guard in one function with a test. It deletes no code.
