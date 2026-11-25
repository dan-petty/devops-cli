### Problem Description

`review_prompt_digest` in `src/devops_cli/ai/personas/__init__.py` hashes each `.md` file under `ai/personas/`. No review loads these files. Thus an edit of a chat persona prompt changes the digest of the review benchmark arm, and splits one arm into two.

#4630 deleted the orphan prompts and the prompt fallbacks (#4710), but the digest still reads `ai/personas/`.

### Reproduction Steps

1. Compute `review_prompt_digest()`.
2. Edit `ai/personas/challenger/prompt.md`.
3. Compute it again. The digest changes, but no review prompt changed.

### Expected vs Actual Behavior

- Expected: the digest changes only when a prompt that a review loads changes.
- Actual: a chat persona edit changes the digest.

### Proposed Solution

`review_prompt_digest` covers only the prompts that a review loads, and leaves out `ai/personas/`.

### Existing Tool Considered

A fix of project code. No tool applies. Cost to build: about 20,000 tokens and 0.5 hours.

### Acceptance Criteria

- A test: an edit of `personas/challenger/prompt.md` does not change `review_prompt_digest`.
- A test: an edit of `review_group_analysis.md` changes it.

### Dependencies

None.


Source: https://github.com/dan-petty/devops-cli/issues/4780

<!-- devops-roadmap-record {"Effort": "Low", "Priority": "P2-Medium", "Status": "In Review", "Value": "Medium", "intake.jev_shadow": "{\"at\":\"2026-11-11T21:05:27Z\",\"answers\":{\"priority\":[\"P2-Medium\",0.49,\"P2-Medium\"],\"value\":[\"Medium\",0.36,\"Medium\"],\"effort\":[\"Low\",0.98,\"Low\"],\"duplicate\":[\"\",0.11,\"\"]}}"} -->
