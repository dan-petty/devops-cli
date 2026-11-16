"""English language pack for devops-cli.

The names load on first access, so a CLI start that reads the help catalog runs this package
without the message and error catalogs (#3550).
"""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from devops_cli.lang.en.errors import ERRORS, ErrorCatalog
    from devops_cli.lang.en.help import HELP, HelpCatalog
    from devops_cli.lang.en.messages import MESSAGES, LanguageCatalog

_ATTR_MAP: dict[str, tuple[str, str]] = {
    "ERRORS": ("devops_cli.lang.en.errors", "ERRORS"),
    "ErrorCatalog": ("devops_cli.lang.en.errors", "ErrorCatalog"),
    "HELP": ("devops_cli.lang.en.help", "HELP"),
    "HelpCatalog": ("devops_cli.lang.en.help", "HelpCatalog"),
    "LanguageCatalog": ("devops_cli.lang.en.messages", "LanguageCatalog"),
    "MESSAGES": ("devops_cli.lang.en.messages", "MESSAGES"),
}


def __getattr__(name: str) -> Any:
    if name in _ATTR_MAP:
        mod_name, attr = _ATTR_MAP[name]
        val = getattr(importlib.import_module(mod_name), attr)
        globals()[name] = val
        return val
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "ERRORS",
    "HELP",
    "MESSAGES",
    "ErrorCatalog",
    "HelpCatalog",
    "LanguageCatalog",
]
