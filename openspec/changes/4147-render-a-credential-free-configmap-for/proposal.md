# Proposal

## Why

ConfigMap `devops-cli-config-sandbox` is the credential-free copy of the Service config that the planner run Job of #4003 mounts at `/config`, and ADR 0018 control 2 asks for it with each key that holds a credential removed. #4147 records that no command renders it: `src/devops_cli/commands/k8s/stack_lifecycle.py:947:return render_active_devops_configmap(product)` renders only `devops-cli-config`, so the copy is manual and drifts from the active config at the next deploy.

## What Changes

- Add `drop_secret_named_keys` to `src/devops_cli/security/sanitizer.py` beside `src/devops_cli/security/sanitizer.py:502:if is_secret_parameter_name(str(key))`: it drops each dict entry whose key the name rule matches, at any depth of dicts and lists, and keeps every other key with its value.
- Add `CONST_K8S_DEVOPS_SANDBOX_CONFIGMAP` to `src/devops_cli/config/constants.py` beside `src/devops_cli/config/constants.py:1204:CONST_K8S_DEVOPS_CONFIGMAP: Final[str] = "devops-cli-config"`.
- Add a keyword-only `drop_secret_keys` parameter to `render_devops_configmap_content` and `render_active_devops_configmap` in `src/devops_cli/k8s/configmap.py`: it drops the credential-named keys after the service block is set and before `src/devops_cli/k8s/configmap.py:91:unknown = unknown_setting_keys(written)`, so a credential key of the template is removed rather than refused as an unknown setting.
- Add `render_active_devops_sandbox_configmap` to `src/devops_cli/k8s/configmap.py`: it renders with the drop, sets `metadata.name` to the sandbox constant and returns the manifest with the one data key, and export it from `src/devops_cli/k8s/__init__.py` beside `src/devops_cli/k8s/__init__.py:14:render_active_devops_configmap,`.
- Apply the sandbox ConfigMap on both deploy paths, delete it in teardown-stack and name it in both dry runs in `src/devops_cli/commands/k8s/stack_lifecycle.py`, beside `src/devops_cli/commands/k8s/stack_lifecycle.py:1772:CONST_K8S_DEVOPS_CONFIGMAP,`.
- Add the test in `tests/k8s/test_k8s_configmap.py` that renders the sandbox ConfigMap from a template with a top-level and a nested credential key and walks every key of the inner config at any depth, and the test in `tests/security/test_secret_redaction.py` for the removal walk.
- Update the deploy, teardown and dry-run cases in `tests/commands/k8s/test_k8s.py` for the second rendered ConfigMap, and add the row of the sandbox ConfigMap to the Homelab Values at Deploy Time table of `k8s/README.md`.
- Keep the manifest of the run Job as it is: `k8s/devops/roadmap-service/cronjob-planner-run.yaml:113:name: devops-cli-config-sandbox` mounts the name that the render keeps, and no group changes that file.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `k8s-planner-run-job`: deploy-stack renders the credential-free sandbox ConfigMap, The sandbox ConfigMap drops every credential key at any depth, The sandbox ConfigMap keeps the name and the data key the run Job mounts, teardown-stack deletes the sandbox ConfigMap, A dry run names the sandbox ConfigMap and prints no value of it, A test walks every key of the rendered config

## Impact

- Code: `src/devops_cli/security/sanitizer.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/k8s/configmap.py`, `src/devops_cli/k8s/__init__.py`, `src/devops_cli/commands/k8s/stack_lifecycle.py`
- Documents: `k8s/README.md`
- Tests: `tests/security/test_secret_redaction.py`, `tests/k8s/test_k8s_configmap.py`, `tests/commands/k8s/test_k8s.py`

## Feasibility

