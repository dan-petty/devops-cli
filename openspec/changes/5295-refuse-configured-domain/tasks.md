# Tasks

## 1. The domain row

Kind: behavior. Reads: `tests/gate/swallowed_failures.py`, `tests/commands/test_ci_bwrap_row.py`, `src/devops_cli/core/dns_names.py`. Changes: `tests/gate/configured_domain.py`, `src/devops_cli/core/dns_names.py`, `src/devops_cli/commands/ci.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/roadmap/runner_tools.py`, `tests/invariants/test_configured_domain_check.py`, `tests/commands/test_ci_domain_row.py`, `tests/commands/test_ci_gate_rows.py`.

- [x] 1.1 Write the failing tests: the check names the path, the line, the commit and the settings key of each added line or path that names a configured domain, and never its value; it passes `example.com`, a removed line, a removed file and a name that only holds the domain as a substring; the row is the last row of the table; the row is skipped with its cause when no domain is configured, and starts its module when one is
  - Verification: `$ uv run devops ci test tests/invariants/test_configured_domain_check.py tests/commands/test_ci_domain_row.py tests/commands/test_ci_gate_rows.py`
- [x] 1.2 Add `configured_domains` to `devops_cli.core.dns_names`, the module `tests/gate/configured_domain.py`, the row `domain` with its title and skip cause, and the row as a reason for `python` and `git` in the runner tools
  - Verification: `$ uv run devops ci test tests/invariants/test_configured_domain_check.py tests/commands/test_ci_domain_row.py tests/commands/test_ci_gate_rows.py tests/roadmap/test_roadmap_runner_tools.py`
- [x] 1.3 Read each configured domain as a host name spells it: ASCII, with no blank space and no final dot, and find a Unicode label in both forms. Before this, `example.net.` in the config found no host under `example.net`
  - Verification: `$ uv run devops ci test tests/invariants/test_configured_domain_check.py`

## 2. Run the row before each push

Kind: other. Changes: `.pre-commit-config.yaml`, `tests/commands/test_instruction_generator.py`, `tests/invariants/test_workflow_contracts.py`.

- [x] 2.1 Add `domain` to the rows of the pre-push hook `devops-ci-pre-push`, to the fast static checks of the hook contract, and to the AGENTS.md line that `devops ai agents` renders from the hook
  - Verification: `$ uv run devops ci test tests/commands/test_instruction_generator.py tests/invariants/test_workflow_contracts.py`

## 3. Documents

Kind: other. Changes: `SECURITY.md`, `CONTRIBUTING.md`, `docs/TESTING.md`, `docs/SDLC.md`, `docs/adr/0014-required-checks-gate-the-merge-and-the-pre-push-hook-runs-the-fast-static-checks.md`, `src/devops_cli/ai/knowledge_base/devops_cli/tasks/ci_quality_gate.md`, `src/devops_cli/ai/knowledge_base/it_domains/topics/continuous_integration_and_progressive_verification.md`.

- [x] 3.1 Say in SECURITY.md rule 8 how the row reads the configured domains and that public evidence holds exit codes and counts only; add the row to the pre-push hooks of CONTRIBUTING.md, docs/SDLC.md and the knowledge base, and to the rows and the invariant test files of docs/TESTING.md
  - Verification: `$ uv run devops ci docs`
- [x] 3.2 Add a `Fact out of date` line to the Status History of ADR 0014, whose pre-push hook now also runs the `domain` row
  - Verification: `$ uv run devops ci test tests/invariants/test_adr_records.py`

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
