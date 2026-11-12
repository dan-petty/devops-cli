---
applies_to:
  - "pkg:pypi/pyyaml@6.0.*"
  - "pkg:pypi/jinja2@3.1.*"
  - "pkg:pypi/ruamel-yaml@0.19.*"
sources:
  - "https://pyyaml.org/"
  - "https://jinja.palletsprojects.com/"
  - "https://yaml.dev/doc/ruamel.yaml/"
reviewed: "2026-11-11"
tags:
  - "pyyaml"
  - "jinja2"
  - "templates"
---

# Code Library: PyYAML & Jinja2 (Structured Manifests & Template Engine)

## 1. Project References

| Resource | Endpoint / URL |
| :--- | :--- |
| **Official Documentation** | [pyyaml.org](https://pyyaml.org/) • [jinja.palletsprojects.com](https://jinja.palletsprojects.com/) |
| **Public Git Repository** | [github.com/yaml/pyyaml](https://github.com/yaml/pyyaml) • [github.com/pallets/jinja](https://github.com/pallets/jinja) |
| **Official PyPI Package** | [pypi.org/project/PyYAML](https://pypi.org/project/PyYAML/) (`6.0.3`) • [pypi.org/project/jinja2](https://pypi.org/project/jinja2/) (`3.1.6`) |
| **DevOps CLI Integration** | [`src/devops_cli/commands/devcontainer.py`](../../../../../../src/devops_cli/commands/devcontainer.py) • [`src/devops_cli/k8s/`](../../../../../../src/devops_cli/k8s/) |

---

## 2. General Information & Architecture

**PyYAML** is a YAML 1.1 parser and emitter for Python. **ruamel.yaml** reads and writes YAML 1.2. **Jinja2** is a fast, expressive, extensible templating engine powering template rendering across Python frameworks.

In `devops-cli`:
- **Kubernetes & GitOps YAML**: Parses and serializes Kubernetes manifests, ArgoCD Application specifications, Helm values overrides, and Kustomize patches.
- **Config files**: ruamel.yaml reads and writes each config file of devops-cli as YAML 1.2 (#4481). YAML 1.1 reads a bare `off`, `on`, `yes` or `no` as a bool and a bare `12:30` as the number 750. So do not read a config file with PyYAML.
- **DevContainer & Agent Scaffolding**: Uses Jinja2 templates (`src/devops_cli/templates/`) to dynamically scaffold `.devcontainer/devcontainer.json` and MCP configuration files (`AGENTS.md` is generated in Python).

---

## 3. Comparable Projects & Tradeoffs

| Library | Strengths | Weaknesses | Why `devops-cli` Chose PyYAML + Jinja2 |
| :--- | :--- | :--- | :--- |
| **`PyYAML` + `jinja2`** | Battle-tested, supports `CSafeLoader`/`CSafeDumper` in C/Rust, expressive templating (loops, filters, macros). | PyYAML does not preserve round-trip comments natively. | **Selected**: The definitive industry standard for cloud-native manifest generation. |
| **`ruamel.yaml`** | Round-trip mode keeps the comments, the order of the keys, the quotes and the unknown keys of a file that it edits. | Slower than PyYAML, and one indentation for all of a document. | Used for the config files of devops-cli: `devops_cli.config.round_trip` edits `config.yaml` in place when a command saves settings (#1999), and `config/yaml_errors.py::parse_config_yaml` reads each config file with the safe loader, as YAML 1.2 (#4481). PyYAML `safe_load` / `safe_dump` reads and writes every other YAML file. |
| **`mako`** | High-performance templating engine. | Less standard in the Kubernetes and DevContainer ecosystem than Jinja2. | Rejected: Jinja2 is the universal standard across Ansible, Helm, and DevContainers. |
| **Python f-strings** | Built into Python. | Unsafe for complex multi-line templates, lacks template inheritance and reusable partial blocks. | Rejected: Jinja2 isolates template files cleanly from Python code logic. |

---

## 4. Key Concepts & Core Patterns

1. **`yaml.safe_load(text)`**: Always use `safe_load` instead of `yaml.load` to prevent arbitrary code execution vulnerabilities. For a config file of devops-cli, use `parse_config_yaml`, which reads YAML 1.2.
2. **`jinja2.Environment`**: `core/templating.py` uses a cached `SandboxedEnvironment(FileSystemLoader, undefined=StrictUndefined)`; values are encoded with `| tojson` and output is re-parsed as JSON. Templates scaffold devcontainer.json and MCP configs; AGENTS.md is generated in Python.
3. **Template Inheritance**: Reuses base template headers across DevContainer configurations.

---

## 5. Common & Advanced Usage Examples

### Safe YAML Parsing

The message of a YAML error quotes the line where the parser stopped, and its `problem_mark` holds the text of the document. The safe loaders of PyYAML and ruamel.yaml also raise `ValueError`, `KeyError`, `IndexError` or `AttributeError` for a tagged value that they cannot build, such as `!!int <text>`, and the message quotes the value. They raise `RecursionError` for a document that nests too deep. A file can hold a credential, so the error that you raise names the type of the error and its position, and quotes no text. Do not catch these errors by hand: call `config/yaml_errors.py::load_yaml` with the parse. It catches the errors of `yaml_load_errors()` by name (a blind `except Exception` is a swallowed failure that `tests/test_swallowed_failures_ratchet.py` refuses), reads the position in a function so that no frame of the traceback holds the mark, and raises the ConfigurationError after the `except` block, so it has no cause and no context that holds the first error. An `OSError` goes up, because it names only the file. `load_yaml` catches the `YAMLError` of ruamel.yaml, so the parse reads with ruamel.yaml: `parse_config_yaml` for a config file. `config/settings.py::_read_config_file`, `config/write_history.py` and `config/round_trip.py` read the config files this way.

```python
from pathlib import Path
from typing import Any

from devops_cli.config.yaml_errors import load_yaml, parse_config_yaml


def load_yaml_file(path: Path) -> Any:
    return load_yaml(
        lambda: parse_config_yaml(path.read_text(encoding="utf-8")) or {},
        name=str(path),
        action="Cannot load the settings",
    )
```

### Rendering a Dynamic DevContainer Configuration
```python
from jinja2 import Environment, FileSystemLoader


def render_devcontainer(template_dir, image_tag: str) -> str:
    env = Environment(loader=FileSystemLoader(str(template_dir)))
    template = env.get_template("devcontainer.json.j2")
    return template.render(image_tag=image_tag)
```

---

## 6. Best Practices & Security Standards

1. **Strictly Enforce `safe_load` / `safe_dump`**: Never invoke `yaml.load(text, Loader=yaml.Loader)`; arbitrary Python object instantiation is a severe security defect.
2. **Sanitize Jinja Variables**: Escape user-supplied strings before interpolating into template environments.
