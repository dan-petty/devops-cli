# Task 310: Terraform & OpenTofu HCL AST Analysis, State Introspection & Drift Optimization Research

**Issue**: [#310](https://github.com/dan-petty/devops-cli/issues/310)
**Status**: Done
**Milestone**: `v0.2.22`
**Priority**: `priority/p1-high`
**Scope**: `type/feature`, `scope/cli`, `priority/p1-high`

---

## 1. Description & Objectives

Read-only Infrastructure-as-Code queries required a full `tofu` / `terraform` binary invocation against an initialized working directory, paying process startup and provider-loading cost to answer questions that are answerable from the configuration and state files alone. This deliverable introduces an in-process HCL AST and state analysis engine, adding resource dependency graphs, blast-radius analysis, and structural drift detection that run with no binary and no `terraform init`.

### Key Deliverables Completed:

- [x] **HCL AST Analysis Engine (`src/devops_cli/tf/analysis.py`)**:
  - In-process HCL parsing via `python-hcl2`, projecting `resource`, `data`, `module`, `variable`, and `output` blocks into typed declarations.
  - Normalisation of the quoting and `__is_block__` markers `python-hcl2` emits, so attribute values and block labels are usable directly.
  - Reference extraction resolving `${...}` interpolations and bare traversals to the address they depend on, correctly distinguishing resource addresses from the language's named values (`var`, `local`, `each`, `count`, `path`, `self`, `terraform`).
  - Per-file error isolation: a malformed manifest is recorded in `failed_files` and surfaced to the user rather than aborting the scan or silently hiding the rest of the configuration.
- [x] **State Introspection**:
  - `terraform.tfstate` JSON projected into typed `IaCState` / `IaCStateResource` models carrying format version, writing binary version, serial, lineage, per-resource instance counts, and outputs.
  - Canonical addressing for data sources (`data.<type>.<name>`) and module-scoped resources (`module.db.<type>.<name>`).
  - Malformed or absent state degrades to `None` rather than raising.
- [x] **Dependency Graph & Blast Radius**:
  - `build_dependency_graph` constructs an in-memory address-to-dependencies mapping spanning resources and modules, combining interpolated references with explicit `depends_on` edges and excluding addresses declared elsewhere.
  - `compute_blast_radius` traverses dependents transitively with cycle termination, reporting direct dependents, transitive impact, and the address's own dependencies.
- [x] **Structural Drift Detection**:
  - `detect_drift` compares declared managed resources against recorded state, reporting resources declared but never applied and resources still tracked after their declaration was removed. Data sources are excluded, being reads rather than managed resources.
- [x] **New Commands**:
  - `devops tf graph [--resource ADDR] [--json]` — dependency table, or blast radius for one address.
  - `devops tf drift [--json]` — configuration-versus-state divergence.
  - Both support `--dry-run`.
- [x] **Centralized Constants**: HCL file extensions, state file resolution order, the closed top-level block-type set, the `python-hcl2` block marker, and non-resource traversal namespaces centralized in `src/devops_cli/config/constants.py`.
- [x] **Typed Models (`src/devops_cli/models/tf.py`)**: `IaCResource`, `IaCModule`, `IaCConfiguration`, `IaCStateResource`, `IaCState`, `IaCDriftReport`, `IaCBlastRadius`.
- [x] **Dependency**: `python-hcl2==8.1.4` (pulls `lark==1.3.1`), pinned exactly and lockfile-verified.
- [x] **Automated Tests & Quality Gates**:
  - 35 unit tests in `tests/test_tf_analysis.py` using structural tuple equality assertions, covering parsing, normalisation, reference extraction, graph construction, cycle-safe blast radius, state projection, drift in both directions, and all CLI surfaces.
  - `src/devops_cli/tf/analysis.py` at 97% coverage.
  - Cyclomatic complexity $M \le 10$ and nesting depth $\le 5$ maintained (`devops scan complexity src/devops_cli/tf` clean).
  - 100% passing status across Gated CI validation suite (`uv run devops ci`).

## Verification Results

- `uv run devops ci` — all gates pass (tests, coverage $\ge 90\%$, lint, format, mypy strict, audit, security, actionlint, docs, uv check, lockfile).
- `devops tf graph`, `devops tf graph --resource`, and `devops tf drift` verified end-to-end against a representative configuration and state fixture.

## Scope Notes

**Infracost parsing was already typed.** The task description called for replacing "ad-hoc regex cost estimation with a typed Infracost schema parser". `src/devops_cli/tf/cost.py` already parses Infracost output through the `TFCostBreakdownResult` / `TFCostResource` Pydantic models with no regex involved, so no change was warranted; the description reflected a speculative assumption rather than the code.

**Binary-backed commands are unchanged.** `init`, `plan`, `apply`, `destroy`, and `fmt` continue to invoke the binary, because they require provider plugins, remote backend negotiation, and the real plan graph. The in-process engine is deliberately scoped to read-only queries answerable from configuration and state, where it removes the binary requirement entirely.

**Drift detection is structural, not live.** `detect_drift` compares declared configuration against recorded state. Comparing recorded attribute values against live infrastructure requires a provider refresh and is therefore still `tofu plan` territory; this is documented in the function's docstring so the boundary is not mistaken.
