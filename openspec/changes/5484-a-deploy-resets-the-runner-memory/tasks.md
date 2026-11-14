# Tasks

## 1. Put the runner memory limit in the example ConfigMap

Kind: other. Reads: `k8s/devops/configmap.example.yaml`, `tests/k8s/test_k8s_configmap_keys.py`, `src/devops_cli/k8s/configmap.py`. Changes: `k8s/devops/configmap.example.yaml`, `tests/k8s/test_k8s_configmap_keys.py`, `tests/ai/benchmark/test_k8s_llm_gateway.py`, `tests/ai/spend/test_hosted_group_prices.py`, `tests/invariants/test_workflow_contracts.py`, `tests/k8s/test_k8s_configmap.py`, `tests/k8s/test_k8s_valkey_stack.py`, `tests/roadmap/implement/test_roadmap_implement_step_classes.py`, `tests/roadmap/stage/test_roadmap_stage_settings.py`, `tests/roadmap/stage/test_roadmap_stage_submit.py`, `tests/roadmap/stage/test_roadmap_stage_window.py`, `tests/roadmap/test_roadmap_limit_classes.py`, `tests/server/routes/test_k8s_roadmap_service.py`.

- [ ] 1.1 Add the case `test_the_example_holds_the_runner_memory_limit` to `tests/k8s/test_k8s_configmap_keys.py` first: render the example through `_example_config()` and assert that `config["roadmap"]["implement"]["max_memory_limit"]` is `16Gi`, then read the template text and assert that the comment above the setting names 2026-11-12, 2026-11-13 and the two killed Jobs. It fails while the template sets nothing. Then add `max_memory_limit: 16Gi` under `roadmap.implement` in `k8s/devops/configmap.example.yaml`, after `ladder`, with that comment. Edit one of the other listed test modules only when the new setting breaks it, and keep each such edit to that failure
  - Verification: `$ uv run devops ci test tests/k8s/test_k8s_configmap_keys.py` passes

## 2. Name the node that bounds the limit in the setting description

Kind: behavior. Reads: `src/devops_cli/config/settings.py`, `tests/roadmap/implement/test_roadmap_implement_size.py`. Changes: `src/devops_cli/config/settings.py`, `tests/roadmap/implement/test_roadmap_implement_size.py`.

- [ ] 2.1 `test_the_description_names_the_smallest_node_that_can_run_a_runner_job` in `tests/roadmap/implement/test_roadmap_implement_size.py`
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_size.py` fails on the base
- [ ] 2.2 Write the case first: read `settings.RoadmapImplementConfig.model_fields["max_memory_limit"].description` and assert that it holds `smallest node that can run a runner Job` and not `smallest node of the cluster`. It fails on the staged description. Then change the `description` of `max_memory_limit` in `src/devops_cli/config/settings.py` so the bound is the smallest node that can run a runner Job, and keep the pattern and the default as they are
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_size.py` passes

## 3. Regenerate the environment variable table from the new description

Kind: other. Reads: `docs/ENV_VARS.md`, `src/devops_cli/config/settings.py`. Changes: `docs/ENV_VARS.md`.

- [ ] 3.1 Run `uv run devops docs generate` with no option, so the row of `DEVOPS_CLI_ROADMAP_IMPLEMENT_MAX_MEMORY_LIMIT` in `docs/ENV_VARS.md` holds the new description of the setting, and keep no other change of the generator
  - Verification: `$ uv run devops docs check` passes
- [ ] 3.2 Edit `docs/ENV_VARS.md` with the output of `uv run devops docs generate`
  - Verification: `$ uv run devops ci docs` passes

## 4. State both limits in the Size line of the cluster document

Kind: other. Reads: `docs/CLUSTER.md`, `tests/config/test_k8s_devops_runtime.py`, `k8s/devops/configmap.example.yaml`. Changes: `docs/CLUSTER.md`, `tests/config/test_k8s_devops_runtime.py`.

- [ ] 4.1 Add the case `test_the_size_section_names_the_default_and_the_example_limit` to `tests/config/test_k8s_devops_runtime.py` first: read the Size line of `docs/CLUSTER.md` and assert that it holds `8Gi` and `16Gi`; it fails until the sentence is there. Then state in that line that the example ConfigMap sets `16Gi`, with the two kills of 2026-11-12 and 2026-11-13 as the reason and #5484
  - Verification: `$ uv run devops ci test tests/config/test_k8s_devops_runtime.py` passes
- [ ] 4.2 Edit `docs/CLUSTER.md` so the Size line states the default 8Gi and the 16Gi of the example ConfigMap
  - Verification: `$ uv run devops ci docs` passes

## Criteria

- Group 1: A test proves that the rendered ConfigMap holds `max_memory_limit: 16Gi`.
- Group 3: `uv run devops docs check` passes with the new default text.
- Pending person: Live proof after the merge: after `devops k8s deploy-stack --stack devops`, the live ConfigMap still holds `16Gi`., It needs the cluster and a deploy of the merged commit. The runner pod holds no Kubernetes token, no test reaches the cluster, and only a person runs the deploy and the read of the live ConfigMap.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
