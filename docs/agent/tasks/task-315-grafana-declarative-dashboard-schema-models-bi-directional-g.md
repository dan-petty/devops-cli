# Task 315: Grafana Declarative Dashboard Schema Models & Bi-Directional GitOps Provisioning Research

**Issue**: [#315](https://github.com/dan-petty/devops-cli/issues/315)
**PR**: [#359](https://github.com/dan-petty/devops-cli/pull/359)
**Status**: In Review
**Milestone**: `v0.2.22`
**Priority**: `priority/p1-high`
**Scope**: `type/feature`, `scope/cli`, `priority/p1-high`

---

## 1. Description & Objectives

Dashboards were maintained as 884 lines of static JSON across four files, in which every panel repeated its datasource binding, colour mode, legend options, and hand-written grid coordinates. That boilerplate is tedious to diff, impossible to parameterise across clusters, and offers no way to catch a malformed query, an overlapping layout, or a duplicate panel id before Grafana renders the result — where the only symptom is a blank or wrong panel.

### Key Deliverables Completed:

- [x] **Typed Dashboard Schema (`src/devops_cli/grafana/schema.py`)**:
  - Pydantic models for the Grafana 10+ dashboard JSON shape: `Dashboard`, `Panel`, `Target`, `GridPos`, `Datasource`, `FieldConfig`, `Legend`.
  - `to_grafana_json()` emits Grafana's camelCase aliases and omits unset optional fields, so generated output is comparable with hand-authored JSON.
  - `GridPos` exposes edge geometry and an `overlaps` predicate, making layout collisions computable rather than visual.
- [x] **Reusable Panel Builders (`src/devops_cli/grafana/builders.py`)**:
  - `timeseries`, `stat`, and `row` builders carrying the project's standard styling and datasource binding.
  - `targets()` assigns sequential `refId` values, since a duplicate silently drops a series.
  - `layout()` assigns panel ids and grid positions automatically, flowing panels left to right and wrapping those that will not fit. Hand-written coordinates are the most common cause of a visually broken dashboard; automatic layout removes the possibility, and a property test asserts laid-out panels can never overlap.
- [x] **Static Dashboard Linting (`src/devops_cli/grafana/linter.py`)**:
  - Detects missing uid, duplicate panel ids, panels exceeding the 24-column grid, overlapping panels, empty or duplicate-`refId` targets, unbound datasources, and malformed PromQL.
  - PromQL targets are validated with the same checker the Prometheus commands use (task #314), so a query rejected at the command line cannot silently ship inside a dashboard.
- [x] **New Command**: `devops grafana dashboards lint [PATH]` accepting a file or directory, with `--json` and `--dry-run`, exiting non-zero on errors so CI can gate on it.
- [x] **Typed Models**: `DashboardLintIssue` and `DashboardLintReport` in `src/devops_cli/models/grafana.py`.
- [x] **Centralized Constants**: grid width, schema version, panel types, and default panel/row heights.
- [x] **Automated Tests & Quality Gates**:
  - 38 unit tests in `tests/test_grafana_dashboards.py` using structural tuple equality assertions.
  - `builders.py` at **100%**, `schema.py` at **99%**, `linter.py` at **94%** coverage.
  - Cyclomatic complexity $M \le 10$ and nesting depth $\le 5$ across all new modules.
  - 100% passing status across Gated CI validation suite (`uv run devops ci`).

## Verification Results

- `uv run devops ci` — all gates pass (tests, coverage $\ge 90\%$, lint, format, mypy strict, audit, security, actionlint, docs, uv check, lockfile).
- All four dashboards shipped in `k8s/monitoring/dashboards/` lint clean (30 panels, zero errors, zero warnings), and a parametrised test asserts this permanently.

## Design Constraint: No False Positives on Working Dashboards

The four dashboards in this repository are hand-authored and known to render, so any lint error against them would be a defect in the linter rather than in the dashboard. They are linted as a parametrised test over the real files, which is what keeps a future check from being added that rejects valid work. The same reasoning governs the PromQL validation those targets inherit from task #314.

## Scope Note

**Bi-directional folder and permission reconciliation, datasource health probing, and synthetic alert rule generation were not implemented.** Each requires a live Grafana instance with credentials to exercise meaningfully, and reconciliation in particular is a destructive operation — it decides what to delete from a live instance. The value available without a server was the schema, the builders, and the linting, which is where a dashboard defect is actually introduced. Reconciliation should be built against a real Grafana with its failure modes observable, not inferred.
