# Tasks

## 1. The phases of the stage Job

Kind: behavior.

- [x] 1.1 Write failing tests: `prepare`, `agent` and `publish` in turn on one run folder publish the plan of `--phase all`; the agent phase refuses the App key and each GitHub token, and an output folder that is there already; `publish` refuses a link, a FIFO, an outcome over the limit or not of its model, a change with a file outside its folder and a state file of another item; a `prepare` that ends the Job gives `publish` its end; an agent phase past its time budget ends in the deadline; a phase needs `--job-item`, `--confirm` and `--work`; the command runs each phase in turn
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_job_phases.py`
- [x] 1.2 Split `plan_stage` into `begin_stage`, `store_reads` and `plan_targets`, add `StageWriter.resume`, `clone_staged`, `held_github_credentials` and the phases of `stage_job_phases.py`, run `run_stage_job` on them, and add `--phase` and `--work` to `devops roadmap stage`
  - Verification: `$ uv run devops ci test tests/roadmap/stage tests/roadmap/phases`

## 2. Documents

Kind: other.

- [x] 2.1 Describe the phases of the stage Job in `docs/roadmap/stage.md`, `docs/CLUSTER.md` and ADR 0030, and generate the command reference
  - Verification: `$ uv run devops ci docs`
