## ADDED Requirements

### Requirement: An open change's plan is no feasibility evidence
`check_proposal` SHALL refuse a `feasibility` line that cites `proposal.md` or `design.md` under `openspec/changes/` when the path is not under `openspec/changes/archive/`. The problem SHALL name the cited path, and the gate SHALL be `citation`. A plan that cites the source at the staged commit, or the plan of an archived change, SHALL add no problem.

#### Scenario: A feasibility line cites another open change's proposal
- **WHEN** `proposal_evidence_problems` reads the feasibility line `openspec/changes/3307-the-plan-check-names-a-caller/proposal.md states the method`
- **THEN** it returns one problem that names that path and says that the change is not archived

#### Scenario: An archived change's plan is cited
- **WHEN** a feasibility line cites `openspec/changes/archive/2026-11-13-1-a-change/proposal.md`
- **THEN** `proposal_evidence_problems` returns no problem

#### Scenario: The problem reaches the citation gate
- **WHEN** a plan holds a feasibility line that cites an open change's proposal
- **THEN** `check_proposal` returns the problem under `ProposalGate.CITATION`

### Requirement: The stage prompt names the staged source as the evidence
The stage prompt SHALL state that a `feasibility` line proves its claim with the source at the staged commit, and never with the `proposal.md` or `design.md` of a change that is not in `openspec/changes/archive/`.

#### Scenario: The prompt states the evidence rule
- **WHEN** a test reads `src/devops_cli/ai/tasks/roadmap_stage_change.md`
- **THEN** the text holds the rule that only the source at the staged commit is evidence
