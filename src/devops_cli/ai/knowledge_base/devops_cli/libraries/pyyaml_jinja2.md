# Code Library: PyYAML & Jinja2 (Structured Manifests & Template Engine)

## 1. Project References

| Resource | Endpoint / URL |
| :--- | :--- |
| **Official Documentation** | [pyyaml.org](https://pyyaml.org/) • [jinja.palletsprojects.com](https://jinja.palletsprojects.com/) |
| **Public Git Repository** | [github.com/yaml/pyyaml](https://github.com/yaml/pyyaml) • [github.com/pallets/jinja](https://github.com/pallets/jinja) |
| **Official PyPI Package** | [pypi.org/project/PyYAML](https://pypi.org/project/PyYAML/) (`6.0.3`) • [pypi.org/project/jinja2](https://pypi.org/project/jinja2/) (`3.1.6`) |
| **DevOps CLI Integration** | [`src/devops_cli/commands/devcontainer.py`](file:///workspaces/devops-cli/src/devops_cli/commands/devcontainer.py) • [`src/devops_cli/k8s/`](file:///workspaces/devops-cli/src/devops_cli/k8s/) |

---

## 2. General Information & Architecture

**PyYAML** is a YAML 1.2 parser and emitter for Python. **Jinja2** is a fast, expressive, extensible templating engine powering template rendering across Python frameworks.

In `devops-cli`:
- **Kubernetes & GitOps YAML**: Parses and serializes Kubernetes manifests, ArgoCD Application specifications, Helm values overrides, and Kustomize patches.
- **DevContainer & Agent Scaffolding**: Uses Jinja2 templates (`src/devops_cli/templates/`) to dynamically scaffold `.devcontainer/devcontainer.json`, `AGENTS.md`, and MCP configuration files.

---

## 3. Comparable Projects & Tradeoffs

| Library | Strengths | Weaknesses | Why `devops-cli` Chose PyYAML + Jinja2 |
| :--- | :--- | :--- | :--- |
| **`PyYAML` + `jinja2`** | Battle-tested, supports `CSafeLoader`/`CSafeDumper` in C/Rust, expressive templating (loops, filters, macros). | PyYAML does not preserve round-trip comments natively. | **Selected**: The definitive industry standard for cloud-native manifest generation. |
| **`ruamel.yaml`** | Preserves YAML comments and exact formatting. | Slower parsing, complex API with frequent subtle behavioral shifts. | Rejected: PyYAML `safe_load` / `safe_dump` is cleaner and faster. |
| **`mako`** | High-performance templating engine. | Less standard in the Kubernetes and DevContainer ecosystem than Jinja2. | Rejected: Jinja2 is the universal standard across Ansible, Helm, and DevContainers. |
| **Python f-strings** | Built into Python. | Unsafe for complex multi-line templates, lacks template inheritance and reusable partial blocks. | Rejected: Jinja2 isolates template files cleanly from Python code logic. |

---

## 4. Key Concepts & Core Patterns

1. **`yaml.safe_load(text)`**: Always use `safe_load` instead of `yaml.load` to prevent arbitrary code execution vulnerabilities.
2. **`jinja2.Environment`**: Configured with `FileSystemLoader` and strict auto-escaping options.
3. **Template Inheritance**: Reuses base template headers across DevContainer configurations.

---

## 5. Common & Advanced Usage Examples

### Safe YAML Parsing
```python
import yaml


def load_k8s_manifest(manifest_text: str) -> dict:
    try:
        return yaml.safe_load(manifest_text) or {}
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid YAML syntax: {exc}")
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
