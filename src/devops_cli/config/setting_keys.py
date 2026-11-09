"""Find the keys of a settings mapping that no settings model declares (#4093).

Most models of `Settings` set `extra="ignore"`, so a key that a change removes from a model loads
with no error when a file still holds it. This walk reports such a key by its dotted path.
"""

from __future__ import annotations

import typing
from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel

from devops_cli.config.settings import Settings


def unknown_setting_keys(
    config: Mapping[str, Any], model: type[BaseModel] = Settings, *, prefix: str = ""
) -> list[str]:
    """The dotted path of each key of `config` that no field of `model` or of a nested model
    declares, in the order of the mapping.

    The walk goes into a value when the field is a model, alone or in an optional, and into each
    value of a mapping field whose values are a model. It reads no key of a mapping field itself,
    because such a field holds keys of the user and not names of fields.
    """
    unknown: list[str] = []
    for key, value in config.items():
        path = f"{prefix}{key}"
        field = model.model_fields.get(key)
        if field is None:
            unknown.append(path)
            continue
        values = _mapping_value_model(field.annotation)
        if values is not None and isinstance(value, Mapping):
            for name, item in value.items():
                if isinstance(item, Mapping):
                    unknown.extend(unknown_setting_keys(item, values, prefix=f"{path}.{name}."))
            continue
        nested = _nested_model(field.annotation)
        if nested is not None and isinstance(value, Mapping):
            unknown.extend(unknown_setting_keys(value, nested, prefix=f"{path}."))
    return unknown


def _mapping_value_model(annotation: Any) -> type[BaseModel] | None:
    """The model that the values of a mapping annotation are, else nothing."""
    if typing.get_origin(annotation) not in (dict, Mapping):
        return None
    arguments = typing.get_args(annotation)
    value = arguments[1] if len(arguments) == 2 else None
    if isinstance(value, type) and issubclass(value, BaseModel):
        return value
    return None


def _nested_model(annotation: Any) -> type[BaseModel] | None:
    """The model that an annotation names, alone or in an optional, else nothing."""
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return annotation
    if typing.get_origin(annotation) in (dict, Mapping):
        return None
    for argument in typing.get_args(annotation):
        if isinstance(argument, type) and issubclass(argument, BaseModel):
            return argument
    return None
