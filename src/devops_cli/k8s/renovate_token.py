"""The rules for the Renovate config script and the token file (#6020)."""

from __future__ import annotations

from typing import Final

RENOVATE_TOKEN_PATH: Final = "/token/github-token"


def token_file_problems(config_js: str) -> list[str]:
    """Report problems in the Renovate config script.

    The script must name the default token path, read it, and remove the file after the read.
    """
    problems: list[str] = []
    if RENOVATE_TOKEN_PATH not in config_js:
        problems.append(f"the script does not name the default token path {RENOVATE_TOKEN_PATH}")
    if "readFileSync" not in config_js:
        problems.append(f"the script does not read {RENOVATE_TOKEN_PATH}")
    if "unlinkSync" not in config_js:
        problems.append(f"the script does not remove {RENOVATE_TOKEN_PATH}")
    if "readFileSync" in config_js and "unlinkSync" in config_js:
        read_idx = config_js.find("readFileSync")
        unlink_idx = config_js.find("unlinkSync")
        if unlink_idx < read_idx:
            problems.append(f"the script removes {RENOVATE_TOKEN_PATH} before the read")
    return problems
