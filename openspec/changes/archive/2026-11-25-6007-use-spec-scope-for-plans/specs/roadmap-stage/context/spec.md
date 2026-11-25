## MODIFIED Requirements

### Requirement: A plan pull request carries a plan mark
The stage context builder SHALL mark an open pull request whose title has the type `docs(spec)` or legacy `docs(openspec)` as a plan pull request.

#### Scenario: A plan pull request overlaps a cited path
- **WHEN** A test gives the builder a fake client that holds pull request 3252, titled `docs(spec): plan #3252 stage context`, which changes `src/devops_cli/roadmap/stage/stage_overlap.py`, and an item body that cites that path.
- **THEN** The context entry holds the number, the title, the state, the plan mark and `src/devops_cli/roadmap/stage/stage_overlap.py`.

#### Scenario: A pull request that is no plan carries no mark
- **WHEN** A test gives the builder a fake client that holds pull request 3253, titled `feat(roadmap): stage context`, which changes `src/devops_cli/roadmap/stage/stage.py`, and an item body that cites that path.
- **THEN** The context entry holds the number and no plan mark.
