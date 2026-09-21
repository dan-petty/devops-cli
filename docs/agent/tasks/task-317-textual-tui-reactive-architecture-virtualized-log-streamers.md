# Task 317: Textual TUI Reactive Architecture, Virtualized Log Streamers & Component Decoupling Research

**Issue**: [#317](https://github.com/dan-petty/devops-cli/issues/317)
**PR**: [#361](https://github.com/dan-petty/devops-cli/pull/361)
**Status**: Done
**Milestone**: `v0.2.22`
**Priority**: `priority/p1-high`
**Scope**: `type/feature`, `scope/cli`, `priority/p1-high`

---

## 1. Description & Objectives

`DashboardApp.action_refresh_data` called five blocking provider functions in sequence
directly from the keypress handler and from the mount hook. The interface was therefore
unresponsive for the sum of five network round trips, and a single unreachable cluster
froze every unrelated tab for the duration of its timeout — including the key bound to
quitting. The five `_refresh_*` methods were also near-identical, each fetching, formatting
a banner, and populating a table addressed by widget id, so none of the rendering could be
exercised without running an app against live infrastructure.

### Key Deliverables Completed:

- [x] **Thread-Safe State Store (`src/devops_cli/ui/state.py`)**:
  - `DashboardState` owns the shared snapshots that workers publish and the UI reads.
  - Subscribers are notified *outside* the lock, so a slow listener cannot stall an
    unrelated worker that is merely trying to publish; a listener that raises is isolated
    rather than allowed to abort the publish.
  - `begin_refresh`/`finish_refresh` claims prevent a fixed-interval timer from stacking a
    new thread per tick against an endpoint that is already slow.
  - `DomainSnapshot` distinguishes *never loaded* from *stale*, since the two render
    differently and conflating them puts a staleness warning over a blank panel.
- [x] **Refresh Coordination (`src/devops_cli/ui/refresh.py`)**:
  - `refresh_domain` converts a provider failure into a published error snapshot. An
    exception escaping a worker thread would otherwise kill the refresh silently and leave
    the panel showing data that never updates again.
  - `pod_log_source` defers opening the log stream until it is consumed, so the blocking
    connect happens on the worker and never on the thread that wired it up.
- [x] **Pure Projections (`src/devops_cli/ui/projections.py`)**:
  - Banner text and table rows for all five domains as pure functions of their summary
    type, testable without constructing an app.
  - A failed refresh keeps the last retrieved rows beneath an error banner: a transient
    outage should dim the panel, not blank it.
- [x] **Domain-Isolated Widgets (`src/devops_cli/ui/widgets.py`)**:
  - `DomainPanel` declares its own columns and renders its own snapshot, replacing the
    five `_refresh_*` methods and the central column initialiser. The app now holds no
    per-domain rendering code at all.
  - `LogPane` tails a stream through a bounded buffer with scroll, page, and follow
    bindings.
- [x] **Virtualized Log Buffer (`src/devops_cli/ui/log_buffer.py`)**:
  - `VirtualLogBuffer` retains a fixed window and hands out only the visible slice, so both
    memory and per-frame work are bounded by the retention limit rather than by how long
    the tail has been running.
  - Sequence numbers count every line ever appended, so stream position stays true after
    eviction; scrolling back detaches from following so incoming lines do not yank the
    reader's position away.
  - Redraws are coalesced under a minimum interval: every line is retained, but a busy pod
    cannot schedule a repaint per line.
- [x] **Asynchronous Refresh**: `@work(thread=True)` per domain. Each panel renders as soon
  as its own fetch returns, so a fast subsystem is never held behind a slow one.
- [x] **Failure Confinement**: a projection that cannot render its data reports in that
  domain's own banner. Because the worker-to-UI hand-off runs on the UI thread, letting it
  propagate would take down a dashboard whose other four subsystems are healthy.
- [x] **Single Source of Truth**: tabs, bindings, panels, columns, fetchers and the CLI
  `--tab` map are all derived from `CONST_DASHBOARD_DOMAINS`. Adding a domain no longer
  requires edits in five places that can each be forgotten independently.
- [x] **Centralized Constants**: domain keys and labels, log retention and viewport sizes,
  redraw interval, refresh interval, staleness threshold.
- [x] **Automated Tests & Quality Gates**:
  - 124 tests in `tests/test_ui_reactive.py` using structural tuple equality assertions.
  - `state.py`, `log_buffer.py`, `projections.py`, `refresh.py` at **100%**;
    `widgets.py` **98%**; `dashboard.py` **99%**.
  - Cyclomatic complexity $M \le 10$ and nesting depth $\le 5$ across all new modules.
  - 100% passing status across Gated CI validation suite (`uv run devops ci`).

## Verification Results

- `uv run devops ci` — all gates pass (tests, coverage $\ge 90\%$, lint, format, mypy
  strict, audit, security, actionlint, docs, uv check, lockfile).
- The 17 pre-existing tests in `tests/test_ui_dashboard.py` pass unmodified, so the
  refactor preserved the tab ids, widget ids and CLI surface they assert on.

## Design Constraint: The Freeze Must Be Asserted, Not Assumed

The defect this task addresses is a *timing* property, and a refactor that merely looks
asynchronous can reintroduce it. Three tests therefore exercise it directly rather than
inspecting structure, each holding the providers open on an event the test controls so the
assertion is made while the fetch is genuinely still outstanding:

- `test_a_slow_subsystem_does_not_freeze_the_interface` blocks the Kubernetes provider and
  asserts the dashboard still switches tabs and renders the other four domains.
- `test_a_refresh_keypress_never_blocks_on_the_providers` times the handler against
  providers that have not returned.
- `test_redraws_are_coalesced_under_a_fast_stream` asserts a 2000-line burst schedules at
  most three repaints.

A synchronous implementation fails the first two by construction, since the assertions run
while the providers are still blocked and a synchronous refresh could not have returned.

## Scope Note

**Command palette integration was not implemented.** Textual supplies a palette already,
and the useful commands it would carry — switch tab, refresh, tail a pod — are all bound to
single keys and shown in the footer. Adding a second way to reach them is surface area
without a behaviour change, so it was left out in favour of the blocking-I/O and log
virtualization work the issue identifies as the actual defects.
