"""SIGTERM exports the telemetry of the process, and the process then stops as it did before
(#5916).

Kubernetes stops the pod of a Job for its deadline, an eviction or a node drain with SIGTERM. The
metrics since the last export were lost then. The child case starts a real interpreter: the
handler before is the default action there, and that action ends the process. `PYTHONPATH` names
this tree's `src`, so a replay of `devops ci fail-to-pass --base origin/main` runs the base source.
Each case imports the handler module in its body, so a replay on the base collects every case.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path
from types import FrameType

import pytest

from devops_cli.entry import main
from devops_cli.telemetry.exporter import OtlpSignal
from devops_cli.telemetry.instruments import AI_TOKENS_TOTAL, emit
from tests.support.fakes.otlp import FakeCollector, metric_points
from tests.support.paths import REPO_ROOT
from tests.support.waits import wait_while_running

_TOKENS = {"operation": "chat", "type": "prompt"}

# The child records the signal of each export request in the file that its first argument names,
# then waits for a signal. It runs with no OTLP collector: the recorder is its exporter.
#
# The child waits for SIGTERM on the read end of its wakeup pipe, not in `signal.pause()`. A SIGTERM
# that came after the last check for signals and before the pause system call only set the flag of
# the C handler, and the pause then waited for a second signal that never came, so the test hung to
# the bound of pytest-timeout (#6048). The C handler also writes a byte to the wakeup pipe, so the
# read returns for a signal that came before it, and the Python handler runs as the read returns.
_CHILD = """
import os
import signal
import sys

from devops_cli.telemetry.instruments import AI_TOKENS_TOTAL, emit
from devops_cli.telemetry.sigterm_export import install_sigterm_export
from devops_cli.telemetry.tracer import install_exporter


class Recorder:
    endpoint = "http://otlp.example.com:4318"

    def export(self, otlp_signal, body, content_type):
        with open(sys.argv[1], "a", encoding="utf-8") as record:
            record.write(f"{otlp_signal.value}\\n")

    def probe(self, timeout):
        raise NotImplementedError

    def close(self):
        return None


install_exporter(Recorder())
install_sigterm_export()
emit(AI_TOKENS_TOTAL, 120.0, {"operation": "chat", "type": "prompt"})
wakeup_read, wakeup_write = os.pipe()
os.set_blocking(wakeup_write, False)
signal.set_wakeup_fd(wakeup_write)
print("ready", flush=True)
os.read(wakeup_read, 1)
"""


class _HandlerBefore:
    """A Python handler of SIGTERM that records each call."""

    def __init__(self) -> None:
        self.signals: list[int] = []

    def __call__(self, signum: int, _frame: FrameType | None) -> None:
        self.signals.append(signum)


@pytest.fixture
def handler_before() -> Iterator[_HandlerBefore]:
    """A recording handler of SIGTERM in place of the one before the test, which comes back."""
    handler = _HandlerBefore()
    previous = signal.signal(signal.SIGTERM, handler)
    yield handler
    signal.signal(signal.SIGTERM, previous)


def test_sigterm_exports_the_metrics_then_calls_the_handler_before(
    otlp: FakeCollector, handler_before: _HandlerBefore
) -> None:
    """Verify SIGTERM exports the tokens that the process counted, then runs the handler that was
    in place before."""
    from devops_cli.telemetry.sigterm_export import install_sigterm_export

    install_sigterm_export()
    emit(AI_TOKENS_TOTAL, 120.0, _TOKENS)

    signal.raise_signal(signal.SIGTERM)

    assert (
        metric_points(otlp.received(OtlpSignal.METRICS), AI_TOKENS_TOTAL.name),
        handler_before.signals,
    ) == ([(_TOKENS, 120.0)], [signal.SIGTERM])


def test_one_handler_stays_after_two_installs_and_the_uninstall_gives_back_the_one_before(
    handler_before: _HandlerBefore,
) -> None:
    """Verify a second install wraps no second handler, and the uninstall sets back the handler
    before the first install."""
    from devops_cli.telemetry.sigterm_export import install_sigterm_export, uninstall_sigterm_export

    install_sigterm_export()
    installed = signal.getsignal(signal.SIGTERM)
    install_sigterm_export()
    after_second = signal.getsignal(signal.SIGTERM)

    uninstall_sigterm_export()

    assert (
        installed is not handler_before,
        after_second is installed,
        signal.getsignal(signal.SIGTERM),
    ) == (True, True, handler_before)


def test_the_cli_entry_installs_the_export_at_sigterm(
    otlp: FakeCollector, handler_before: _HandlerBefore
) -> None:
    """Verify the `devops` entry point sets the handler, so SIGTERM exports in each command."""
    with pytest.raises(SystemExit) as exited:
        main(["--version"])
    emit(AI_TOKENS_TOTAL, 120.0, _TOKENS)

    signal.raise_signal(signal.SIGTERM)

    assert (
        exited.value.code,
        metric_points(otlp.received(OtlpSignal.METRICS), AI_TOKENS_TOTAL.name),
        handler_before.signals,
    ) == (0, [(_TOKENS, 120.0)], [signal.SIGTERM])


@pytest.mark.live("python")
@pytest.mark.real_sleep
def test_a_process_with_the_default_action_exports_then_ends_by_sigterm(tmp_path: Path) -> None:
    """Verify a process that had the default action for SIGTERM exports its metrics, and SIGTERM
    still ends it."""
    record = tmp_path / "exports.txt"
    output = tmp_path / "stdout.txt"
    with output.open("w", encoding="utf-8") as stdout:
        child = subprocess.Popen(
            [sys.executable, "-c", _CHILD, str(record)],
            cwd=tmp_path,
            env={**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")},
            stdout=stdout,
        )
    try:
        # The child writes its one line once it waits for the signal. SIGTERM goes also after
        # another line, so the assertion names that line and the test does not wait on.
        wait_while_running(lambda: output.read_text(encoding="utf-8").endswith("\n"), child)
        child.send_signal(signal.SIGTERM)
        returncode = child.wait()
    finally:
        # Each path kills and reaps the child; after its exit both calls return at once.
        child.kill()
        child.wait()

    exports = record.read_text(encoding="utf-8").split() if record.exists() else []
    assert (output.read_text(encoding="utf-8"), returncode, exports) == (
        "ready\n",
        -signal.SIGTERM,
        [OtlpSignal.METRICS.value],
    )
