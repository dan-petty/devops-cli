"""API contract grounding engine for anti-hallucination review prompt synthesis."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from pathlib import Path

from devops_cli.ai.rag.library_store import (
    LibraryVectorStore,
    _format_class_signature,
    _format_fn_signature,
    library_contracts_dir,
)
from devops_cli.core.repo import is_own_source_repository
from devops_cli.models.library import ClassSignature, FunctionSignature
from devops_cli.security.sanitizer import sanitize_prompt_boundary_tags

logger = logging.getLogger(__name__)

_DEFAULT_MAX_GROUNDED_CONTRACTS = 6


def _format_signature_block(sig: FunctionSignature | ClassSignature) -> str:
    """Format a FunctionSignature or ClassSignature as a clean Python stub."""
    if isinstance(sig, FunctionSignature):
        fn_str = _format_fn_signature(sig)
        doc = f'    """{sig.docstring.strip().splitlines()[0]}"""\n' if sig.docstring else ""
        return f"{fn_str}:\n{doc}    ..."
    if isinstance(sig, ClassSignature):
        cls_str = _format_class_signature(sig)
        doc = f'    """{sig.docstring.strip().splitlines()[0]}"""\n' if sig.docstring else ""
        methods_stub = "\n".join(
            f"    {_format_fn_signature(m)}: ..." for m in list(sig.methods.values())[:5]
        )
        body = f"{doc}{methods_stub}" if methods_stub else f"{doc}    ..."
        return f"{cls_str}:\n{body}"
    return str(sig)


def _lies_within(path: Path, root: Path) -> bool:
    """Whether `path` resolves inside `root`; an unresolvable path counts as inside."""
    try:
        return path.resolve().is_relative_to(root.resolve())
    except OSError, RuntimeError:
        return True


def _reviewed_tree_holds(contracts_dir: Path, reviewed_tree: Path) -> bool:
    """Whether contracts at `contracts_dir` lie inside `reviewed_tree`, which could have written
    them. devops-cli's own repository is exempt (`is_own_source_repository`): its code already
    runs in this process, and a review started there keeps its contracts in its `.data`."""
    return _lies_within(contracts_dir, reviewed_tree) and not is_own_source_repository(
        reviewed_tree
    )


def resolve_grounded_contracts(
    imports: Sequence[tuple[str, str | None]],
    store: LibraryVectorStore | None = None,
    max_contracts: int = _DEFAULT_MAX_GROUNDED_CONTRACTS,
    contracts_dir: Path | None = None,
    reviewed_tree: Path | None = None,
) -> list[FunctionSignature | ClassSignature]:
    """Resolve verified API contracts from installed library contracts for imported symbols.

    Contracts come from devops-cli's data directory (`library_contracts_dir`), never the working
    directory (#972). Contracts inside `reviewed_tree`, the tree under review, are refused, even
    in a data directory the user named there: the prompt states them as ground truth the model
    must not dispute, and that tree could have written them. A review of devops-cli's own
    repository still reads its `.data/libraries` (`_reviewed_tree_holds`).
    """
    if not imports:
        return []

    active_store = store or LibraryVectorStore(
        local_contracts_dir=contracts_dir or library_contracts_dir()
    )
    if reviewed_tree is not None and _reviewed_tree_holds(
        active_store.local_contracts_dir, reviewed_tree
    ):
        logger.warning(
            "Library contracts at %s lie inside the tree under review and are not read",
            active_store.local_contracts_dir,
        )
        return []

    resolved: list[FunctionSignature | ClassSignature] = []
    seen_qualnames: set[str] = set()

    for mod, sym in imports:
        if len(resolved) >= max_contracts:
            break

        pkg_candidate = mod.split(".", 1)[0]
        query_sym = sym or mod

        # Attempt exact lookup
        match = active_store.lookup_symbol(query_sym, package=pkg_candidate)
        if match is None and sym:
            # Fallback: try looking up qualified name
            match = active_store.lookup_symbol(f"{mod}.{sym}", package=pkg_candidate)

        if match is not None:
            qual = getattr(match, "qualname", getattr(match, "name", query_sym))
            if qual not in seen_qualnames:
                seen_qualnames.add(qual)
                resolved.append(match)

    return resolved


def format_contract_grounding_for_prompt(
    contracts: Sequence[FunctionSignature | ClassSignature],
) -> str:
    """Format verified library contracts into anti-hallucination prompt context block."""
    if not contracts:
        return ""

    formatted_blocks = [_format_signature_block(c) for c in contracts]
    combined = "\n\n".join(formatted_blocks)
    sanitized = sanitize_prompt_boundary_tags(combined)

    return (
        "\n\n### Verified Third-Party API Contracts (Ground Truth)\n"
        "```python\n"
        f"{sanitized}\n"
        "```\n"
        "> **Anti-Hallucination Guardrail**: The above signatures are verified ground-truth contracts "
        "extracted from installed packages in this environment. Do NOT claim these functions, classes, "
        "methods, parameter names, or type annotations do not exist or are invalid."
    )
