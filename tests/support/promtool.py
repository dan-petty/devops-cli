"""The run of the pinned promtool (`tools.lock`) that the monitoring tests share (#2472, #4680).

A test that calls it carries `@pytest.mark.live("promtool")`, so it skips where promtool is not
installed. CI's test job installs it.
"""

from __future__ import annotations

import subprocess
from pathlib import Path


def promtool(*args: str | Path) -> subprocess.CompletedProcess[str]:
    """Run the promtool on PATH and keep its output for the failure message."""
    return subprocess.run(
        ["promtool", *map(str, args)], capture_output=True, text=True, check=False
    )
