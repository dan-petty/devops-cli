# Proposal: #6469

## Why
`devops pr create --repo OWNER/NAME --head BRANCH` previously checked the title scope against `.github/labels.yml` on the base branch only, so pull requests that add a new scope label on the head branch were refused and received a misleading checkout-only refusal message.

## What Changes
- Read `.github/labels.yml` from both the base ref and the `--head` ref when `--repo` and `--head` are both set, in both the form check and post-create PR labeling, while keeping non-not-found errors fatal if either ref is unreadable.
- Allow either ref to lack `.github/labels.yml` when the other ref declares it, and raise when both refs lack the file.
- Pass the checked ref location (`labels_source`) into `title_problems` so refusal messages name the base ref and `--head` ref when `--repo` + `--head` are set, the base ref only when `--repo` is set without `--head`, and `.github/labels.yml` only in checkout mode.
- Include the `--head` `.github/labels.yml` read in `plan_pr_title_labels` and `plan_pr_create` dry-run request plans when `--repo` and `--head` are set.

## Capabilities

### Modified Capabilities
- `pull-request-form`: Read `.github/labels.yml` from `--head` in addition to `--base` when `--repo` and `--head` are set, and report the checked refs in the scope refusal message.

## Impact
- `src/devops_cli/roadmap/pull_labels.py`, `src/devops_cli/roadmap/pull_describe.py`, `src/devops_cli/roadmap/pull_form.py`, `src/devops_cli/github/pr_plans.py`, and `src/devops_cli/commands/pr.py`
- No external dependency added.

## Feasibility
Confirmed against `src/devops_cli/commands/pr.py`, `src/devops_cli/roadmap/pull_describe.py`, `src/devops_cli/roadmap/pull_labels.py`, and `src/devops_cli/roadmap/pull_form.py`. `InMemoryRoadmapStore.repository_file` and `GitHubStore.repository_file` both accept `ref=head` and raise `GitHubFileNotFoundError` when absent on a single ref.

## Existing Tool Considered
Alternatives check recorded verdict `none`: no external tool reads `.github/labels.yml` at git refs inside `devops pr create`'s own form check. Cost to build in place: ~50 lines across existing PR/roadmap modules plus unit tests (~4,000 tokens, <1h elapsed).
