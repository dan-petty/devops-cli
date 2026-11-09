# Tasks

## 1. Test the slot of the trial

Reads: `k8s/devops/configmap.example.yaml`, `k8s/llm/gateway/config.yaml`. Changes: `tests/config/test_k8s_devops_runtime.py`, `tests/k8s/test_k8s_configmap.py`, `tests/roadmap/stage/test_roadmap_stage_window.py`.

- [x] 1.1 Add `test_the_analysis_slot_is_the_sonnet_trial_and_every_other_chat_slot_is_deepseek` and `test_the_comment_above_the_analysis_slot_names_the_reason_the_cost_and_the_way_back` to `tests/config/test_k8s_devops_runtime.py`. They read the template: `analysis` and `stage` name `claude-sonnet-5-5` with 200000, every other chat slot names `deepseek-v4.1-flash-1017`, and the comment above `analysis` names #4204, 2026-11-09, 0.27 USD, 3 items, 37 minutes and #3874
  - Verification: `$ uv run devops ci test tests/config/test_k8s_devops_runtime.py` passes once group 2 is done; both tests fail on the base tree
- [x] 1.2 Change `test_every_chat_model_slot_of_the_rendered_template_names_one_hosted_group_but_analysis` in `tests/k8s/test_k8s_configmap.py` to the rule with the one exception `analysis`
  - Verification: `$ uv run devops ci test tests/k8s/test_k8s_configmap.py` passes once group 2 is done; the test fails on the base tree
- [x] 1.3 Change `tests/roadmap/stage/test_roadmap_stage_window.py`: the window of `analysis` is 200,000 and the gateway window is 1,000,000, and the test of the shared model and window says that the review keeps DeepSeek and 256,000 while the planner runs Sonnet
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_window.py` passes once groups 2 and 3 are done; the changed tests fail on the base tree

## 2. Name Sonnet in the template

Reads: `k8s/devops/configmap.example.yaml`. Changes: `k8s/devops/configmap.example.yaml`.

- [x] 2.1 Set `analysis` to `model: claude-sonnet-5-5` and `context_window: 200000` in `k8s/devops/configmap.example.yaml`, with the comment of the trial (reason #4204, owner decision of 2026-11-09, about 0.27 USD for each stage case at the sample of #3566, up to 3 items for each 37 minutes of the stage row, undo when the rule of #3874 applies again). Fix the header comment of the model block and the comment of `verification`, which name one model for every slot and the same window as `analysis`
  - Verification: `$ uv run devops ci test tests/config/test_k8s_devops_runtime.py tests/k8s/test_k8s_configmap.py tests/k8s/test_k8s_configmap_keys.py tests/roadmap/stage/test_roadmap_stage_window.py tests/roadmap/test_roadmap_limit_classes.py`
- [x] 2.2 Read the live ConfigMap and the rendered template and compare the key `ai.tasks.analysis`
  - Verification: the read-only `kubectl -n devops get configmap devops-cli-config -o yaml` shows `claude-sonnet-5-5` and `200000` for `ai.tasks.analysis`, the same values as the template; apply nothing

## 3. Fix the documents

Reads: `k8s/README.md`, `docs/roadmap/stage.md`, `SECURITY.md`, `openspec/specs/roadmap-service-deployment/spec.md`. Changes: `k8s/README.md`, `docs/roadmap/stage.md`, `SECURITY.md`.

- [x] 3.1 Edit item 19 of `k8s/README.md` and the sentence on `analysis` near line 674: `analysis` is Sonnet with 200,000 tokens, the other chat slots are DeepSeek, and `claude-sonnet-5-5` serves the slot `analysis`
  - Verification: `$ ! git grep -n "claude-sonnet-5-5. serves no slot" -- k8s/README.md SECURITY.md`
- [x] 3.2 Edit `docs/roadmap/stage.md`: the window of the task `stage` is 200,000 tokens, the limit is 150,000, and the model is Sonnet with 1,000,000
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_window.py`
- [x] 3.3 Edit rule 13 of `SECURITY.md`: the prompts of `analysis` leave the cluster to Anthropic, and the other chat slots to OpenRouter
  - Verification: `$ uv run devops ci docs`
- [x] 3.4 Check the changed spec
  - Verification: `$ uv run devops openspec check`

## Criteria

- Group 1: A new test in `tests/config/test_k8s_devops_runtime.py` asserts `claude-sonnet-5-5` and `200000` for `ai.tasks.analysis` and DeepSeek for the other chat slots, and it fails on the base tree; the test of `tests/k8s/test_k8s_configmap.py` takes the exception `analysis`.
- Group 2: The template names `claude-sonnet-5-5` and `context_window: 200000` for `ai.tasks.analysis` with the comment that the issue asks for, and the live ConfigMap shows no drift for that key.
- Group 3: The spec `roadmap-service-deployment`, `k8s/README.md` and `docs/roadmap/stage.md` name the slots as they are, and `git grep -n "256000\|256,000" -- k8s/README.md docs/roadmap/stage.md` shows only the windows that still hold.
