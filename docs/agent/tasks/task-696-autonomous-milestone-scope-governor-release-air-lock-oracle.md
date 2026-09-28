# Task 696: Autonomous Milestone Scope Governor & Release Air-Lock Oracle (`devops gh pm governor`)

**Issue**: [#696](https://github.com/dan-petty/devops-cli/issues/696)
**Status**: Backlog
**Milestone**: `v0.2.24`
**Priority**: `priority/p1-high`
**Scope**: `type/feature`, `scope/github`, `priority/p1-high`

---

## 1. Description & Objectives

Autonomous AI coding agents operating continuously in repositories naturally exhibit the "Milestone Horizon Inflation Trap" and recursive scope cascades: as agents explore codebases and implement features, they uncover adjacent bugs, secondary refactorings, and edge cases, opening new issues directly into the active release milestone. If unconstrained, this causes milestone issue count to monotonically expand (e.g. `v0.2.23` ballooning to 196 tracked items with 29 open issues remaining at release candidate cutoff), trapping the milestone completion percentage in a permanent 70%–85% asymptotic band despite hundreds of closed issues.

#### Key Deliverables:
- Context & Rationale*: Autonomous AI coding agents operating continuously in repositories naturally exhibit the "Milestone Horizon Inflation Trap" and recursive scope cascades: as agents explore codebases and implement features, they uncover adjacent bugs, secondary refactorings, and edge cases, opening new issues directly into the active release milestone. If unconstrained, this causes milestone issue count to monotonically expand (e.g. `v0.2.23` ballooning to 196 tracked items with 29 open issues remaining at release candidate cutoff), trapping the milestone completion percentage in a permanent 70%–85% asymptotic band despite hundreds of closed issues.
- Deep Integration & Functional Extension*: Native CLI command (`devops gh pm governor`) and FastMCP tool (`milestone_governor`) implementing mathematical scope convergence tracking:
- Velocity & Convergence Ratio ($C_R$)**: Measures Scope Injection Velocity ($V_{\text{scope}} = \Delta I_{\text{created}} / \Delta t$) against Burn-Down Velocity ($V_{\text{burn}} = \Delta I_{\text{closed}} / \Delta t$) over configurable rolling windows. Flags release live-lock when $C_R = V_{\text{burn}} / V_{\text{scope}} \le 1.0$ or when estimated days to convergence becomes indefinite.
- Lifecycle Phase Invariant Gating**: Enforces formal milestone phases: `INTAKE` (unrestricted feature exploration), `AIR_LOCKED` (release stabilization admitting exclusively P0 critical blockers), `FROZEN` (release candidate stabilization where any remaining open item must be resolved or rolled over), and `CLOSED`. Emits diagnostic rules `MLS001` (ScopeExpansionLiveLock), `MLS002` (AirLockBoundaryBreach), `MLS003` (MegaMilestoneSizingAlert for $>50$ and $>100$ issues), and `MLS004` (StagnantHorizonRatchet).
- Automated Rollover Partitioning & Actionable Triage**: Partitions active milestone issues into retained release blockers vs. rollover candidates, generating rate-paced `issue edit` commands or batch migrations to the subsequent release milestone (`vNext`).
- OASIS SARIF 2.1.0 & Structured JSON Export**: Emits machine-readable SARIF diagnostic reports for automated GitHub Actions CI gating (`devops ci` or PR sentinel) and ASCII completion burndown graphs in terminal output.
- Code Optimization & Performance Acceleration*: Port and integrate the core governor oracle from `repos/dan-petty/vibes/tools/milestone_governor.py` into `src/devops_cli/github/milestone_governor.py`; route all GitHub API inspections and issue transitions through rate-limited `run_gh` token buckets to prevent secondary rate-limit penalties.
- Refactoring Potential & Legacy Elimination*: Seamlessly binds with `devops gh pm inflight`, `devops release prepare`, and `devops dashboard` (`tab-github`), replacing ad-hoc manual milestone pruning and unbounded agent issue sprawl with mathematical, self-governing air-locks.
- Unit and integration test coverage with structural tuple equality assertions.
- Maintain cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
- 100% passing across Gated CI validation suite (`uv run devops ci`).
