# Proposal: #7040

## Why

Issue #7040 removes unnecessary person-only restrictions from agent instructions across the repository. Today `AGENTS.md`, `CONTRIBUTING.md`, workflow documents, knowledge base task guides, skills, and `src/devops_cli/ai/tasks/roadmap_refine_reply.md` still list routine actions such as managing issue and pull request labels, planning milestones, closing duplicate issues, and running `devops review verify` during evaluation as person-only steps. Interactive agents stop and ask a person to perform these routine steps even though `devops` CLI commands already handle them cleanly.

## What Changes

- Update `AGENTS.md` ("Only a person" paragraph) so only merging pull requests (with existing Renovate exceptions), changing secrets, repository settings and hardware, threshold exceptions (rule 5), and release steps stay person-only; explicitly allow agents to manage issue and pull request labels, close duplicates, manage milestones, and record evaluation verdicts.
- Update `CONTRIBUTING.md`, `docs/SDLC.md`, `docs/ROUTINE_TASKS.md`, `docs/SELF_IMPROVEMENT.md`, `docs/ROADMAP_WORKFLOW.md`, `docs/roadmap/stage.md`, `docs/roadmap/intake.md`, `docs/roadmap/refine.md`, `src/devops_cli/ai/knowledge_base/devops_cli/tasks/github_project_management.md`, `src/devops_cli/ai/knowledge_base/devops_cli/tasks/ai_code_review.md`, and the skill copies under `.agents/skills/`, `.claude/skills/`, and `.kilocode/skills/` so interactive agents can manage labels (including removing `verdict/fix-plan` after verified plan repairs), manage milestones, close duplicates, and run `devops review verify` when evaluating findings (while keeping automated review pipelines from verifying their own findings).
- Update `src/devops_cli/ai/tasks/roadmap_refine_reply.md` so `kind: person` applies only to a merge, a secret, a repository setting or a host, without changing `intake` or `consolidate` automation rules.
- Add invariant and prompt tests in `tests/invariants/test_agents_md.py` and `tests/roadmap/refine/test_roadmap_refine_proposal.py` to prevent these unnecessary restrictions from returning.
- This change alters observable agent-instruction contracts (`agent-instructions`) and refine proposal prompt behavior (`roadmap-refine/proposal`), so it carries deltas for both capabilities. It fits in one pull request.

## Capabilities

### Modified Capabilities
- `agent-instructions`: Remove `records verdicts` and `plans milestones` from the inline person-only constraints in `AGENTS.md` and keep skills and routed documents aligned.
- `roadmap-refine/proposal`: Restrict `kind: person` questions in `src/devops_cli/ai/tasks/roadmap_refine_reply.md` to owner-only acts (`a merge, a secret, a repository setting or a host`).

## Impact

- Interactive coding sessions and `devops roadmap refine` stop escalating routine label, milestone, duplicate-closure, and evaluation-verdict work to a person.
- Security boundaries (merging pull requests, secrets, repository settings, hardware, threshold overrides, releases, and `intake`/`consolidate` automation rules) stay intact.

## Feasibility

Confirmed against the repository in `/workspaces/devops-cli/.data/agent/worktrees/w-7040`:
- `tests/invariants/test_agents_md.py:321-333` requires keeping `**Only a person** merges pull requests` and `changes secrets, repository settings and hardware` in `AGENTS.md`, and does not assert `records verdicts` or `plans milestones`.
- `src/devops_cli/commands/gh.py` (`issue_edit`, `label_sync`, `milestones_edit`, `milestones_close`, `issue_close`) and `src/devops_cli/commands/review.py` (`verify_finding`) impose no technical block on interactive agents running these commands.
- `src/devops_cli/github/release_title.py:58-60` treats Markdown files under `src/devops_cli/` as document data rather than runtime code.

## Existing Tool Considered

No external tool covers editing repository-specific Markdown instructions and prompts. Existing repository checks (`tests/invariants/test_agents_md.py`, `tests/roadmap/refine/test_roadmap_refine_proposal.py`, `uv run devops ci docs`, `uv run devops openspec check`, and `vale`) validate formatting, links, invariants, and rules with zero new code built.
