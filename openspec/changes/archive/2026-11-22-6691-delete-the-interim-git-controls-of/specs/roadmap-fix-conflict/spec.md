## MODIFIED Requirements

### Requirement: Tier 1 runs only in a runner Job
Tier 1 runs code of the checkout (`devops docs generate`, `uv lock`), so the step `fix-conflict` SHALL rebase, run tier 1 and push only with `--confirm`. The command SHALL clear the dumpable flag of its process first, and then accept `--confirm` only in a runner Job (`require_runner`), or in the agent phase of one (`require_agent_runner`). Without `--confirm` the step SHALL return `planned`, and SHALL run no code of the checkout, push nothing and write no record.

#### Scenario: Without --confirm the step gives its plan
- **WHEN** the step runs without `--confirm` on a bot pull request that conflicts with the default branch
- **THEN** it returns `planned` with the conflicted files, runs no fixer of tier 1, pushes nothing and writes no record

#### Scenario: A plan on a host with no App
- **WHEN** the step runs without `--confirm` on a host with no `service.github_app.slug`
- **THEN** it returns `planned`, as its clone makes no check of the authors, which needs the App

#### Scenario: --confirm outside a runner Job runs no step
- **WHEN** the command runs with `--confirm` outside a runner Job
- **THEN** it stops with the error of the runner check before the step

#### Scenario: A confirmed round hardens its process first
- **WHEN** the command runs with `--confirm` in a runner Job
- **THEN** it calls `deny_environment_reads`, then the runner check, and only then the step
