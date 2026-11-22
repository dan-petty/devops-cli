# Tasks

## 1. Record the repository settings decision

Reads: `docs/adr/0026-github-settings-are-opentofu-code-the-owner-applies.md`, `docs/adr/0032-infrastructure-templates-live-in-four-homes.md`, `docs/adr/README.md`, `src/devops_cli/roadmap/onboard.py`, `src/devops_cli/roadmap/adr.py`.

Changes: `docs/adr/0035-the-onboard-command-owns-the-repository-settings.md` (new), `docs/adr/README.md`.

- [x] 1.1 Write ADR 0035 with decisions D1 to D4 of #6773 and the amendments of ADR 0026 decisions 1, 4 and 7
  - Verification: `$ uv run devops ci test tests/invariants/test_adr_records.py`
- [x] 1.2 Regenerate the index of `docs/adr/README.md`
  - Verification: `$ uv run devops ci --check --only docs,domain`

## 2. Amend ADR 0026 and the guideline

Changes: `docs/adr/0026-github-settings-are-opentofu-code-the-owner-applies.md`, `docs/guidelines/production-readiness.md`.

- [x] 2.1 Add `amended-by: ["0032", "0035"]` and a dated `Amended by ADR 0035` line to ADR 0026
  - Verification: `$ uv run devops ci test tests/invariants/test_adr_records.py`
- [x] 2.2 Change row ACC-3 of the production readiness guideline to the command and the organization stacks
  - Verification: `$ uv run devops ci test tests/invariants/test_guidelines.py`

## Criteria

- Group 1: `ls docs/adr/0035-*.md` SHALL find one file, and `grep -c 0035 docs/adr/README.md` SHALL print 1 or more.
- Group 1: The record SHALL hold no real domain, host or node name, private address, device path or token value.
- Group 2: `grep -c 0035 docs/adr/0026-*.md` SHALL print 2.
- Group 2: The accepted body of ADR 0026 SHALL keep its `body-hash`.

## Workflow follow-up

- The items of the design build the decision: the Copier template and the baseline in dan-petty/infra, the reusable workflows in dan-petty/infra, `devops gh secret sync --env`, the command of #6773, the nightly drift Job, and the convergence of the existing repositories.
