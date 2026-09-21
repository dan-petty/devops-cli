# Task 314: Prometheus PromQL AST Validation, Client-Side Anomaly Detection & Alertmanager Engine Research

**Issue**: [#314](https://github.com/dan-petty/devops-cli/issues/314)
**PR**: [#358](https://github.com/dan-petty/devops-cli/pull/358)
**Status**: In Review
**Milestone**: `v0.2.22`
**Priority**: `priority/p1-high`
**Scope**: `type/feature`, `scope/telemetry`, `priority/p1-high`

---

## 1. Description & Objectives

PromQL expressions were forwarded to `/api/v1/query` after a length check and nothing else, so a typo cost a network round trip and returned an error phrased in the server's terms rather than pointing at the offending character. Metric series were rendered but never analysed, leaving "is this behaving unusually, and where is it heading" to be expressed as increasingly baroque server-side subqueries.

### Key Deliverables Completed:

- [x] **In-Process PromQL Structural Validation (`src/devops_cli/prometheus/promql.py`)**:
  - Bracket balance and nesting, string literal termination, and range-selector duration shape verified before dispatch, reporting the offending character position.
  - String literals are masked before structural analysis, so a regex inside a label matcher (`{__name__=~"node_[a-z]+_total"}`) cannot be miscounted as grouping delimiters.
  - Duration checks are suppressed while brackets are unbalanced, since positions derived from a mis-parsed selector would point at the wrong character.
  - Wired into `_validate_expr`, so every PromQL-accepting command validates before contacting the server.
- [x] **Client-Side Anomaly Detection & Forecasting (`src/devops_cli/prometheus/analysis.py`)**:
  - Z-score outlier detection with a configurable threshold, reporting each anomaly's index, timestamp, value, score, and direction.
  - Exponentially weighted moving average smoothing and least-squares slope fitting.
  - Trend classification scaled by series magnitude, so a metric in bytes is not judged by the same absolute slope as a ratio.
  - Forward projection extending the smoothed level along the fitted slope.
  - Series shorter than `DEFAULT_ANOMALY_MIN_SAMPLES` report nothing, because a handful of points cannot establish a baseline.
- [x] **Robust Payload Extraction**: samples that are unparseable or `NaN` — both legal in a Prometheus range response — are skipped rather than coerced, so a reported gap never masquerades as a zero measurement.
- [x] **New Command**: `devops prometheus analyze <expr>` with `--threshold`, `--start`, `--step`, `--json`, and `--dry-run`.
- [x] **Typed Models**: `TrendDirection`, `MetricAnomaly`, and `SeriesAnalysis` in `src/devops_cli/models/prometheus.py`, replacing ad-hoc dictionary handling.
- [x] **Centralized Constants**: PromQL bracket pairs, quote characters, and duration units in `constants.py`; anomaly threshold, minimum samples, EWMA alpha, and forecast horizon in `defaults.py`.
- [x] **Automated Tests & Quality Gates**:
  - 44 unit tests in `tests/test_promql_analysis.py`, including a 15-case parametrised suite asserting that valid PromQL is never rejected.
  - `promql.py` at **100%**, `analysis.py` at **97%** coverage.
  - Cyclomatic complexity $M \le 10$ and nesting depth $\le 5$ across all touched modules.
  - 100% passing status across Gated CI validation suite (`uv run devops ci`).

## Verification Results

- `uv run devops ci` — all gates pass (tests, coverage $\ge 90\%$, lint, format, mypy strict, audit, security, actionlint, docs, uv check, lockfile).
- `devops scan complexity` clean on `prometheus/promql.py`, `prometheus/analysis.py`, and `commands/prometheus.py`.

## Design Constraint: Never Reject a Valid Query

A client-side validator that wrongly rejects a valid expression blocks work the server would happily have served — strictly worse than forwarding a malformed query the server would have rejected anyway. The validator therefore checks only what is unambiguously malformed and deliberately does **not** police function or aggregation names, which vary by Prometheus version and would turn a version skew into a false rejection. The parametrised suite covering subqueries, nested aggregations, regex label matchers, offset modifiers, and compound durations exists to hold that line.

## Scope Note

**Alertmanager dispatch and silence management were not implemented.** The issue groups them with PromQL validation, but they are a separate integration against a different service with its own authentication, and nothing in the codebase currently sends alerts or manages silences. Building an unexercised dispatch path into an alerting system — where the failure mode is either a missed page or a spurious one — is not something to add speculatively. Pre-flight rule file verification is likewise deferred: it belongs with that work, since a rule file is only meaningful against the Alertmanager that will load it.
