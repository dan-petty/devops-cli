# Proposal

## Why

`review_prompt_digest` hashes each `.md` file under `ai/personas/`, and no review loads those files. An edit of a chat persona prompt splits one benchmark arm into two (#4829).

## What Changes

- The digest covers only the review task prompts under `ai/tasks/`, and the function takes no personas directory.
- A test edits a chat persona and holds the digest still, and an edit of `review_group_analysis.md` moves it.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `ai-review-profile`: The prompt digest covers the review prompts only.

## Impact

- Code: `src/devops_cli/ai/personas/__init__.py`
- Tests: `tests/ai/review/test_review_profile.py`

## Feasibility

- The digest already walks one directory for each label.
- The profile records the digest already.
- Verification commands: `uv run devops ci test tests/ai/review` and `uv run devops ci --check --only lint,format,typecheck`.

## Existing Tool Considered

The digest is the repository's own. The change removes one folder from it.
