# Tasks

## 1. Refuse a uv audit project outside the workspace

Reads: `src/devops_cli/security/uv_audit.py`, `src/devops_cli/lang/en/messages.py`, `tests/security/test_security_uv_audit.py`, `tests/security/test_builtin_tools.py`, `tests/support/fakes/scanners.py`, `openspec/specs/scanner-adapters/spec.md`. Changes: `src/devops_cli/security/uv_audit.py`, `src/devops_cli/lang/en/messages.py`, `tests/security/test_security_uv_audit.py`, `tests/security/test_builtin_tools.py`, `tests/support/fakes/scanners.py`.

- [x] 1.1 In `tests/security/test_security_uv_audit.py`, write a case that stages a uv project at a parent of the workspace, scans the subdirectory of the workspace, and asserts that the outcome is `not_applicable` with no finding and a reason that names the project, and that the audit does not start. Add a case for a project in the workspace that audits it, and keep the `not installed` and no-lockfile cases. In `tests/security/test_builtin_tools.py`, write a case that the agent tool refuses the project outside the workspace and gives no result
  - Verification: `$ uv run devops ci test tests/security/test_security_uv_audit.py tests/security/test_builtin_tools.py` fails on the base
- [x] 1.2 In `src/devops_cli/security/uv_audit.py`, add `project_outside_workspace` to the uv audit adapter, which runs `uv workspace dir --project <target>` when uv is installed, and gives the refusal when the project lies outside the working directory. In `run_uv_audit_scan`, refuse the audit with that reason when it is not None. Add the field to `ScanMessages` in `src/devops_cli/lang/en/messages.py`. In `tests/support/fakes/scanners.py`, answer the `uv workspace dir` probe of a scanner with the project it names, without a record in `runs`
  - Verification: `$ uv run devops ci test tests/security/test_security_uv_audit.py tests/security/test_builtin_tools.py` passes

## 2. Documents

- [x] 2.1 Add the refusal to the `scanner-adapters` capability in `openspec/specs/scanner-adapters/spec.md`, with a scenario for a project outside the workspace, one in the workspace, one that uv finds none, and the `not installed` case
  - Verification: `$ uv run devops openspec check 2440-refuse-uv-audit-outside-workspace` passes

## Criteria

- Group 1: The uv audit adapter SHALL resolve the project that uv would audit from the target, and SHALL NOT start the audit when that project lies outside the workspace.
- Group 1: The adapter SHALL give the outcome `not_applicable`, with no finding, and a reason that names the directory of the project.
- Group 1: The adapter SHALL run the audit when the project lies in the workspace, and when uv finds no project.
- Group 1: The probe SHALL run only when uv is installed, so the `not installed` outcome is unchanged.
- Group 1: The refusal SHALL use a message field in `ScanMessages` in `src/devops_cli/lang/en/messages.py`.

## Workflow follow-up

- Pending a person: review the diff and approve the pull request.
