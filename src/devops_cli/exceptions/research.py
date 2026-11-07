"""Research agent exception definitions for devops-cli."""

from __future__ import annotations

from devops_cli.exceptions.base import DevOpsCLIError


class InventoryError(DevOpsCLIError):
    """Raised when `devops research inventory` cannot read or parse a file that holds pins (#3896)."""

    error_code = "RESEARCH_INVENTORY_ERROR"
