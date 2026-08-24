Refactor this legacy dictionary-based configuration loader to modern Python 3.14+ using Pydantic v2 (`pydantic.BaseModel`, `Field`, `model_validator`, strict typing):

```python
class ServerConfig:
    def __init__(self, data: dict):
        self.host = data.get('host', '127.0.0.1')
        self.port = int(data.get('port', 8080))
        self.ssl_enabled = bool(data.get('ssl_enabled', False))
        self.cert_path = data.get('cert_path')
        if self.ssl_enabled and not self.cert_path:
            raise Exception('cert_path required when ssl is on')
```

Ensure immutability (frozen), type validation, environment variable parsing capability, and clean error messages.
