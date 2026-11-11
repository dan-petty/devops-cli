# Tasks

## 1. The registry and the resolver chain

Kind: behavior. Reads: `src/devops_cli/roadmap/decision_step.py`, `src/devops_cli/roadmap/decision_fit.py`, `tests/support/fakes/jev.py`. Changes: `src/devops_cli/roadmap/decision_point.py` (new), `src/devops_cli/roadmap/decision_registry.py` (new), `src/devops_cli/roadmap/decision_step.py`, `src/devops_cli/telemetry/instruments.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_decision_point.py` (new), `tests/roadmap/test_roadmap_limit_classes.py`.

- [x] 1.1 Write failing tests: the chain asks a proven rule first and sends no request; the model answers in `on` and in `shadow` with one record and one count; an error, a missing answer and a secret fall back with the resolver `fallback` and the band `none`; an empty `ai.decision_model` gives no chain; the registry refuses an unknown key, `on` for a point with no cuts file (naming the point and the file) and a catalogue above 60 series; the join gives the labelled cases and the decisions with no outcome
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_decision_point.py`
- [x] 1.2 Build `DecisionPoint`, `ResolverChain`, `chain_of`, the records, `join`, `Registry` and `REGISTRY` on `decision_step.py` and `decision_fit.py`; add `model_name` to `decide_all`; add the counter `devops_cli_decision_point_total`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_decision_point.py tests/roadmap/test_roadmap_decision_step.py`

## 2. The settings

Kind: behavior. Reads: `src/devops_cli/config/settings.py`, `src/devops_cli/ai/pydantic_ai_bridge.py`. Changes: `src/devops_cli/config/settings.py`, `src/devops_cli/config/defaults.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/ai/pydantic_ai_bridge.py`, `tests/config/test_decision_point_settings.py` (new), `tests/security/test_config_declarations.py`.

- [x] 2.1 Write failing tests: `ai.decision_model` takes a System One name and refuses a chat model; `roadmap.decisions` takes a JSON object from its variable, refuses a value that is no object, refuses a key that names no point and accepts `shadow` and `on` for `stage.verify_screen`; a file that still holds the removed key `roadmap.stage.jev_screen` loads, and the point stays off
  - Verification: `$ uv run devops ci test tests/config/test_decision_point_settings.py`
- [x] 2.2 Add `ai.decision_model` and `roadmap.decisions` with their validators, and let the model bridge use the same check of a System One name
  - Verification: `$ uv run devops ci test tests/config/test_decision_point_settings.py tests/security/test_config_declarations.py`

## 3. The verify screen on the registry

Kind: behavior. Reads: `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/roadmap/stage/stage_screen_eval.py`. Changes: `src/devops_cli/roadmap/stage/stage_jev_screen.py`, `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/roadmap/stage/stage_screen_eval.py`, `src/devops_cli/roadmap/stage/jev_screen_cuts.json`, `src/devops_cli/config/settings.py`, `src/devops_cli/config/defaults.py`, `src/devops_cli/telemetry/instruments.py`, `tests/roadmap/stage/test_roadmap_stage_jev_screen.py`.

- [x] 3.1 Write failing tests: the screen is the registered point `stage.verify_screen` with the cuts of `jev_screen_cuts.json`; with no decision model the review runs and nothing is asked or counted; in `shadow` the review runs, and one count, one decision record and one outcome record name the band and the result; in `on` the band continue skips the review and an error of the model runs it
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_jev_screen.py`
- [x] 3.2 Make `VERIFY_SCREEN` a `DecisionPoint`, give the stage job its chain and its outcome record, and remove `JevScreener`, `ScreenMode`, `roadmap.stage.jev_screen` and the two old counters
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_jev_screen.py tests/roadmap/stage/test_roadmap_stage_screen_eval.py`
- [x] 3.3 Confirm that the golden replay and the stored screen report give the numbers of the base
  - Verification: `$ uv run devops roadmap eval stage --replay`

## 4. Documents

Kind: other. Changes: `docs/roadmap/stage.md`, `CONTEXT.md`, `k8s/devops/configmap.example.yaml`, `docs/ENV_VARS.md`, `docs/CONFIGURATION.md`, `docs/TELEMETRY.md`.

- [x] 4.1 Describe the point `stage.verify_screen`, its settings and its records in `docs/roadmap/stage.md`, add the term decision point to `CONTEXT.md`, put `roadmap.decisions` in the example ConfigMap, and generate the reference documents
  - Verification: `$ uv run devops ci docs`

## Workflow follow-up

- `stage.explore_stop` registers in #4399. The registry then refuses its mode `on` until its cuts file is in the repository (#4410).
- The intake labels move onto the registry after #4395, and the extension of the implement budget after #4394.
- Pending a person: add `roadmap.decisions` to the live ConfigMap at any time. After the image of this change runs, add `ai.decision_model` and remove `roadmap.stage.jev_screen`, in the order of the pull request comment.
- #4446 puts `ai.decision_model` in the ConfigMap template after the image of this change runs, so that `deploy-stack` keeps it.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
