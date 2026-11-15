"""The run of the pinned Vale (`tools.lock`) that the docs tests share (#5157).

A test that calls it carries `@pytest.mark.live("vale")`, so it skips where Vale is not installed.
CI's test job installs it.
"""

from __future__ import annotations

import subprocess
from pathlib import Path


def vale(*args: str | Path, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    """Run the Vale on PATH and keep its output for the failure message."""
    return subprocess.run(
        ["vale", *map(str, args)], capture_output=True, text=True, check=False, cwd=cwd
    )
