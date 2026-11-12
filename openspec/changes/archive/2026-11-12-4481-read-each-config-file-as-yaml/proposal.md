# Proposal: #4481

## Why

A bare `off` or `on` as the value of `roadmap.intake.jev` stops the settings load (#4481). The settings save writes a config file with ruamel.yaml, which writes YAML 1.2 (`round_trip.edit`). The readers read the file with PyYAML `yaml.safe_load`, which reads YAML 1.1. In YAML 1.1, a bare `off` is `false`, a bare `no` is `false` and a bare `12:30` is the number 750. So `devops config set roadmap.intake.jev off` writes `jev: off`, and the next load reads `false`, which the mode type refuses. The same defect occurs for each string setting: `devops config set search.language no` and `devops config set k8s.context 12:30` write the file and then stop each later load.

## What Changes

- Each reader of a config file reads it as YAML 1.2 with the safe loader of ruamel.yaml (`YAML(typ="safe", pure=True)`), the library that writes the file. The readers are the settings load (`settings._read_config_file`), the two readers of `write_history`, the audit of `devops config audit-keys`, the config in the ConfigMap template of `k8s/configmap.py`, and the project config read of the SSH key prefix (`crypto/ssh_keys.py`).
- `config/yaml_errors.py` holds the one YAML 1.2 reader, `parse_config_yaml`, and the errors of a load, `yaml_load_errors()`. `load_yaml` catches the `YAMLError` of ruamel.yaml in place of the error of PyYAML. Each function imports ruamel.yaml when it runs, so a command that reads no config file does not import it.
- A bare `off`, `on`, `yes` or `no` in a config file loads as a string. A key that a mapping holds two times stops the load with an error that names the file, the line and the column. `JevMode`, `DecisionMode` and the refusal of a bool stay as they are: a bare `true` is still a bool, and the mode types refuse it.
- The ConfigMap render reads the manifest of the template with PyYAML, because Kubernetes reads the manifest. Only the config in the manifest is read as YAML 1.2.
- `docs/CONFIGURATION.md` and `docs/roadmap/intake.md` state that a config file is read as YAML 1.2.
- These behaviors are observable (the settings load, `devops config set`, `devops config audit-keys`, the ConfigMap render and the SSH key prefix), so the change has a spec delta.

## Capabilities

- `config-commands`: ADDED requirements for the YAML 1.2 read of each config file. MODIFIED requirement "A write or an edit of a config file quotes no text of a file that a YAML parser cannot load", because no reader of a config file uses PyYAML after this change.

## Impact

- Each command that loads the settings imports ruamel.yaml when it reads a config file: 29 more modules. `uv run devops ci --only startup-imports` measures the start of the help commands.
- Values that change type, from the census of the committed config inputs: none. Values of the YAML 1.1 forms change: a bare `0755` loads as 755 and not as 493, a bare `1:30` loads as the string `1:30`, so a number setting refuses it, and a bare `1e3` loads as the number 1000.0.
- The change fits one pull request.

## Feasibility

The premise was confirmed with commands on PyYAML 6 and ruamel.yaml 0.19.1, the version that `pyproject.toml` pins:

- `yaml.safe_load("jev: off")` gives `{'jev': False}`, and `YAML(typ="safe", pure=True).load("jev: off")` gives `{'jev': 'off'}`. The same holds for `on`, `yes` and `no`. `12:30` gives 750 with PyYAML and `'12:30'` with ruamel.yaml.
- A key that a mapping holds two times raises `DuplicateKeyError`, a `MarkedYAMLError` with a mark. `roadmap: [unclosed` raises `ParserError` with a mark. `!!int <text>` raises `ValueError`, `!!bool <text>` raises `KeyError`, and a document that nests too deep raises `RecursionError`, as with PyYAML. `!!timestamp <text>` raises `ConstructorError` with a mark, where PyYAML raised `AttributeError`.
- ruamel.yaml.clib is not installed. `pure=True` keeps the Python parser of YAML 1.2 also when it is installed: the deprecation text of `ruamel.yaml.main.safe_load` names `typ='safe', pure=True` as its replacement.
- Census of the readers: `git grep -nE 'yaml\.safe_load(_all)?\(' -- 'src/*.py'` gives 44 lines. 7 of them are in `src/devops_cli/config`, `commands/config.py`, `k8s/configmap.py` and `crypto/ssh_keys.py`: 6 read a config file, and 1 reads the Kubernetes manifest of the ConfigMap template and stays PyYAML. The other 37 lines read other files (manifests, rule packs, `labels.yml`, `.pre-commit-config.yaml`), not a config file of devops-cli.
- Census of the values: on `config.example.yaml` and the config in `k8s/devops/configmap.example.yaml`, 0 of 84 values change between the two readers.
- With `import devops_cli.config.settings` done first, `import ruamel.yaml` adds 29 modules.

## Existing Tool Considered

ruamel.yaml (`ruamel-yaml==0.19.1`), an open and maintained library that `pyproject.toml` already pins and that `round_trip.edit` uses to write the file. Its safe loader reads YAML 1.2, the version that the writer writes. The change builds no code to keep: each reader calls the loader of the library.

The change deletes this internal code: the PyYAML imports of `config/settings.py` and `config/write_history.py`, the `errors` parameter of `load_yaml`, `_LOAD_ERRORS` of `config/round_trip.py` and `_AUDIT_READ_ERRORS` of `commands/config.py`.