- Premise: the data key devops-cli.yaml is no repository file. The probe says, word for word: "The path `devops-cli.yaml` is no file at the root of the staging commit. These files of the commit are candidates: `tests/fixtures/dashboard_queries/devops-cli.yaml`. No commit in the history deleted or renamed it." So the key is a value of the manifest, and the render reads the active config and the template.
- Premise: the config.yaml of the issue is the workstation config, not a file of the repository. The probe says, word for word: "The path `config.yaml` is no file at the root of the staging commit. These files of the commit are candidates: `k8s/llm/gateway/config.yaml`, `openspec/config.yaml`. No commit in the history deleted or renamed it."
- Premise: metadata.name and metadata.namespace are manifest values, not repository files. The probe says, word for word: "The path `metadata.name` is no file of the staging commit. No commit in the history deleted or renamed it."
- Premise: no command renders the sandbox ConfigMap. `search_code` for `_render_devops_configmap` shows one definition at `src/devops_cli/commands/k8s/stack_lifecycle.py:944:def _render_devops_configmap(product: Path) -> str:` and one render at `src/devops_cli/commands/k8s/stack_lifecycle.py:947:return render_active_devops_configmap(product)`, which writes the one name `devops-cli-config`; `search_code` for `devops-cli-config-sandbox` finds only the run Job manifest, the admission policy, `docs/CLUSTER.md`, one roadmap test and archived changes, and no command.
- `read_file` shows the renderer at `src/devops_cli/k8s/configmap.py:135:def render_active_devops_configmap(` with `src/devops_cli/k8s/configmap.py:153:active_settings = settings if settings is not None else load_settings()`, so a caller passes its own settings, and `src/devops_cli/k8s/configmap.py:88:data[_CONFIG_KEY] = yaml.dump(config, Dumper=_BlockDumper, sort_keys=False)` writes the one data key that the sandbox render rewrites.
- `read_file` shows `src/devops_cli/security/sanitizer.py:487:def is_secret_parameter_name(name: str) -> bool:` with `src/devops_cli/security/sanitizer.py:490:return any(word in lowered for word in CONST_MCP_SECRET_PARAMETER_WORDS)`, the one name rule of the project, and `src/devops_cli/security/sanitizer.py:502:if is_secret_parameter_name(str(key))` keeps a credential-named key and masks its value, so the new walk beside `src/devops_cli/security/sanitizer.py:493:def mask_secret_named_values(data: Any) -> Any:` drops the entry instead.
- The staged value of the credential words is `CONST_MCP_SECRET_PARAMETER_WORDS` = (password, passphrase, secret, token, api_key, apikey, private_key, credential, bearer, key_values), declared at `src/devops_cli/config/constants.py:617:CONST_MCP_SECRET_PARAMETER_WORDS: Final[tuple[str, ...]] = (`.
- The staged value of the existing ConfigMap name is `CONST_K8S_DEVOPS_CONFIGMAP` = devops-cli-config, declared at `src/devops_cli/config/constants.py:1204:CONST_K8S_DEVOPS_CONFIGMAP: Final[str] = "devops-cli-config"`; the sandbox name is that value with the suffix -sandbox, which the run Job already mounts.
- The planner run Job already mounts the sandbox name at this commit: `k8s/devops/roadmap-service/cronjob-planner-run.yaml:113:name: devops-cli-config-sandbox` with `k8s/devops/roadmap-service/cronjob-planner-run.yaml:71:value: /config/devops-cli.yaml`, and the admission policy admits it at `k8s/devops/roadmap-service/admissionpolicy.yaml:144:(variables.planner && v.configMap.name == "devops-cli-config-sandbox"))) ||`, so no manifest changes.
- The render refuses an unknown setting key before it writes: `src/devops_cli/k8s/configmap.py:91:unknown = unknown_setting_keys(written)` with `src/devops_cli/config/setting_keys.py:33:unknown.append(path)`, and the walk goes into a nested model. A template with a credential key would therefore be refused, so the drop runs between the service block and that check, and the fixture of the test can hold the credential keys.
- `read_spec` of `k8s-planner-run-job` lists the requirement "The kustomization and deploy-stack hold the new files" and the mount requirement "The pod holds two writable volumes and two read-only ones", so the change adds requirements to that capability and modifies none of them.
- `read_file` shows the existing inner-config parse at `tests/k8s/test_k8s_configmap.py:138:inner = yaml.safe_load(doc["data"]["devops-cli.yaml"])` and the template constant `SAMPLE_TEMPLATE`, so the new case walks the inner config as the existing cases do.
- `render_active_devops_configmap(product_dir, settings=None)` needs a checkout of the repository: it reads `configmap.example.yaml` under the product base; it needs no client of a service and no network. `load_settings()` reads the active config file of the workstation and needs no checkout, no client and no network.
- `runtime._run_cmd` with kubectl apply and kubectl delete needs a client of the cluster, a kubeconfig context; `tests/commands/k8s/test_k8s.py:1610:_APPLY_STDIN = ["kubectl", "apply", "-f", "-", *_CONTEXT]` shows the fake that doubles that process edge, and the tests reach no cluster.
- Each verify is `uv run devops ci test` with one module, and the document group uses `uv run devops ci docs`; their programs uv, python and devops are runner tools of the image, and NOT_IN_RUNNER names none of them. The failure class is a failing test or docs row with exit 1, and no cluster, network or scanner is needed. The pod settings that apply are readOnlyRootFilesystem true, runAsNonRoot true, allowPrivilegeEscalation false, capabilities.drop ALL and seccompProfile RuntimeDefault; the tests write only pytest temporary files.
- First checks against the real system: `uv run devops ci test tests/security/test_secret_redaction.py`, `uv run devops ci test tests/k8s/test_k8s_configmap.py`, `uv run devops ci test tests/commands/k8s/test_k8s.py`, `uv run devops ci docs`, and `uv run devops k8s deploy-stack --stack devops --dry-run`, which names devops/devops-cli-config-sandbox and prints no value of it.
- `find_issues` for devops-cli-config-sandbox shows #4098, which wires the planner run tool and needs the ConfigMap to exist, so it comes after this render. The overlap #6586 changes the settings model that `load_settings` reads; this change adds no setting field, so #6586 merges first and the render runs on its model.
- The issue is buildable as written: the renderer, the name rule and the mount of the run Job all exist at the staged commit, so the plan compensates for no false premise and changes no manifest. The plan cites the renderer by its definition and its call line, and quotes no conditional expression, so no code span of the plan reads as a command.
- The reported fault is corrected: the line that names the renderer now cites two statements of that module with their full path, `src/devops_cli/k8s/configmap.py:135:def render_active_devops_configmap(` and `src/devops_cli/k8s/configmap.py:153:active_settings = settings if settings is not None else load_settings()`, and no code span of the plan is a bare module path.

## Existing Tool Considered

mikefarah/yq partly covers the need: it deletes keys at any depth with a recursive expression, but it renders and applies no ConfigMap and holds no copy of the name rule of the project (`is_secret_parameter_name`), and `kustomize configMapGenerator` builds a ConfigMap from files and literals and removes no key. The change adds about 25 lines to the existing renderer and the sanitizer: about 2k tokens to build, 1k tokens a year to keep, 2k tokens to fix, and about 1 hour. It deletes no internal code.

## Dependencies

- #6586: changes src/devops_cli/config/settings.py, which `load_settings` reads for the render; it merges first so the render and its tests run on its settings model.
