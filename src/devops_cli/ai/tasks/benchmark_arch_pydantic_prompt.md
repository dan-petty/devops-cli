Refactor this legacy dictionary-based configuration loader to modern Python 3.14+ using Pydantic v2 (`pydantic.BaseModel`, `Field`, `model_validator`, strict typing) following a step-by-step chain-of-thought refactoring process:

### Legacy Implementation:
```python
class ServerConfig:
    def __init__(self, data: dict):
        self.host = data.get("host", "127.0.0.1")
        self.port = int(data.get("port", 8080))
        self.ssl_enabled = bool(data.get("ssl_enabled", False))
        self.cert_path = data.get("cert_path")
        if self.ssl_enabled and not self.cert_path:
            raise Exception("cert_path required when ssl is on")
```

### Refactoring Requirements:
1. **Analyze Invariants**: Map data types, port ranges (1-65535), default values, and conditional invariants (`cert_path` required when `ssl_enabled=True`).
2. **Model Construction**: Use `pydantic.BaseModel` with `model_config = ConfigDict(frozen=True)` and strict static typing.
3. **Cross-Field Validation**: Use `@model_validator(mode="after")` for conditional validation with clean `ValueError` messages.
4. **Environment Parsing**: Support environment variable aliases or settings integration.

Provide the complete, strictly typed Python 3.14+ implementation.
