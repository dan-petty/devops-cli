"""The run of the pinned Helm (`tools.lock`) that chart tests share (#5200).

A test that calls it carries `@pytest.mark.live("helm")`, so it skips where Helm is not installed.
CI's test job installs it.
"""

from __future__ import annotations

import subprocess
from pathlib import Path


def helm(*args: str | Path, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    """Run the Helm on PATH and keep its output for the failure message."""
    return subprocess.run(
        ["helm", *map(str, args)], capture_output=True, text=True, check=False, cwd=cwd
    )
