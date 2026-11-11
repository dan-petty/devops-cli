# Proposal: #4501

## Why
When `roadmap.decisions` is not empty, the validator `_check_decisions` of `RoadmapConfig` imports `devops_cli.roadmap.decision_registry`. The registry imports `decision_point` and `stage.stage_jev_screen`, and both import `pydantic_ai.models.decision`. Thus a light command such as `devops config get ai.provider` imports 1403 modules in place of 816, and pydantic_ai is one of them. The runner Jobs, the Service and the MCP server load a ConfigMap that sets the key, so each `devops` start pays this cost. The `startup-imports` row does not set the key, so it does not find the cost. Closes #4501.

## What Changes
- A new module `devops_cli.roadmap.decision_table` holds `POINT_CUTS`, a table of the name and the cuts file of each registered point, and `check_modes`, which refuses a key that names no point and the mode `on` for a point with no cuts file. It imports only `devops_cli.lang`.
- `RoadmapConfig._check_decisions` calls `check_modes`, and it does not import the registry.
- `Registry.check` and its path helper go out of `decision_point.py`, because no caller is left. Their tests move to `tests/roadmap/test_roadmap_decision_table.py`.
- A test keeps `POINT_CUTS` equal to the names and cuts files of `REGISTRY`.
- The `startup-imports` row gets a probe that loads a config file with `roadmap.decisions` set and fails when the load imports pydantic_ai.
- The import set of a command is observable through the `startup-imports` row and the start time, so the change has deltas on `decision-workflows` and `ci-gate-rows`.

## Capabilities
- Modified: `decision-workflows`, `ci-gate-rows`.

## Impact
- `src/devops_cli/roadmap/decision_table.py`, `src/devops_cli/roadmap/decision_point.py`, `src/devops_cli/roadmap/decision_registry.py`, `src/devops_cli/config/settings.py`, `tests/gate/startup_imports.py`, `tests/roadmap/test_roadmap_decision_table.py`, `tests/roadmap/test_roadmap_decision_point.py`.
- The messages of a refused key and of `on` with no cuts do not change.
- A new decision point must also go into `POINT_CUTS`. The table test fails until it does.
- The change fits one pull request.

## Feasibility
- Source on `main` at 5f75d256: `_check_decisions` in `src/devops_cli/config/settings.py` runs `from devops_cli.roadmap.decision_registry import REGISTRY`. `decision_point.py` and `stage/stage_jev_screen.py` import `pydantic_ai.models.decision` at module level.
- Command output on 7234d718, with `DEVOPS_CLI_CONFIG` set and `python -X importtime -c 'from devops_cli.entry import main; main()' config get ai.provider`: 816 modules with no `roadmap.decisions`, 1403 modules and pydantic_ai with `roadmap.decisions: {stage.verify_screen: shadow}`.
- The new probe of the `startup-imports` row gives `[true, {"stage.verify_screen": "shadow"}]` on the base, so it fails. With the change it gives `[false, ...]` and 817 modules.

## Existing Tool Considered
- No open tool or library covers this need: it is an import boundary inside this project. The standard answer is a static table that the validator imports alone, kept equal to the full registry by a test. The change builds a module of about 50 lines: about 3,000 tokens to build, 1,000 tokens to keep and fix, and 2 hours of elapsed time.
- The change deletes `Registry.check`, `_shown` and `_SHOWN_FROM` of `decision_point.py`.
