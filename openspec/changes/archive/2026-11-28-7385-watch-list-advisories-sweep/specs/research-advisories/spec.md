## ADDED Requirements

### Requirement: A watch entry or pin maps a component to OSV
When a component carries `osv_ecosystem` and `osv_name` from `.devops/research-watch.toml`, `devops research advisories` SHALL build its inventory with `mapped_inventory`, queue `(osv_name, version, osv_ecosystem)` in OSV for pinned releases while keeping any `repo` GitHub advisory query, read each OSV record with `osv_name`, and count no mapped component in `not_covered`.

#### Scenario: An image with a mapped OSV pair and watch entry
- **WHEN** `_plan` runs on an image `ollama/ollama` at version `0.40.18` with `osv_ecosystem` `Go`, `osv_name` `github.com/ollama/ollama`, and a watch entry for `ollama/ollama`
- **THEN** `plan.osv` holds `("github.com/ollama/ollama", "0.40.18", "Go")`, `plan.repositories` holds `("ollama/ollama", None)`, and `plan.not_covered` is empty

#### Scenario: An unpinned component with an OSV pair
- **WHEN** `_plan` runs on a component with `osv_ecosystem` and `osv_name` and an empty or non-release version
- **THEN** the component is counted in `plan.unpinned` and no OSV query is queued

#### Scenario: OSV record read uses mapped osv_name
- **WHEN** `_osv_findings` resolves an advisory for plan key `("github.com/ollama/ollama", "0.40.18", "Go")` on component `ollama/ollama`
- **THEN** `osv.get_vulnerability` is called with `"github.com/ollama/ollama"` as the package name

#### Scenario: The advisories command reads mapped_inventory
- **WHEN** `devops research advisories --root <repo> --json` runs on a repository whose watch list maps an image `osv_ecosystem` and `osv_name`
- **THEN** the command queries OSV with that mapped pair
