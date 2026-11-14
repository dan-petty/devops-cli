# Tasks

## 1. Behavior

- [x] 1.1 Add failing tests for toolchain presets and project profile resolution
  - Verification: `$ uv run pytest tests/roadmap/test_roadmap_project_profile.py`
- [x] 1.2 Implement `src/devops_cli/roadmap/toolchains.py` and `src/devops_cli/roadmap/project_profile.py`
  - Verification: `$ uv run pytest tests/roadmap/test_roadmap_project_profile.py`
- [x] 1.3 Update `scoped_checks`, `implement_step.py`, and `implement_run.py` to use toolchain presets
  - Verification: `$ uv run pytest tests/roadmap/implement/`
- [x] 1.4 Update `.devops/roadmap.toml` to declare `[project] toolchain = "devops-cli"` and remove `[implement.steps]`
  - Verification: `$ uv run pytest tests/invariants/`

## 2. Documents

- [x] 2.1 Update documentation and verify quality gates
  - Verification: `$ uv run devops ci --only lint,format,typecheck,docs`
