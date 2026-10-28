---
applies_to:
  - "pkg:pypi/pyyaml@6.0.*"
  - "pkg:pypi/jinja2@3.1.*"
  - "pkg:pypi/ruamel-yaml@0.19.*"
sources:
  - "https://pyyaml.org/"
  - "https://jinja.palletsprojects.com/"
  - "https://yaml.dev/doc/ruamel.yaml/"
reviewed: "2026-10-24"
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

**PyYAML** is a YAML 1.2 parser and emitter for Python. **Jinja2** is a fast, expressive, extensible templating engine powering template rendering across Python frameworks.

In `devops-cli`:
- **Kubernetes & GitOps YAML**: Parses and serializes Kubernetes manifests, ArgoCD Application specifications, Helm values overrides, and Kustomize patches.
- **DevContainer & Agent Scaffolding**: Uses Jinja2 templates (`src/devops_cli/templates/`) to dynamically scaffold `.devcontainer/devcontainer.json` and MCP configuration files (`AGENTS.md` is generated in Python).

---

## 3. Comparable Projects & Tradeoffs

| Library | Strengths | Weaknesses | Why `devops-cli` Chose PyYAML + Jinja2 |
| :--- | :--- | :--- | :--- |
| **`PyYAML` + `jinja2`** | Battle-tested, supports `CSafeLoader`/`CSafeDumper` in C/Rust, expressive templating (loops, filters, macros). | PyYAML does not preserve round-trip comments natively. | **Selected**: The definitive industry standard for cloud-native manifest generation. |
| **`ruamel.yaml`** | Round-trip mode keeps the comments, the order of the keys, the quotes and the unknown keys of a file that it edits. | Slower than PyYAML, and one indentation for all of a document. | Used for one job: `devops_cli.config.round_trip` edits `config.yaml` in place when a command saves settings (#1999). PyYAML `safe_load` / `safe_dump` reads and writes every other YAML file. |
| **`mako`** | High-performance templating engine. | Less standard in the Kubernetes and DevContainer ecosystem than Jinja2. | Rejected: Jinja2 is the universal standard across Ansible, Helm, and DevContainers. |
| **Python f-strings** | Built into Python. | Unsafe for complex multi-line templates, lacks template inheritance and reusable partial blocks. | Rejected: Jinja2 isolates template files cleanly from Python code logic. |

---

## 4. Key Concepts & Core Patterns

1. **`yaml.safe_load(text)`**: Always use `safe_load` instead of `yaml.load` to prevent arbitrary code execution vulnerabilities.
2. **`jinja2.Environment`**: `core/templating.py` uses a cached `SandboxedEnvironment(FileSystemLoader, undefined=StrictUndefined)`; values are encoded with `| tojson` and output is re-parsed as JSON. Templates scaffold devcontainer.json and MCP configs; AGENTS.md is generated in Python.
3. **Template Inheritance**: Reuses base template headers across DevContainer configurations.

---

## 5. Common & Advanced Usage Examples

### Safe YAML Parsing

The message of a PyYAML error quotes the line where the parser stopped, and the `buffer` of its `problem_mark` holds the full text of the document. The safe loader also raises `ValueError`, `KeyError`, `IndexError` or `AttributeError` for a tagged value that it cannot build, such as `!!int <text>`, and the message quotes the value. A file can hold a credential, so the error that you raise names the type of the error and its position, and quotes no text. Catch each error but `OSError`, which names only the file. Read the position in a helper function, so that no frame of the traceback holds the mark. Raise the error after the `except` block: then it has no cause and no context that holds the first error. `config/settings.py::_read_config_file` reads the config files this way.

```python
from pathlib import Path
from typing import Any

import yaml

from devops_cli.exceptions import ConfigurationError


def load_yaml_file(path: Path) -> Any:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except OSError:
        raise
    except Exception as exc:
        error_type, where = type(exc).__name__, _error_location(exc)
    raise ConfigurationError(f"{path} is not valid YAML ({error_type}){where}.")


def _error_location(exc: Exception) -> str:
    mark = exc.problem_mark if isinstance(exc, yaml.MarkedYAMLError) else None
    return f" at line {mark.line + 1}, column {mark.column + 1}" if mark else ""
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
