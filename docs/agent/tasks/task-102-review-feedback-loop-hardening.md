# Task: Strengthen Review Prompts, Feedback Dataset Export & Self-Improvement Loop (#102)

**Issue**: #102
**Status**: Done
**Milestone**: v0.2.15
**Priority**: priority/p1-high
**Scope**: scope/ai

## Description
Deepen closed-loop integration between AI code review findings, automated and human verifications, feedback dataset calibration (`feedback_dataset.jsonl`), review task prompts, and specialized persona instructions. Ensure the review engine continuously learns from mitigated/invalidated findings and known hallucinations catalog.

## Acceptance Criteria
- [x] Verify zero unresolved findings in review session `20260910-143644`
- [x] Export and synchronize complete feedback dataset (558 records) to `.data/reviews/feedback_dataset.jsonl` and `.data/feedback_dataset.jsonl`
- [x] Strengthen core review task prompts (`code_review_prompt.md`, `diff_review_prompt.md`, `path_review_prompt.md`, `review.md`, `review_output_instruction.md`, `verify_finding_system.md`) with feedback memory and architectural invariant grounding
- [x] Strengthen specialized persona prompts (`devsecops`, `qa`, `architect`, `auditor`, `challenger`, `pm`) with falsification criteria and domain invariants
- [x] Update knowledge base documentation (`ai_code_review.md`, `agentic_ai_and_code_reviews.md`) and `AGENTS.md`
- [x] Synchronize documentation via `devops docs generate --sync-readme`
- [x] Pass all 10 CI quality gates (`devops ci`) and architectural invariant tests
- [x] Synchronize project card via `devops gh project sync`

## Deliverables
- [x] Exported feedback datasets via `devops review export-feedback`
- [x] Enhanced core review task markdown templates in `src/devops_cli/ai/tasks/`
- [x] Enhanced persona prompts in `src/devops_cli/ai/personas/`
- [x] Updated task manual `src/devops_cli/ai/knowledge_base/devops_cli/tasks/ai_code_review.md`
- [x] Updated IT domain guide `src/devops_cli/ai/knowledge_base/it_domains/topics/agentic_ai_and_code_reviews.md`
- [x] Updated `AGENTS.md` closed-loop feedback section
