"""A process that clears its dumpable flag keeps its environment from a child of its user (#2667).

The agent's shell of the implement job is a child of the job and runs as the same user, so it
could read `/proc/<job pid>/environ`, where the App's private key and the other secrets are. The
kernel refuses that read for a process that is not dumpable. The tests run real processes.
"""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from devops_cli.core import process_hardening
from devops_cli.exceptions import RoadmapImplementError

pytestmark = [
    pytest.mark.live("python3"),
    pytest.mark.skipif(sys.platform != "linux", reason="prctl and /proc are Linux only"),
    # A user with CAP_SYS_PTRACE reads any environment, whatever the flag says.
    pytest.mark.skipif(os.geteuid() == 0, reason="root may read any /proc/<pid>/environ"),
]

SECRET = "hardening-probe-value"

# Run as the parent. It holds SECRET in its starting environment, optionally clears its flag, and
# starts a child that reads the parent's environment and says what happened.
PARENT = textwrap.dedent(
    """
    import os, subprocess, sys
    if sys.argv[1] == "harden":
        from devops_cli.core.process_hardening import deny_environment_reads
        deny_environment_reads()
    child = (
        "import sys\\n"
        "try:\\n"
        "    data = open('/proc/' + sys.argv[1] + '/environ', 'rb').read()\\n"
        "    print('read', sys.argv[2].encode() in data)\\n"
        "except PermissionError:\\n"
        "    print('denied')\\n"
    )
    argv = [sys.executable, "-c", child, str(os.getpid()), os.environ["PROBE_NAME"]]
    done = subprocess.run(argv, capture_output=True, text=True)
    print(done.stdout.strip() or done.stderr.strip())
    """
)


def _child_sees(mode: str, tmp_path: Path) -> str:
    script = tmp_path / "parent.py"
    script.write_text(PARENT, encoding="utf-8")
    env = {**os.environ, "PROBE_NAME": SECRET}
    return subprocess.run(
        [sys.executable, str(script), mode],
        env=env,
        capture_output=True,
        text=True,
        check=True,
        timeout=60,
    ).stdout.strip()


def test_a_child_reads_the_environment_of_a_parent_that_did_not_harden(tmp_path: Path) -> None:
    """The control: without the call, the same user reads the environment of its parent."""
    assert _child_sees("plain", tmp_path) == "read True"


def test_a_child_cannot_read_the_environment_of_a_parent_that_hardened(tmp_path: Path) -> None:
    assert _child_sees("harden", tmp_path) == "denied"


def test_a_refusal_of_the_kernel_raises_and_names_the_call(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(process_hardening, "_prctl", lambda *_args: -1)
    with pytest.raises(RoadmapImplementError, match="PR_SET_DUMPABLE"):
        process_hardening.deny_environment_reads()
