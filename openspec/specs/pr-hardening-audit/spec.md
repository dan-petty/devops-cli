# pr-hardening-audit Specification

## Purpose
How the hardening audit decides that a merged defect pull request added a guardrail, and how the audit workflow shows the result after the merge without an issue and without a failed run.

## Requirements

### Requirement: A test counts as a hardening surface
`audit_pr_hardening` SHALL count an addition under `tests/` as a hardening guardrail.

#### Scenario: A defect pull request adds a regression test
- **WHEN** A defect pull request adds lines under `tests/` and adds no line under another hardening surface.
- **THEN** The audit reports the pull request as hardened and names `tests/`.

### Requirement: A living spec counts as a hardening surface
`audit_pr_hardening` SHALL count an addition under `openspec/specs/` as a hardening guardrail.

#### Scenario: A defect pull request adds a living spec requirement
- **WHEN** A defect pull request adds lines under `openspec/specs/` and adds no line under another hardening surface.
- **THEN** The audit reports the pull request as hardened and names `openspec/specs/`.

### Requirement: No guardrail leaves the pull request unhardened
`audit_pr_hardening` SHALL report a defect pull request with no addition under a hardening surface as not hardened, and SHALL count no addition under `openspec/changes/`.

#### Scenario: A defect pull request adds only product code
- **WHEN** A defect pull request adds lines under `src/` only.
- **THEN** The audit reports the pull request as not hardened and names no surface.

#### Scenario: A defect pull request adds only a change folder
- **WHEN** A defect pull request adds lines under `openspec/changes/` and under `src/`, and adds no line under another hardening surface.
- **THEN** The audit reports the pull request as not hardened and names no surface.

### Requirement: Pull request 3467 reports hardened
The audit SHALL report the recorded file list of pull request 3467 as hardened.

#### Scenario: The recorded file list of pull request 3467 is audited
- **WHEN** A test audits the file list recorded for pull request 3467.
- **THEN** The audit reports the pull request as hardened through its `tests/` and `openspec/specs/` additions.

### Requirement: The job summary shows the report
The audit workflow SHALL append the hardening report to `$GITHUB_STEP_SUMMARY`.

#### Scenario: The workflow file is read for the report step
- **WHEN** A test reads `.github/workflows/defect-pr-hardening-audit.yml`.
- **THEN** The step that runs `devops pr hardening-report` writes its output to `$GITHUB_STEP_SUMMARY`.

### Requirement: The workflow files no issue
The audit workflow MUST NOT create an issue and MUST NOT pass `--fail-on-missing` to the report.

#### Scenario: The workflow file is read for an issue step
- **WHEN** A test reads `.github/workflows/defect-pr-hardening-audit.yml`.
- **THEN** The file holds no `issues create` command and no `--fail-on-missing` argument.

### Requirement: The workflow holds no issue write permission
The audit workflow MUST NOT request the `issues: write` permission.

#### Scenario: The permissions block is read
- **WHEN** A test reads the `permissions` block of `.github/workflows/defect-pr-hardening-audit.yml`.
- **THEN** The block holds `contents: read` and `pull-requests: read` and no `issues` entry.

### Requirement: The workflow cites the owning document
The audit workflow text MUST NOT cite `AGENTS.md` and SHALL cite `docs/SELF_IMPROVEMENT.md`.

#### Scenario: The workflow text is read
- **WHEN** A test reads the text of `.github/workflows/defect-pr-hardening-audit.yml`.
- **THEN** The text holds no `AGENTS.md` and holds `docs/SELF_IMPROVEMENT.md`.
