# Tasks

## 1. The Service image runs the pinned OpenSpec

- [x] 1.1 Add the three tests of the service stage to `tests/invariants/test_service_image.py` (OpenSpec from the lockfile on `PATH`, telemetry off, Node of the major in `.node-version`), and verify that `uv run devops ci test tests/invariants/test_service_image.py` fails on the base
- [x] 1.2 Add the `node` stage, the install in the builder stage, the copies and the environment to `Dockerfile`, and the `openspec --version` line to the smoke test in `.github/workflows/ci.yml` and `.github/workflows/release.yml`, and verify that `uv run devops ci test tests/invariants/test_service_image.py` passes and that `docker build --target service .` runs `openspec --version` as user 1000
- [x] 1.3 Run `devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## 2. The settings of the stage job

- [x] 2.1 Write `tests/test_roadmap_stage_settings.py` (the defaults, the config file, the variable, an invalid entry, the command taking the settings, the options replacing them) and add the two variables to `tests/test_config_declarations.py`, and verify that `uv run devops ci test tests/test_roadmap_stage_settings.py` fails on the base
- [x] 2.2 Add `stage_filter.py`, the settings `roadmap.stage.filter` and `roadmap.stage.limit` with their defaults, and the settings fallback in `devops roadmap stage`, and verify that `uv run devops ci test tests/test_roadmap_stage_settings.py tests/test_roadmap_stage_selection.py tests/test_config_declarations.py` passes
- [x] 2.3 Run `devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## 3. The row and the metric

- [x] 3.1 Write the due-table tests in `tests/test_roadmap_run.py` (first run, interval, refine set an item Ready, refine set none, the dry run lists `stage`, the module-level import of the stage module) and `tests/test_roadmap_stage_job.py` (a round plans with the settings, writes, fails for a failed item, and counts each item once by its result), and `tests/test_roadmap_refine.py` (the refine job reports `set_ready`), and verify that `uv run devops ci test tests/test_roadmap_run.py tests/test_roadmap_stage_job.py tests/test_roadmap_refine.py` fails on the base
- [x] 3.2 Add the row, `JobOutcome.set_ready`, the runner, `DEFAULT_ROADMAP_STAGE_INTERVAL_MINUTES`, `ROADMAP_STAGE_TOTAL` and `emit_stage_results`, and verify that `uv run devops ci test tests/test_roadmap_run.py tests/test_roadmap_stage_job.py tests/test_roadmap_refine.py tests/test_telemetry_instruments.py` passes
- [x] 3.3 Run `devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

- [x] 3.4 Write the tests for a refine round that sets an item Ready and fails another (`tests/test_roadmap_run.py`, `tests/test_roadmap_refine.py`), carry `readied_count` in `RoadmapRefineError`, and verify that `uv run devops ci test tests/test_roadmap_run.py tests/test_roadmap_refine.py` passes

## 4. The documents

- [x] 4.1 Name the row, the settings and the metric in `CONTEXT.md` ("Lane"), `k8s/README.md` ("Roadmap service") and `k8s/devops/configmap.example.yaml`, and verify that `uv run devops ci test tests/test_k8s_configmap.py tests/test_k8s_roadmap_service.py` passes
- [x] 4.2 Run `devops docs generate --sync-readme`, and verify that `uv run devops ci` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
