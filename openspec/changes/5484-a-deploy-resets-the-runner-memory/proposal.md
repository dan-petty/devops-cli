# Proposal

## Why

Each `devops k8s deploy-stack --stack devops` renders ConfigMap `devops-cli-config` from `k8s/devops/configmap.example.yaml`, and that template sets no `roadmap.implement.max_memory_limit`. The Service then reads the code default 8Gi, the limit at which the kernel killed two runner Jobs, and the 16Gi that a person set in the live ConfigMap is lost at the next deploy. Git holds no copy of the limit that works, so a deploy keeps the failure (#5484).

## What Changes

- Set `roadmap.implement.max_memory_limit: 16Gi` under `roadmap.implement` in `k8s/devops/configmap.example.yaml`, with a comment that names the two kills of 2026-11-12 and 2026-11-13.
- Hold the value with `test_the_example_holds_the_runner_memory_limit` in `tests/k8s/test_k8s_configmap_keys.py`, which renders the example through `render_active_devops_configmap`.
- List each test module that reads the example ConfigMap in the `changes` of the group that changes the template, so the step may edit one that the new setting breaks.
- Keep the code default `DEFAULT_ROADMAP_IMPLEMENT_MAX_MEMORY_LIMIT` at 8Gi, so a cluster whose nodes cannot allocate 16Gi keeps the product default.
- Change the description of `roadmap.implement.max_memory_limit` in `src/devops_cli/config/settings.py` to name the smallest node that can run a runner Job as the bound.
- Hold the description with `test_the_description_names_the_smallest_node_that_can_run_a_runner_job` in `tests/roadmap/implement/test_roadmap_implement_size.py`.
- Regenerate `docs/ENV_VARS.md` with `uv run devops docs generate`, so its row of the setting states the new bound.
- State the default 8Gi and the example's 16Gi in the Size line of `docs/CLUSTER.md`, and hold the statement with `test_the_size_section_names_the_default_and_the_example_limit` in `tests/config/test_k8s_devops_runtime.py`.
- Leave the other doubled values that the live ConfigMap holds (#5440) out of this change: no acceptance criterion of #5484 names them, and each needs its own proof.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-service-deployment`: The example ConfigMap holds the runner memory limit
- `roadmap-implement-job/runner-job`: The description of the memory limit names the node that runs the Job, The cluster document states both runner memory limits

## Impact

- Code: `k8s/devops/configmap.example.yaml`, `src/devops_cli/config/settings.py`
- Documents: `docs/ENV_VARS.md`, `docs/CLUSTER.md`
- Tests: `tests/k8s/test_k8s_configmap_keys.py`, `tests/ai/benchmark/test_k8s_llm_gateway.py`, `tests/ai/spend/test_hosted_group_prices.py`, `tests/invariants/test_workflow_contracts.py`, `tests/k8s/test_k8s_configmap.py`, `tests/k8s/test_k8s_valkey_stack.py`, `tests/roadmap/implement/test_roadmap_implement_step_classes.py`, `tests/roadmap/stage/test_roadmap_stage_settings.py`, `tests/roadmap/stage/test_roadmap_stage_submit.py`, `tests/roadmap/stage/test_roadmap_stage_window.py`, `tests/roadmap/test_roadmap_limit_classes.py`, `tests/server/routes/test_k8s_roadmap_service.py`, `tests/roadmap/implement/test_roadmap_implement_size.py`, `tests/config/test_k8s_devops_runtime.py`

## Feasibility

- The probe lines confirm the cited paths of the staging commit: "The path `k8s/devops/configmap.example.yaml` is a file of the staging commit.", "The path `src/devops_cli/k8s/configmap.py` is a file of the staging commit.", "The path `src/devops_cli/config/defaults.py` is a file of the staging commit." and "The path `docs/CLUSTER.md` is a file of the staging commit."
- The probe line "The path `roadmap.implement.max_memory_limit` is no file of the staging commit. No commit in the history deleted or renamed it." confirms that the cited name is a setting and no path, so no module moves and no import is rewritten.
- `read_file` of `src/devops_cli/k8s/configmap.py` lines 45-135 shows `src/devops_cli/k8s/configmap.py:57:def render_devops_configmap_content(`, which sets `config["service"]` and writes the whole config again, and `src/devops_cli/k8s/configmap.py:124:def render_active_devops_configmap(`, which reads the template of the product directory.
- `search_code` with `max_memory_limit` returns no line of `k8s/devops/configmap.example.yaml`, so the template sets no runner memory limit, and the staged default is `src/devops_cli/config/defaults.py:1054:DEFAULT_ROADMAP_IMPLEMENT_MAX_MEMORY_LIMIT: str = "8Gi"`.
- `read_file` of `src/devops_cli/config/defaults.py` lines 1045-1062 shows the comment that the 8Gi is below the 15 Gi of the smallest node, which is why the default stays 8Gi and the cluster value goes into the template.
- `read_file` of `src/devops_cli/config/settings.py` lines 1425-1470 shows `src/devops_cli/config/settings.py:1441:max_memory_limit: Annotated[str, Variable()] = Field(`, the text that the change replaces at `src/devops_cli/config/settings.py:1442:it must fit the smallest node of the cluster`, and the form that it keeps at `src/devops_cli/config/settings.py:1444:pattern=r"^[1-9][0-9]*Gi$",`, which admits 16Gi.
- `search_code` with `smallest node of the cluster` returns `docs/ENV_VARS.md:145:The memory limit of every runner Job that the Service creates, as a whole number of Gi such as` and the same text in the field, so group 3 regenerates that one generated row and no other document.
- `read_file` of `src/devops_cli/roadmap/implement/implement_size.py` lines 70-95 shows `src/devops_cli/roadmap/implement/implement_size.py:74:memory="6Gi",` and `src/devops_cli/roadmap/implement/implement_size.py:81:MIN_MEMORY_LIMIT_GI: Final[int] = max(int(row.memory.removesuffix("Gi")) for row in RUNNER_SIZES)`, so the bound is 6 and the 16Gi of the template clears it.
- `read_file` of `docs/CLUSTER.md` lines 40-80 shows `docs/CLUSTER.md:67:- **Size.** The Service sizes the CPU and the memory request of a Job from its plan (#3193).`, the line that states the setting and its default 8Gi.
- `read_file` of `tests/k8s/test_k8s_configmap_keys.py` lines 1-45 shows `tests/k8s/test_k8s_configmap_keys.py:28:rendered = render_active_devops_configmap(`, so the new case renders the example through `_example_config()` and reads its `roadmap.implement` value.
- `read_file` of `tests/roadmap/implement/test_roadmap_implement_size.py` lines 1-30 and 100-140 shows `tests/roadmap/implement/test_roadmap_implement_size.py:114:def test_the_memory_limit_is_8gi_when_the_setting_is_not_set() -> None:` and the import of the `settings` module, so the description case goes there and reaches the field through `settings.RoadmapImplementConfig`, which `src/devops_cli/config/settings.py:1298:class RoadmapImplementConfig(BaseModel):` defines.
- `read_file` of `tests/config/test_k8s_devops_runtime.py` lines 190-225 shows `tests/config/test_k8s_devops_runtime.py:200:raw = yaml.safe_load(_doc("configmap.example.yaml")["data"]["devops-cli.yaml"])`, the module that already reads the template, so the Size case joins it.
- `search_code` with `docs generate` shows `docs/ROADMAP_WORKFLOW.md:309:Write the generated documents in the docs directory of the checkout` and the amendment that deleted `--sync-readme`, so group 3 runs the generator with no option; the earlier plan cited the deleted option and is corrected here.
- The earlier plan also cited a read of the live ConfigMap as a `devops` command, which no command of the tool implements. This plan names no such command: the live read is a person's step after the merge, with the cluster's own client.
- `render_active_devops_configmap` needs a checkout of the repository: the new case passes `REPO_ROOT / "k8s" / "devops"` as `product_dir` and the function reads `configmap.example.yaml` there; it needs no client of a service and no network.
- `render_devops_configmap_content` needs no checkout, no client and no network: it takes the template text, the repository list and the GitHub App settings as values and returns a text.
- The plan introduces no program and no option: `uv`, `devops` and `pytest` are tools of the runner image, so no failure class is added, no `NOT_IN_RUNNER` entry applies and no pod setting changes from `readOnlyRootFilesystem: true` and `runAsNonRoot: true`.
- The first checks against the real system are `uv run devops ci test tests/k8s/test_k8s_configmap_keys.py` for the rendered limit, `uv run devops ci test tests/roadmap/implement/test_roadmap_implement_size.py` for the description, `uv run devops docs generate` and then `uv run devops docs check` for the generated row, and `uv run devops ci test tests/config/test_k8s_devops_runtime.py` for the Size line.
- The live ConfigMap, the two kills and the allocatable memory of the parked node are not checked by this run: the plan run has no cluster client and runs no command. The third criterion stays a person's step after the merge, which runs `devops k8s deploy-stack --stack devops` and reads the live ConfigMap.
- The related document of #5444 is absent, per the probe line "The path `docs/K8S_PERFORMANCE.md` is no file of the staging commit. No commit in the history deleted or renamed it."; this change creates no such file and records no gap in it.
- The issue can be built as written: the template exists, the render writes every setting that is not `service` again, and the field pattern admits 16Gi above the bound of 6.

## Existing Tool Considered

The example ConfigMap `k8s/devops/configmap.example.yaml` and `devops k8s deploy-stack --stack devops` are the existing controls, and this change adds no tool, library or command. The issue estimates 50,000 tokens and 30 minutes to build the same result as code; this change writes no code and adds no dependency.

## Dependencies

- #5492 changes `docs/CLUSTER.md`, the same document that group 4 edits, so the two edits must not conflict.
- #5547 changes `src/devops_cli/config/defaults.py`, which this change reads for `DEFAULT_ROADMAP_IMPLEMENT_MAX_MEMORY_LIMIT` and does not edit; the default stays 8Gi.
