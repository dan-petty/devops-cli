# Code Library: Pydantic v2 & Pydantic-Settings (Data Validation & Configuration)

## 1. Project References

| Resource | Endpoint / URL |
| :--- | :--- |
| **Official Documentation** | [docs.pydantic.dev](https://docs.pydantic.dev/latest/) • [docs.pydantic.dev/latest/concepts/pydantic_settings/](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) |
| **Public Git Repository** | [github.com/pydantic/pydantic](https://github.com/pydantic/pydantic) • [github.com/pydantic/pydantic-settings](https://github.com/pydantic/pydantic-settings) |
| **Official PyPI Package** | [pypi.org/project/pydantic](https://pypi.org/project/pydantic/) (`2.13.4`) • [pypi.org/project/pydantic-settings](https://pypi.org/project/pydantic-settings/) (`2.15.0`) |
| **DevOps CLI Integration** | [`src/devops_cli/models/`](file:///workspaces/devops-cli/src/devops_cli/models/) • [`src/devops_cli/config/settings.py`](file:///workspaces/devops-cli/src/devops_cli/config/settings.py) |

---

## 2. General Information & Architecture

**Pydantic v2** is the industry-standard data validation and settings management library for Python. Re-engineered in Rust via `pydantic-core`, Pydantic v2 delivers 5x–50x performance improvements over v1, comprehensive JSON Schema generation, recursive model validation, strict type coercion, and seamless serialization.

In `devops-cli`:
- **Domain Modeling**: All domain entities (`Finding`, `ReviewSession`, `AgentUsage`, `TLSBundle`, `K8sPodStatus`) inherit from `pydantic.BaseModel`.
- **Layered Settings**: `pydantic_settings.BaseSettings` coordinates resolution across CLI flags $\rightarrow$ Environment variables (`DEVOPS_CLI_*`) $\rightarrow$ Config files $\rightarrow$ Defaults.
- **Zero Mutable Defaults**: All collection fields enforce `Field(default_factory=list)` or `Field(default_factory=dict)` to guarantee immutability across executions.

---

## 3. Comparable Projects & Tradeoffs

| Library | Strengths | Weaknesses | Why `devops-cli` Chose Pydantic v2 |
| :--- | :--- | :--- | :--- |
| **`pydantic` v2** | Blazing speed (Rust core), strict Mypy plugin, automatic JSON Schema export, deep AI framework integration (PydanticAI, FastMCP). | Breaking changes from v1 API (now standardized in v2). | **Selected**: Foundational data backbone across entire modern Python AI and Cloud ecosystem. |
| **`dataclasses`** (Stdlib) | Built into standard library, zero overhead. | No automatic type validation, no JSON schema generation, no robust deserialization or field aliasing. | Rejected: Insufficient for parsing external LLM payloads, complex configs, and JSON schemas. |
| **`attrs`** | Flexible class generator with validators. | Less standard JSON Schema generation, smaller ecosystem integration compared to Pydantic. | Rejected: Lacks native FastAPI, FastMCP, and PydanticAI interoperability. |
| **`marshmallow`** | Schema-based serialization/deserialization. | Slower Python-only validation, verbose separate schema definitions from model classes. | Rejected: Pydantic defines data models and schemas in a single concise class definition. |

---

## 4. Key Concepts & Core Patterns

1. **`BaseModel` & `Field`**:
   ```python
   from pydantic import BaseModel, Field


   class MetricSummary(BaseModel):
       metric_name: str
       sample_count: int = 0
       latency_p95_ms: float = Field(default=0.0, ge=0.0)
       tags: dict[str, str] = Field(default_factory=dict)
   ```
2. **Settings Hierarchies with `BaseSettings`**:
   ```python
   from pydantic_settings import BaseSettings, SettingsConfigDict


   class AppSettings(BaseSettings):
       model_config = SettingsConfigDict(env_prefix="DEVOPS_CLI_", case_sensitive=False)
       github_token: str | None = None
       log_level: str = "INFO"
   ```
3. **Model Serialization**:
   - `model.model_dump()`: Returns clean Python dictionary.
   - `model.model_dump_json(indent=2)`: Returns formatted JSON string.
   - `Model.model_validate(data)`: Strictly validates incoming dict/JSON.

---

## 5. Common & Advanced Usage Examples

### Complex Domain Entity with Aliases and Validation
```python
from pydantic import BaseModel, Field


class ReviewFinding(BaseModel):
    id: str
    persona: str = "devsecops"
    severity: str = Field(pattern=r"^(CRITICAL|HIGH|MEDIUM|LOW|INFO)$")
    title: str
    location: str
    description: str
    remediation: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    details: dict[str, str] = Field(default_factory=dict)


# Deserialization & Serialization
finding = ReviewFinding.model_validate(
    {
        "id": "SEC-001",
        "severity": "HIGH",
        "title": "Hardcoded AWS Access Key",
        "location": "terraform/main.tf:14-16",
        "description": "Plaintext secret detected in IaC configuration.",
    }
)
assert finding.persona == "devsecops"
```

---

## 6. Best Practices & Security Standards

1. **Strict Type Annotations**: Always enforce full type hints on all model fields (`A | B` syntax for Python 3.14+).
2. **Never Use Mutable Defaults**: Always use `Field(default_factory=list)` instead of `default=[]` to avoid shared state across model instances.
3. **Sensitive Field Protection**: Mark sensitive credentials with `Field(exclude=True)` to prevent accidental leakage in logs or serialized reports.
