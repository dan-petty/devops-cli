"""The Terraform pins: each provider in a `required_providers` block under `tf/` (#3896).

python-hcl2 parses the files. Its result has no line for an attribute, so the line is the one
that opens the provider's block. The version of a provider is its constraint, as written (`~> 5.0`).
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from devops_cli.exceptions.research import InventoryError
from devops_cli.research.files import LineIndex, matching_files, relative
from devops_cli.research.models import Component, ComponentKind, Ecosystem

TERRAFORM_GLOBS = ("tf/**/*.tf",)
_NOT_A_PROVIDER = "__is_block__"
_DEFAULT_NAMESPACE = "hashicorp"


def _opens_block(key: str) -> Callable[[str], bool]:
    """A test for the line that opens the attribute `key = {`."""

    def opens(line: str) -> bool:
        return line.strip().startswith(key) and line.rstrip().endswith("{")

    return opens


def _read_file(root: Path, path: Path) -> list[Component]:
    import hcl2

    text = path.read_text(encoding="utf-8")
    file = relative(root, path)
    try:
        document = hcl2.loads(
            text,
            serialization_options=hcl2.SerializationOptions(
                strip_string_quotes=True, with_comments=False
            ),
        )
    # python-hcl2 raises the parse errors of lark, a library of its own that this project does not import.
    except Exception as exc:
        raise InventoryError(
            f"Cannot read the pins of {file}: {exc}", details={"file": file}
        ) from exc
    lines = LineIndex(text)
    found: list[Component] = []
    for block in document.get("terraform", []):
        for providers in block.get("required_providers", []):
            for local_name, provider in providers.items():
                if local_name == _NOT_A_PROVIDER or not isinstance(provider, dict):
                    continue
                found.append(
                    Component(
                        kind=ComponentKind.TERRAFORM_PROVIDER,
                        ecosystem=Ecosystem.TERRAFORM,
                        name=provider.get("source", f"{_DEFAULT_NAMESPACE}/{local_name}"),
                        version=provider.get("version", ""),
                        file=file,
                        line=lines.find_where(local_name, _opens_block(local_name)),
                    )
                )
    return found


def read_terraform_pins(root: Path) -> list[Component]:
    """The provider components of the `.tf` files under `tf/` in `root`."""
    found: list[Component] = []
    for path in matching_files(root, *TERRAFORM_GLOBS):
        found.extend(_read_file(root, path))
    return found
