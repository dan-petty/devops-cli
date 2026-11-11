# Proposal: #4397

## Why

ADR 0020 makes a decision point the unit of design of a decision model in a workflow, with a resolver chain: a proven rule, then the decision model, then the current behavior. The code has no such unit (#4397). The verify screen (`src/devops_cli/roadmap/stage/stage_jev_screen.py`, #4282) has its own mode setting `roadmap.stage.jev_screen`, its own two counters and its own log lines. It asks `typesafe/jev-1.14` from a constant, so no setting says which decision model a workflow uses. The shared parts in `decision_step.py` and `decision_fit.py` give the cuts, the bands and the fit, but no registry, no resolver chain, no record of a decision and no join with its real outcome.

## What Changes

- A typed registry of decision points (`src/devops_cli/roadmap/decision_point.py`, `src/devops_cli/roadmap/decision_registry.py`). It is built on `Band`, `Thresholds`, `band_of` and `decide_all` of `decision_step.py` and on `FitCase` of `decision_fit.py`. An entry holds the name `<area>.<what>`, the fixed questions, the evidence builder, the three action bands, the path of the cuts file, the rule (when one is proven) and whether the point asks the model.
- The resolver chain: the rule of the point, then the decision model when `ai.decision_model` is set and the mode of the point is `shadow` or `on`, then the current behavior. An error, a timeout, a missing answer, a missing cut or a digest that holds a secret falls back. With `ai.decision_model` empty, a point with no rule makes no request, writes no record and no series, and the workflow is the same as before.
- The settings. `ai.decision_model` (variable `DEVOPS_CLI_AI_DECISION_MODEL`) names the decision model; empty is the default, and a name that is not a System One model stops the load. `roadmap.decisions` (variable `DEVOPS_CLI_ROADMAP_DECISIONS`, a JSON object) maps a point name to `off`, `shadow` or `on`. A key that names no registered point stops the load. The registry refuses `on` for any point that has no fitted cuts file in the repository, and the error names the point and the file. This is the general rule that #4410 asks for `stage.explore_stop`.
- One counter, `devops_cli_decision_point_total` (labels `point`, `resolver`, `band`, `mode`). It replaces `devops_cli_roadmap_decision_step_total` and `devops_cli_roadmap_decision_step_review_total`. The registry refuses a catalogue of more than 60 series. The one point of the registry today has 8.
- One decision record and one outcome record for each decision, as log lines with the same identifier, and a pure function that joins them into the labelled cases of the next fit.
- The verify screen becomes the point `stage.verify_screen`. Its mode is `roadmap.decisions["stage.verify_screen"]`, and the setting `roadmap.stage.jev_screen`, the class `JevScreener` and the two old counters go. The digest, the nine questions and the cuts file stay. The review writes the outcome record. The cuts file names the point.
- The client of the decision model: `decide_all` takes the model name, so the registry asks the model of `ai.decision_model`. The check of a System One model name moves to the settings and the model bridge uses it, so one rule decides both.

The setting, the variable, the counter and the behavior of the Service change, so the change has a spec delta.

## Capabilities

- `decision-workflows`: ADDED the variables of the two settings.
- `roadmap-stage`: MODIFIED the requirements of the Jev screen and of its fail-open rule, which now name the point and the registry.

## Impact

- The live ConfigMap holds `roadmap.stage.jev_screen: shadow`. `RoadmapStageConfig` ignores an unknown key, so the old key does not stop the load of the new image, and the change removes the setting in one step. `AIConfig` refuses an unknown key, so `ai.decision_model` goes into the ConfigMap only after the new image runs. Until then the screen makes no request, and the review runs as it does in `shadow` today. The pull request comment gives the exact lines and their order.
- The intake labels (#4395) and the extension of the implement budget (#4394) stay on their own settings. Their migrations are later items of ADR 0020.
- The golden eval of the stage gates and the stored report of `devops roadmap eval screen` give the same numbers as before.

## Feasibility

- `RoadmapConfig` and `RoadmapStageConfig` set `extra="ignore"` and `AIConfig` sets `extra="forbid"` (`src/devops_cli/config/settings.py`). So the old key `roadmap.stage.jev_screen` in the live ConfigMap is ignored by the new image, and `ai.decision_model` stops the load of an image that does not know it.
- `resolve_pydantic_ai_model` builds a `SystemOneModel` for a name that `_is_jev_model_str` accepts (`typesafe/jev-…`, `jev-…`, or a `typesafe:` or `system-one:` prefix), and `create_jev_model(model_name, settings=...)` takes the name (`src/devops_cli/ai/jev.py`). So `ai.decision_model` reaches the gateway route by name with no new client.
- `decide_all` sends one request for each piece of evidence and raises any error, and `FAILED` names the errors of a request (`src/devops_cli/roadmap/decision_step.py`). The fake of the Jev edge (`tests/support/fakes/jev.py`) answers a `SystemOneModel` with no socket.
- The baselines before the change, in this worktree at `origin/main` `1ca0133a`: `uv run devops roadmap eval stage --replay` gives 81 of 317 defects caught by a gate, 0 missed, and 5 of 5 good plans accepted. `uv run devops roadmap eval screen --from .data/roadmap_eval/screen/20261110T043616Z.json` gives the oracle 9 of 48 (19%), and the shared cut skips 1 of 23 and 1 of 25 reviews on the halves that were not fitted, with 0 serious defects lost.

## Existing Tool Considered

pydantic_ai `DecisionModel` and `SystemOneModel` are the client, and the existing `decision_step.py` and `decision_fit.py` give the cuts, the bands, the requests and the fit. OpenFeature (`open-feature/python-sdk`) evaluates a named flag with a mode, but it has no fitted-cut precondition, no question set, no evidence builder and no outcome join, and the mode is one field of the settings that pydantic already validates. No open library gives a resolver chain of a rule and a calibrated decision model. The build is two small modules on the existing parts: about 25,000 tokens to build with the tests, about 4,000 tokens for each later fix, and about one day of elapsed time. The change deletes `JevScreener`, `ScreenMode`, `ScreenResult`, `result_of`, `screener_of`, `DECIDING`, the setting `roadmap.stage.jev_screen`, the type `StageJevScreen` and its default, and the two counters of the decision step.

The change fits one pull request.
