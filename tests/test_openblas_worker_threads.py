"""Test processes start no idle OpenBLAS threads against the container's pids.max (#1664)."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from tests.support.paths import REPO_ROOT
from tests.support.waits import THREAD_HANDOFF_BOUND_SECONDS

PROC_STATUS = Path("/proc/self/status")
THREADS_AFTER_CONFTEST_THEN_NUMPY = (
    "import re\n"
    "import tests.conftest\n"
    "import numpy\n"
    "status = open('/proc/self/status', encoding='utf-8').read()\n"
    "print(re.search(r'^Threads:\\s+(\\d+)', status, re.M).group(1))\n"
)


@pytest.mark.skipif(not PROC_STATUS.is_file(), reason="reads a thread count from /proc")
def test_numpy_imported_after_the_root_conftest_starts_no_openblas_threads() -> None:
    """A process that imports tests/conftest.py and then numpy holds one thread, whatever
    OPENBLAS_NUM_THREADS the caller set, so the conftest sets it before anything it imports can
    load numpy. OpenBLAS otherwise parks an idle thread per CPU in every xdist worker and every
    child process, which a 16-CPU host counts 15 times against pids.max."""
    environment = {key: value for key, value in os.environ.items() if key != "OPENBLAS_NUM_THREADS"}
    probe = subprocess.run(
        [sys.executable, "-c", THREADS_AFTER_CONFTEST_THEN_NUMPY],
        cwd=REPO_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=True,
        timeout=THREAD_HANDOFF_BOUND_SECONDS,
    )

    assert probe.stdout.strip() == "1"
