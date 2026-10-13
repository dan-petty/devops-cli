# Task 1126: Roadmap Job Tallies Release Growth and Agent Quota

**Issue**: [#1126](https://github.com/dan-petty/devops-cli/issues/1126)
**Status**: Done
**Milestone**: `v0.2.35`
**Priority**: `priority/p2-medium`
**Scope**: `type/feature`, `scope/telemetry`, `scope/github`, `priority/p2-medium`
**Feasibility**: Verified against `reprioritize.py` (decision lifecycle, `JobMark`, transitions, run record), `store.py` (JobMark, Item), `github_store.py` (_JOB_RECORD_KEYS), `telemetry/instruments.py` (InstrumentKind.GAUGE), `metrics.py`, `dashboards/project-metrics.json`, and `test_roadmap_lifecycle_properties.py`.

---

## 1. Description & Objectives

Most of a release's items join it after it starts. `devops roadmap reprioritize` now records a durable ledger of joins, descopes, and trims on each item's job record in a `Tally` mark, and records a 10-release start size history in `Sizes` on the run record. A pure read model `release_growth` categorizes decisions into four groups (`joined`, `descoped`, `start`, `kept`), which are reported in the CLI reprioritize plan, exposed via MCP, emitted as Prometheus/OTLP gauges on command execution, and visualized in the *Project & Engineering Velocity* Grafana dashboard in a new *Release growth* row.

#### Key Deliverables:
- In `src/devops_cli/roadmap/store.py`:
  - Add `JobMark.TALLY = "Tally"` and `JobMark.SIZES = "Sizes"`.
- In `src/devops_cli/roadmap/github_store.py`:
  - Add `JobMark.TALLY` and `JobMark.SIZES` to `_JOB_RECORD_KEYS` to ensure round-trip preservation.
- In `src/devops_cli/roadmap/reprioritize.py`:
  - Implement `_TallyEntry` and `_TALLY_ADAPTER` using Pydantic `TypeAdapter`.
  - Update `_final_marks` to append a tally entry `[milestone_number, reason]` (with optional `"critical_fix"` or `"person"` discriminator) for non-silent transitions.
  - Update run record writes at start or first run to record `Sizes` mapping (last 10 releases).
  - Implement pure read model function `release_growth(items, run_record, releases)` classifying reasons into `joined`, `descoped`, `start`, and `kept`.
  - Add "Release growth" section to `render_plan` and `reprioritize` output for current and previous release using strings from `MESSAGES.roadmap`.
  - Emit OTLP gauges `devops_cli_roadmap_release_size_at_start` and `devops_cli_roadmap_release_decisions` following standard telemetry skip conditions.
- In `k8s/monitoring/dashboards/project-metrics.json`:
  - Add a "Release growth" row with panels querying `devops_cli_roadmap_release_size_at_start` and `devops_cli_roadmap_release_decisions` via `last_over_time`.
  - Verify zero errors with `devops grafana dashboards lint`.
- In `tests/test_roadmap_lifecycle_properties.py`:
  - Add lifecycle machine invariant `tally_matches_reason_comments` asserting each item's `Tally` entry count matches the job's reason comments.
- In `tests/test_roadmap_reprioritize.py`:
  - Add comprehensive unit tests covering ledger durability, fault stopping, person joins, read model group coverage, plan rendering, and telemetry emissions.
- In `docs/TELEMETRY.md` and `CONTEXT.md`:
  - Define `**Release growth**:` in `CONTEXT.md` and regenerate CLI docs via `devops docs generate --sync-readme`.
- Cyclomatic complexity $M \le 10$ and nesting depth $\le 5$ maintained.
- 100% passing across Gated CI validation suite (`uv run devops ci`).

## 2. Acceptance Criteria
- [x] Criterion 1: Ledger on the item (`Tally` mark): `_final_marks` appends `[release, reason]` or `[release, reason, "critical_fix"]` / `[release, reason, "person"]` to `Tally` mark via Pydantic `TypeAdapter`. Decisions with `KEEP` or `START_NEXT` add no entry. Dropped changes add no entry. Two changes in one run add two entries. Entries name releases by milestone number. Round-trips through GitHub adapter's job-record encoding with 50 entries.
- [x] Criterion 2: Size history (`Sizes` mark): At start or first run, the run record write sets `Sizes` holding up to 10 releases' start sizes in a single write.
- [x] Criterion 3: Lifecycle machine invariant: Machine gains invariant verifying that each item's `Tally` entry count equals the reason comments posted on it, and every entry contains a valid milestone number and `Reason`.
- [x] Criterion 4: Read model (`release_growth`): Pure public function returns size at start and counts across `joined`, `descoped`, `start`, and `kept`. Test verifies all non-silent `Reason` members are mapped to exactly one group.
- [x] Criterion 5: Report: `devops roadmap reprioritize` and MCP tool output a "Release growth" section for current and previous release using `MESSAGES.roadmap`.
- [x] Criterion 6: Gauges: Emits `devops_cli_roadmap_release_size_at_start` and `devops_cli_roadmap_release_decisions` gauges with standard skip conditions.
- [x] Criterion 7: Dashboard: *Project & Engineering Velocity* dashboard gains "Release growth" row with valid PromQL panels, passing `devops grafana dashboards lint`.
- [x] Criterion 8: Documentation & terms: `CONTEXT.md` defines **Release growth** and `docs/TELEMETRY.md` updated.
- [x] Criterion 9: All tests run offline, test duration under budget, and `uv run devops ci` passes 100%.
- Pending a person: once the board is migrated, run `devops roadmap reprioritize` against it without `--confirm`. Check that the plan shows the "Release growth" section and that the dashboard row shows the current release's size at start. After the next start, check that the previous release's numbers are still shown.
- [x] Changelog fragment authored at `changelog.d/1126.md`.
