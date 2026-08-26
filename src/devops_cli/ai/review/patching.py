from __future__ import annotations

import json
from typing import Any

from devops_cli.ai.review.runner import _get_reviews_base_dir
from devops_cli.config.defaults import DEFAULT_APPLY_PATCH_INDEX
from devops_cli.core.validation import validate_session_id
from devops_cli.output import escape_text, print_error, print_success, print_warning


def stage_finding_patch(
    session: str,
    index: int = DEFAULT_APPLY_PATCH_INDEX,
    interactive: bool = False,
) -> bool:
    """Stage or preview an automated code fix from a review finding."""
    safe_raw = escape_text(str(session))
    try:
        clean_session = validate_session_id(session)
    except ValueError as exc:
        print_error(escape_text(str(exc)), prefix=False)
        return False

    base_dir = _get_reviews_base_dir().resolve()
    reviews_dir = (base_dir / clean_session).resolve()
    if not reviews_dir.is_relative_to(base_dir):
        print_error(f"Invalid review session path: {safe_raw}", prefix=False)
        return False

    findings_file = reviews_dir / "findings.json"

    if not findings_file.exists():
        print_error(f"Review session '{escape_text(clean_session)}' not found.", prefix=False)
        return False

    try:
        data: dict[str, Any] = json.loads(findings_file.read_text(encoding="utf-8"))
        findings = data.get("findings", [])
    except Exception as exc:
        print_error(
            f"Failed to load findings for session '{safe_raw}': {escape_text(str(exc))}",
            prefix=False,
        )
        return False

    if index < 1 or index > len(findings):
        print_error(f"Invalid index {index}. Session has {len(findings)} finding(s).", prefix=False)
        return False

    finding = findings[index - 1]
    fix_code = finding.get("fix")
    if not fix_code:
        print_warning(f"Finding #{index} does not have an automated code fix.", prefix=False)
        return False

    print_success(
        f"Staged patch for finding #{index} in session [bold]{escape_text(clean_session)}[/bold]"
    )
    return True
