## ADDED Requirements

### Requirement: Agent instructions allow routine label, milestone, duplicate, and evaluation-verdict tasks
`AGENTS.md` and the routed instructions SHALL limit person-only constraints to merging pull requests (with Renovate exceptions), changing secrets, repository settings and hardware, lowering security or quality thresholds, and release steps, and SHALL NOT reserve managing issue or pull request labels, planning milestones, closing duplicates, or running evaluation verdicts via `devops review verify` solely for a person.

#### Scenario: Retired person-only phrases stay out of AGENTS.md and routed guides
- **WHEN** the agent instruction invariant check inspects `AGENTS.md`, `CONTRIBUTING.md`, `docs/SDLC.md`, `docs/ROUTINE_TASKS.md`, `docs/SELF_IMPROVEMENT.md`, and the knowledge base task guides
- **THEN** none of them contain the retired person-only prohibitions on recording evaluation verdicts, managing issue or pull request labels, or planning milestones
