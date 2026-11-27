# Design

## Decisions

- **The shared loader constructs the value tag as a string.** `_value_tag_as_string` in `src/devops_cli/core/serialization.py` makes a subclass of the PyYAML loader that `YAML_SAFE_LOADER` names: `CSafeLoader` when PyYAML has libyaml, else `SafeLoader`. It registers a constructor for `tag:yaml.org,2002:value` with `add_constructor`, the documented PyYAML way. The constructor calls `construct_yaml_str`, as for a `!!str` scalar. So a plain `=` loads as `"="`, as YAML 1.2 and Kubernetes read it. A value tag on a mapping or a sequence, such as `!!value {a: 1}`, still raises `ConstructorError`: `construct_scalar` refuses a node that is not a scalar.
- **The PyYAML classes do not change.** `add_constructor` copies the table of constructors into the class that it is called on. On a subclass, `yaml.SafeLoader.yaml_constructors` and `yaml.CSafeLoader.yaml_constructors` keep no entry for the tag. The gate code under `tests/gate/` loads with `yaml.CSafeLoader` and so keeps the behavior of PyYAML.
- **Each reader of a render loads with the shared loader.** The readers that parse a render, as the census of the proposal gives them:
  - `_render_app_objects` (`src/devops_cli/k8s/catalog.py:688`) loads with `YAML_SAFE_LOADER`, so the change of the loader covers it.
  - `image_values` and `updater_repositories` (`src/devops_cli/k8s/image_pins.py:169`, `:188`) compose nodes with `YAML_SAFE_LOADER` and construct no object, so a plain `=` never stopped them. They do not change.
  - `_check_path_source` (`src/devops_cli/k8s/argocd_gate.py:265`) loads a Kustomize build with `yaml.safe_load_all`. It loads with `yaml.load_all` and `YAML_SAFE_LOADER` now.
  - `_PathBuild.objects` (`src/devops_cli/commands/k8s/stack_lifecycle.py:1299`) loads a Kustomize build with `yaml.safe_load_all`. It loads with `yaml.load_all` and `YAML_SAFE_LOADER` now. The import of the loader stays in the method, beside the import of `yaml`.
- **The readers of a file that is not a render keep `yaml.safe_load_all`.** Examples are the value files of the Argo CD gate, the manifest files of `devops review` and the manifests of kubeconform. The item names the readers of a rendered manifest.

## Rejected alternatives

- **Call `add_constructor` on `yaml.SafeLoader` or `yaml.CSafeLoader`.** It changes PyYAML for the whole process. `tests/gate/k8s_checks/deploy_stack.py:46` and `tests/gate/k8s_checks/network_policies.py:61` load with `yaml.CSafeLoader`, and each library in the process that loads YAML would get the constructor too.
- **Remove the implicit resolver of `=` from a loader subclass.** A comment on yaml/pyyaml#89 gives `yaml_implicit_resolvers.pop("=")`. The subclass then resolves a plain `=` to `tag:yaml.org,2002:str`. It changes the tags of the nodes that `yaml.compose_all` gives, which `src/devops_cli/k8s/image_pins.py:169` reads, and it still stops on an explicit `!!value` tag. The constructor changes only the construction, and the open PyYAML pull request yaml/pyyaml#867 uses it.
- **Change `=` in the text of a render before the load.** A text edit cannot tell a plain scalar from a quoted scalar or a block scalar, so it can change the data. The parser of PyYAML already knows the scalar style.
- **Move each reader to ruamel.yaml.** ruamel.yaml reads YAML 1.2, but it is no drop-in for `yaml.load_all` with the shared loader. The move changes each reader, and the alternatives check of the issue records no drop-in.
