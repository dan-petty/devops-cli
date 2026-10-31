# Proposal

## Why
The command `devops pr create` warns when a pull request title uses scope `git`:
`The scope git of the title has no label: .github/labels.yml does not declare scope/git. The pull request gets no scope label.`
The file `.github/labels.yml` declares `scope/github` and other scopes, but does not declare `scope/git`. A pull request with a `git` scope receives no scope label.

## What Changes
- Add `scope/git` to `.github/labels.yml` in the Scope Labels section directly after `scope/github`.
- Set label color to `24292E` and description to `Git commands, git configuration, and git credential handling`.
- Add test coverage in `tests/test_pr_title_labels.py` verifying `scope/git` declaration and PR label assignment without warnings.

## Capabilities

### New Capabilities
- None.

### Modified Capabilities
- None.

## Impact
Pull requests with titles using `scope/git` receive the `scope/git` label automatically and emit no warning.

## Feasibility
Confirmed against `.github/labels.yml`:
- `.github/labels.yml` contains `scope/github` at lines 74-76 with color `24292E`.
- `grep -n "scope/git" .github/labels.yml` confirms that `scope/git` is not present.
- Adding the label entry satisfies the taxonomy requirement of `devops pr create`.
