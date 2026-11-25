# Design

## Decisions

1. **Keep only hard security, merge, threshold, and release boundaries person-only**: `AGENTS.md` preserves `**Only a person** merges pull requests` (with existing Renovate exceptions), `changes secrets, repository settings and hardware`, threshold exceptions in rule 5, and `no release step` so existing safety invariants in `tests/invariants/test_agents_md.py:321-333` continue to pass while removing `records verdicts` and `plans milestones`.
2. **Distinguish automated review self-grading from interactive evaluation**: `docs/SDLC.md`, `docs/ROUTINE_TASKS.md`, `docs/SELF_IMPROVEMENT.md`, and `src/devops_cli/ai/knowledge_base/devops_cli/tasks/ai_code_review.md` continue to forbid automated review pipelines from grading their own findings, while allowing an interactive agent or developer evaluating findings to clear `verdict/fix-plan` after verified fixes or run `devops review verify`.
3. **Restrict refine `person` escalation to owner-only acts**: `src/devops_cli/ai/tasks/roadmap_refine_reply.md` removes `a review verdict` and `a milestone` from the `kind: person` list while leaving `devops roadmap intake` and `devops roadmap consolidate` rules unchanged.

## Rejected alternatives

- **Remove `verified_by="human"` in `src/devops_cli/ai/review/adjudication.py` and change `intake`/`consolidate` automation**: Rejected because modifying runtime code and review exporter behavior is outside the agreed documentation and refine-prompt scope (the owner selected updating instructions, skills, knowledge base, and `roadmap_refine_reply.md` without changing `intake`/`consolidate` automation rules).
- **Restrict removal strictly to `verdict/*` labels while keeping `devops review verify` and milestones person-only**: Rejected because the owner confirmed agents may manage issue/PR labels, close duplicates, manage milestones, and run `devops review verify` during finding evaluation.
