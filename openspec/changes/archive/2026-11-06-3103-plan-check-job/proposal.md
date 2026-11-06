# Proposal

## Why

A pull request that the roadmap Service opens can merge in minutes, and nothing in CI looks at a plan before it merges (#3103). The Service made 34 plan pull requests with defects out of 37 on 2026-11-01. The command `devops roadmap plan-check` finds the form defects of a plan with no model, but nobody runs it on each plan.

The first design of #3103 was a commit status `service-vetted`, set by the independent review and required by a ruleset. It cannot be built (see Feasibility). This change keeps the part that can be built: a CI job that runs `devops roadmap plan-check` on each plan pull request of the Service and shows the result in its check run.

## What Changes

- Add the job `plan-check` (name `Plan Check`) to `.github/workflows/pr-title.yml`. It needs `semantic-title`, it uses `always()` so that a failed title check still reaches it, and it holds the permissions `checks`, `contents` and `pull-requests`, all read. It runs `devops roadmap plan-check`.
- The condition of the job selects a pull request whose author is `devops-cli-service[bot]` and whose title starts with `docs(openspec): plan #`. Any other pull request skips the job, and a skipped job reports Success.
- Add invariant tests in `tests/invariants/test_workflow_contracts.py` for the needs, the condition, the permissions and the steps of the job.
- Document the job in `docs/roadmap/plan-check.md` and `docs/ROADMAP_WORKFLOW.md`.
- The job is advisory. It is not the independent review, and it posts no `service-vetted` status. A person makes it a required check (ADR 0014).
- The change alters no command, option or message, so it has no spec delta and sets `skip_specs: true`.
- This change fits one pull request.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
None.

## Impact

- `.github/workflows/pr-title.yml`: one new job.
- `tests/invariants/test_workflow_contracts.py`: tests for the job.
- `docs/roadmap/plan-check.md`, `docs/ROADMAP_WORKFLOW.md`: the job.
- No code under `src/` changes.

## Feasibility

- No review workflow exists. The directory `.github/workflows` holds `ci`, `cleanup-devcontainer`, `clear-status`, `codeql`, `copilot-setup-steps`, `defect-pr-hardening-audit`, `fail-to-pass`, `pr-title` and `release`. The name `service-vetted` appears only in an archived proposal. The independent review runs outside this repository, so no check here can read its verdict. For this reason the gate `service-vetted` is dropped.
- The command exists: `devops roadmap plan-check` (`src/devops_cli/commands/roadmap.py`) and the checks in `src/devops_cli/roadmap/plan_check.py`. It reads the check run named `Semantic PR title` (`SEMANTIC_TITLE_CHECK`) and reports a problem when it is missing or has not passed. So the job runs after `semantic-title` and, with `always()`, also after a failed one.
- The login of the bot comes from a real plan pull request of the Service. The pull request API for #3261 (title `docs(openspec): plan #3201 add a plan-check command for a plan pull request`) gives the user `devops-cli-service[bot]` with the type `Bot`. That is `<slug>[bot]` for the slug `devops-cli-service` of the Service App (`k8s/devops/configmap.example.yaml`, ADR 0015). The event field `github.event.pull_request.user.login` holds the same value. A test holds the login in the condition equal to the login that the settings give for that slug.
- The title prefix is the form that the stage job gives: `staging_title` in `src/devops_cli/roadmap/stage_change.py`. A test builds a title with it and runs the condition on it.
- A job that its condition skips reports Success. The header of `.github/workflows/fail-to-pass.yml` records this, and the GitHub documentation says the same. A test evaluates the condition for the plan of the Service and for six other pull requests.
- The job needs only read permissions. It reads check runs, the head commit through `refs/pull/<number>/head`, and the pull request. The issue that the plan names is public, so no `issues` permission is needed. The Service App token has no `statuses` permission (`src/devops_cli/github/check_verdict.py`), which is one more reason to post no status.
- Who makes `Plan Check` a required check: a person, under ADR 0014, because only a person changes the ruleset of the repository. Recommendation: make it required after the plan reader gives no false alarm. Until then it stays advisory.

## Existing Tool Considered

- GitHub Actions and the existing command `devops roadmap plan-check` cover the job. No new library is needed.
- palantir/policy-bot (Apache-2.0, maintained) covers a blocking gate: it posts a status that a ruleset can require, selects a pull request by author and title, and resets on a push. It lacks the review itself: it only consumes an approval from a configured user or team, and it does not run `plan-check`. A person must write its policy file and add the check to the ruleset. So it is not part of this change. Where the independent review runs, and whether a gate reads its verdict, is a decision for a person and for #2867.
- Code that the change deletes: none.
