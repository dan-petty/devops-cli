1. Inherits from `pydantic.BaseModel` with `model_config = ConfigDict(frozen=True)`.
2. Type annotations with modern Python syntax (`str`, `int`, `bool`, `Path | None`).
3. Validation: `Field(ge=1, le=65535)` on port.
4. `@model_validator(mode='after')` verifying `cert_path is not None` when `ssl_enabled is True` with `ValueError`.
5. Clean default values and documentation docstrings.
