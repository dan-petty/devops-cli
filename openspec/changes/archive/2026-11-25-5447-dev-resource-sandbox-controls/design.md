# Design

## Decisions
- **Placement and heading in `SECURITY.md`**: Keep the existing `## Dedicated Development Resources and Sandboxes` section between `## Infra Repos` and `## Judging a Trivy-config Alert`. Keep Title Case consistent with every other `##` heading in `SECURITY.md`, matching existing citations in `docs/ROADMAP_WORKFLOW.md`, `.github/workflows/release-image.yml`, and `docs/CLUSTER.md`, whose anchor `#dedicated-development-resources-and-sandboxes` stays unchanged.
- **Section layout**: Use bold lead-ins (`**Default.**`, `**Conditions.**`, `**Never changed.**`, `**Approval.**`) as `Infra Repos`, `A Finding with No Fix`, and `Judging a Trivy-config Alert` do, list the dedicated resources by role (homelab, devcontainer, project-owned test namespaces and repositories, RuntimeClass `gvisor`, review sandbox, planner run Job), and keep the six-column control table (`Control`, `Scope`, `Compensating control`, `Evidence`, `Approved by`, `Reviewed`) with existing owner-approved Trivy entries.
- **Invariant tests**: Add policy and table validation tests to `tests/invariants/test_agents_md.py` using `tests.support.markdown_tables.tables()`, and guideline link assertions to `tests/invariants/test_guidelines.py`.
- **Review date rule**: Validate `Reviewed` cells against ISO 8601 `YYYY-MM-DD` with `re.fullmatch` and `datetime.date.fromisoformat`.

## Rejected alternatives
- **Separate `docs/security/exceptions.md` or ADR**: Splits policy rules away from the controls and exception table in `SECURITY.md`.
- **`###` subheadings for each rule**: Breaks the bold lead-in convention shared by all other policy rule sections in `SECURITY.md`.
- **New `tests/invariants/test_security_controls_table.py` module**: Rejected by `docs/TESTING.md` and `#6080`, which keep one invariant file per subject.
- **Renaming heading to sentence case**: Conflicts with Title Case on every other `SECURITY.md` `##` heading and existing `Dedicated Development Resources and Sandboxes` references.

## Security
This change updates `SECURITY.md` only to codify strict criteria before weakening any control for a dedicated development resource or sandbox. Secrets and private-data rules on the public repository, `main` branch protection, production service controls, and human-only actions (merging PRs, modifying secrets, repository/org settings, and hardware) remain non-negotiable. Every approved change requires evidence with counts, a compensating boundary control, narrow test-verified scope, owner approval, and a `YYYY-MM-DD` review date; dedicated resources are named by role with no host names or private addresses (`tests/invariants/test_committed_addresses.py`).
