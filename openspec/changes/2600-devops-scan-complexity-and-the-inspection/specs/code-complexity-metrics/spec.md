## Purpose
Defines how devops-cli computes and reports function complexity for scan and inspection commands

## ADDED Requirements

### Requirement: single-source-complexity
The two product readers (devops scan complexity and the inspection hotspots) SHALL get their complexity figure from the McCabe port in core/code_metrics.py, and a test SHALL hold that port equal to Ruff's C901.

#### Scenario: port matches ruff
- **WHEN** the 12 parametrized samples in tests/test_code_metrics.py run
- **THEN** each measured value equals the value that ruff check --select C901 with max-complexity = 0 reports for the same function
