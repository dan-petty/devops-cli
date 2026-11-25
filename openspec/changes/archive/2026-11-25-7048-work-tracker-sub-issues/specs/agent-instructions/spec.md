## ADDED Requirements

### Requirement: Agent instructions forbid returning trackers and route work to sub-issues and related issues
Rule 2 of `AGENTS.md`, `src/devops_cli/templates/AGENTS.md.j2`, and the `devops-roadmap` skill SHALL instruct agents never to return a tracker or epic issue and instead to inspect and work its open sub-issues or related issues, while keeping `AGENTS.md` and generated templates within `CONST_AGENTS_MD_MAX_CHARS` and matching rule titles across `AGENTS.md` and `AGENTS.md.j2`.

#### Scenario: An agent reads Rule 2 and the roadmap skill before returning a tracker
- **WHEN** an agent inspects Rule 2 of `AGENTS.md` or `.agents/skills/devops-roadmap/SKILL.md`
- **THEN** both tell the agent never to return a tracker (`type/epic` or sub-issues) and to work its open sub-issues or related issues instead
- **AND** `AGENTS.md`, `src/devops_cli/templates/AGENTS.md.j2`, and the three skill roots pass all `tests/invariants/test_agents_md.py` and `tests/invariants/test_skills.py` checks
