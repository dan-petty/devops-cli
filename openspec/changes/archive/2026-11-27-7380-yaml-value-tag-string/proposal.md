# Proposal: #7380

## Why

`devops k8s catalog` stops with a `ConstructorError` on the homelab environment tree (#7380). The chart `prometheus-operator-crds` renders CRDs whose enums hold the plain item `=` (`- =`). PyYAML reads YAML 1.1, and its resolver gives a plain `=` the tag `tag:yaml.org,2002:value`. No PyYAML loader has a constructor for that tag, so the load stops. Kubernetes reads YAML 1.2, where `=` is the string `"="`, so the API server and Argo CD accept the same objects. Two other readers of a Kustomize build load with `yaml.safe_load_all` and stop on the same item: the Argo CD gate and the path builds of `devops k8s deploy-stack` and `devops k8s teardown-stack`.

## What Changes

- The shared safe loader `YAML_SAFE_LOADER` of `src/devops_cli/core/serialization.py` reads a node of the tag `tag:yaml.org,2002:value` as a string. The constructor goes on a subclass of the PyYAML loader, so `yaml.SafeLoader` and `yaml.CSafeLoader` do not change.
- `devops k8s catalog` loads each render with that loader, so it reads a plain `=` as `"="`.
- The Argo CD gate (`src/devops_cli/k8s/argocd_gate.py`) and the path builds of the stack commands (`src/devops_cli/commands/k8s/stack_lifecycle.py`) load a Kustomize build with the shared loader in place of `yaml.safe_load_all`.
- The behavior of three commands changes, so the change has a spec delta.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `k8s-service-catalog`: The catalog reads a plain `=` of a render as a string
- `k8s-image-pins`: The Argo CD gate reads a plain `=` of a path build as a string
- `k8s-helm-deploy`: The stack dry run lists a build that holds a plain `=`

## Impact

- Code: `src/devops_cli/core/serialization.py`, `src/devops_cli/k8s/argocd_gate.py`, `src/devops_cli/commands/k8s/stack_lifecycle.py`
- Tests: `tests/core/test_serialization.py`, `tests/k8s/test_k8s_catalog.py`, `tests/k8s/test_k8s_argocd_gate.py`, `tests/commands/k8s/test_k8s.py`
- The readers of a rendered manifest: `git grep -n -e "build_manifest_path(" -e "application_renders(" -- src/devops_cli` gives the producers of a render. Four readers parse the text of a render into YAML: `_render_app_objects` (`src/devops_cli/k8s/catalog.py:688`), `image_values` and `updater_repositories` (`src/devops_cli/k8s/image_pins.py:169`, `:188`), `_check_path_source` (`src/devops_cli/k8s/argocd_gate.py:265`) and `_PathBuild.objects` (`src/devops_cli/commands/k8s/stack_lifecycle.py:1299`). The design gives the result for each of them. The other callers give the text to `kubectl apply` or write it to a file, and parse no YAML.
- The other users of `YAML_SAFE_LOADER`: `src/devops_cli/security/semgrep_registry.py:202` loads a rule file of the Semgrep registry, and `src/devops_cli/research/k8s_pins.py:36` and `src/devops_cli/research/workflow_pins.py:69` compose nodes. A plain `=` in their input now loads as `"="` and no longer stops the load.

## Feasibility

- PyYAML 6.0.4 with libyaml (`yaml.__with_libyaml__` is `True`), Python 3.14: `yaml.load("- =", Loader=L)` raises `ConstructorError: could not determine a constructor for the tag 'tag:yaml.org,2002:value'` for each of `SafeLoader`, `CSafeLoader`, `FullLoader` and `UnsafeLoader`. `lib/yaml/resolver.py` of PyYAML adds the implicit resolver `tag:yaml.org,2002:value` for `^(?:=)$`, and no constructor of PyYAML registers that tag.
- PyYAML reads the tag as a string in one place: `SafeConstructor.flatten_mapping` (`yaml/constructor.py:210`) gives a mapping key of the value tag the tag `tag:yaml.org,2002:str`.
- The live API server (k3s v1.37.2) holds the CRD `alertmanagerconfigs.monitoring.coreos.com` of prometheus-operator 0.95.2 with the enum `['!=', '=', '=~', '!~']`. So Kubernetes reads the plain item as the string `"="`.
- `devops k8s catalog --check --k8s-dir <export of dan-petty/homelab main>/k8s` with the code of `main` exits 1 with the `ConstructorError` at line 12397, column 29 of the render of `prometheus-operator-crds`. With the change, the command reads every render and goes on to the coverage check of `catalog.toml`.
- `check_argocd_gate` on a tree whose path source builds a CRD with `- =` reports `Rendered output for path 'k8s/crds' failed to parse: could not determine a constructor for the tag 'tag:yaml.org,2002:value'`.

## Existing Tool Considered

PyYAML covers the need with its documented extension point: `add_constructor` on a loader class registers a constructor for a tag. The PyYAML issue yaml/pyyaml#89 (open since 2017) gives this fix, a constructor of `tag:yaml.org,2002:value` that returns the scalar as a string. The open pull request yaml/pyyaml#867 adds the same constructor to `SafeConstructor` with `construct_yaml_str`, and the closed pull request yaml/pyyaml#635 did the same. No PyYAML release holds it: 6.0.4 (2026-11-20) has no constructor for the tag. The change adds one constructor of 1 line on a subclass of the loader, and no parser.

ruamel.yaml (MIT, maintained) reads YAML 1.2, so it reads `=` as a string. It is no drop-in for `yaml.load_all` with the shared loader, and each reader of a render would move to its API. The cost of the move is not in proportion to a constructor of 1 line.

The change deletes no internal code. It replaces `yaml.safe_load_all` with the shared loader in 2 readers.
