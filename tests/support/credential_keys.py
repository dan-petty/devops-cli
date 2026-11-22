"""The credential-named keys of a parsed config, for the tests of the sandbox ConfigMap (#4147).

The sandbox ConfigMap of the planner run Job holds a copy of the config with each credential key
removed. A test parses the rendered config and names each key that still holds a credential.
"""

from __future__ import annotations

from devops_cli.security.sanitizer import is_secret_parameter_name


def credential_key_paths(value: object, prefix: str = "") -> list[str]:
    """Each key of `value`, at any depth of maps and lists, that names a credential.

    A number or a boolean under such a name, such as `token_budget`, is no credential: each
    credential of the settings is text.
    """
    if isinstance(value, dict):
        paths: list[str] = []
        for key, item in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            if is_secret_parameter_name(str(key)) and not isinstance(item, int | float):
                paths.append(path)
            else:
                paths.extend(credential_key_paths(item, path))
        return paths
    if isinstance(value, list):
        return [
            path
            for index, item in enumerate(value)
            for path in credential_key_paths(item, f"{prefix}[{index}]")
        ]
    return []
