# Proposal

## Why

Issue #1966: a critical security or bug fix ships only when a person merges the release pull request. On 2026-10-23 the owner asked that such a fix releases without that wait, "as recommended using logical labeling and rules", and lifted the agent restriction on the release files (ADR 0013).

## What Changes

- `release.yml` gets one step after `Run release-please`, in the same job: `Merge the Release Pull Request on an Urgent Fix`. It reads the merged pull request of the pushed commit and the issues that the pull request closes. The fix is urgent when the pull request has the label `release-now`, or an issue it closes has `priority/p0-critical`, or `type/security` with `priority/p1-high`. For an urgent fix it runs `gh pr merge <release PR> --auto --squash` with the release App token.
- The step does not run in the run of a release merge (`releases_created`), or when release-please returned no release pull request.
- The label `release-now` joins `.github/labels.yml`. A person sets it.
- `RELEASE_CYCLE.md` states the rule and how to stop an automatic release. ADR 0013 records the amendment.
- The release workflow is observable to the person who releases, so the change carries a spec delta: the new capability `release-urgent-merge`.
- This change fits one pull request.

## Capabilities

### New Capabilities

- `release-urgent-merge`: when the release pull request merges by itself, and with which token.

## Impact

- `.github/workflows/release.yml`, `.github/labels.yml`, `RELEASE_CYCLE.md`, `docs/adr/0013-releases-use-release-please-as-it-ships-and-agents-stay-out.md`.
- `tests/test_workflow_contracts.py`.

## Feasibility

- **Owner approval:** on 2026-10-23 the owner said: "Let's remove the restriction on agent work regarding release files and implement this functionality as recommended using logical labeling and rules" (#1966). AGENTS.md says only a person merges pull requests: an agent merges nothing here. The release workflow, which the owner reviews and merges through this pull request, turns on GitHub's auto-merge.
- **Repository (read 2026-10-29):** `allow_auto_merge: true`, squash merge only, squash commit from `PR_TITLE` and `PR_BODY`. `main` has no classic branch protection. Its one ruleset requires `Static Analysis`, `Tests & Coverage` and `Semantic PR title`, 0 approvals, and code scanning, code quality and code coverage rules, with no bypass actor. So auto-merge waits for the checks and rules, and for no person.
- **release-please-action v5.0.0** (`45996ed1`, the pinned SHA): `src/index.ts` sets `releases_created`, and `pr` to the first pull request that the run opened or updated. That object has `number`.
- **gh v2.103.3** (`pkg/cmd/pr/merge/merge.go`): `autoMerge: opts.AutoMergeEnable && !isImmediatelyMergeable(...)`, where `CLEAN`, `HAS_HOOKS` and `UNSTABLE` merge at once. So `--auto` merges a pull request whose checks already passed, and turns on auto-merge otherwise.
- **Token:** GitHub's documentation says events that `GITHUB_TOKEN` causes start no new workflow run, so a release pull request merged with it would never create the release. The App token already has `contents`, `issues` and `pull-requests` write.
- **The decision:** the jq expression of the step gave the expected answer for nine label sets (run by hand with jq on 2026-10-29). gh's `--jq` is gojq, which has the same `any`, `first` and variable binding.
- **Label name:** the issue proposed `release/now`. Two guard tests refuse `release/` in a workflow and in an agent document, so that the deleted release-branch process cannot return. The label is `release-now`, and the guards stay as they are.

## Existing Tool Considered

GitHub auto-merge, through `gh pr merge --auto --squash`, merges the release pull request when its checks pass. release-please-action gives the release pull request in its `pr` output. GitHub's `closingIssuesReferences` gives the issues that a pull request closes. The change builds one workflow step of shell and jq that calls these tools, and no merge loop. It deletes nothing.
