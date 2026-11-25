## ADDED Requirements

### Requirement: No spend disagreement pair
The project review catalog SHALL define no disagreement pair named `spend`.

#### Scenario: Shipped catalog omits the spend pair
- **WHEN** `load_catalog()` reads `src/devops_cli/roadmap/project_review/catalog.yaml`
- **THEN** no entry in `catalog.disagreements` has `id == "spend"`

### Requirement: Both spend facts stay separate
The project review catalog MUST keep `prometheus.cli_spend` and `prometheus.gateway_spend` as separate facts.

#### Scenario: Dry run lists both spend facts
- **WHEN** a person runs `uv run devops roadmap review run --since 2026-11-16T12:00Z --until 2026-11-17T12:00Z --dry-run`
- **THEN** the command exits 0 and prints a line for `prometheus.cli_spend` and a line for `prometheus.gateway_spend`
