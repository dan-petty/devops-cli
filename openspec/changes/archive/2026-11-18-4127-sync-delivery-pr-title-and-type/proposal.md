# Proposal: #4127

## Why

The implement job copies the title of an issue to the delivery pull request (#4127). When staging refines the scope of an issue, the title and Conventional Commit type become inaccurate. A test-only change keeps an infra or bug type and adds incorrect changelog entries.

## What Changes

- Derive the Conventional Commit type from the changed paths of the staged plan.
- Use `test` when the plan changes only paths under `tests/`.
- Use `docs` when the plan changes only `docs/`, `openspec/`, or Markdown files.
- Use `ci` when the plan changes only `.github/workflows/` or `.github/actions/`.
- Keep the issue title type for any other set of changed paths.
- Read the pull request summary from the first non-empty line of the proposal `## Summary` section.
- Fall back to the first bullet of the proposal `## What Changes` section when `## Summary` is missing.
- Fall back to the issue summary when the proposal has no usable summary or when the title breaks the form.
- Update pull request labels to match the derived title type and remove stale type labels.

## Capabilities

### Modified Capabilities

- `roadmap-implement-job/pull-request`: Derive delivery pull request title and Conventional Commit type from staged plan changed paths and proposal summary.

## Impact

- Pull requests created by `devops roadmap implement` use accurate commit types and summaries.
- No impact on existing command line interfaces.

## Feasibility

- The implement runner accesses the proposal file and changed paths during execution.
- Existing functions `delivery_title`, `section_text`, and `title_problems` support this derivation.

## Existing Tool Considered

No external library provides repository-specific Conventional Commit derivation for OpenSpec plans. Building internal helpers takes about 2,000 tokens and 15 minutes.
