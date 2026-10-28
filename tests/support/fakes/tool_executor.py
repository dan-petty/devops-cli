"""The review tools a review starts, faked at the tool executor's seam, and the
`tool_executor_fake` fixture that installs the fake (#772, ADR 0007).

The seam is `ToolExecutor` in `devops_cli.security.tool_executor`: code that runs a review tool
takes an executor and calls `run(request)`. The real executor starts the tool in a bubblewrap
sandbox. This fake starts nothing. It answers each request with the `ToolAnswer` scripted for the
request's tool, an empty success when none is scripted, and keeps every request in `requests`.

Everything inside the process runs for real. The fake builds each `ToolRun` with the same
`record_tool_run` that the real executor calls. So the fake refuses a target outside the tree, and
it reads the digests and the commit from real files and a real git tree. By default the fake
records as the sandbox executor does: it refuses a checkout that git cannot read and a file that it
cannot digest, and it records the network profile of the request, else `none`. A fake that stands in
for `DirectToolExecutor` takes `require_commit=False`, `require_files=False` and
`network=CONST_TOOL_NETWORK_HOST`, and records such a run as the direct executor does: with no
commit, or with the digest `unavailable`, and with the network `host`. It refuses a request that
selects a network profile, as the direct executor does. `scanner_fake`
(`tests/support/fakes/scanners.py`) records the commit and the digests as the direct executor does,
and the network profile of the request, as the sandbox executor does.

A test scripts only what the programs of the host decide. These are the version and the binary
digest of the tool, its exit code, its output and whether it ran out of time. A tool that is not
installed has no binary. So the `version` and `binary_sha256` of the answer replace two values. The
real executor reads them from the tools lock and from the binary on disk.

The contract suite is `tests/test_tool_executor_contract.py`. It runs each shared case over this
fake and over the real executor, with a stand-in for the tool on disk. It holds both to the same
answers.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from devops_cli.security.tool_executor import ToolRequest, ToolResult

# How the fake names itself in the record of a run: no tool starts, so nothing is confined.
FAKE_EXECUTOR = "fake"
# The digest a scripted answer gives a binary that no test scripted a digest for.
FAKE_BINARY_SHA256 = hashlib.sha256(b"tool executor fake binary").hexdigest()


@dataclass(frozen=True)
class ToolAnswer:
    """What the fake answers for a tool: the tool's identity and how its run ended."""

    exit_code: int = 0
    stdout: str = ""
    stderr: str = ""
    timed_out: bool = False
    version: str = "0.0.0"
    binary_sha256: str = FAKE_BINARY_SHA256


class ToolExecutorFake:
    """A `ToolExecutor` that answers the scripted `ToolAnswer` of each request's tool."""

    def __init__(
        self,
        *,
        require_commit: bool = True,
        require_files: bool = True,
        network: str | None = None,
    ) -> None:
        self.requests: list[ToolRequest] = []
        self._answers: dict[str, ToolAnswer] = {}
        self._require_commit = require_commit
        self._require_files = require_files
        self._network = network

    def script(self, tool: str, answer: ToolAnswer) -> None:
        """Answer every later request for `tool` with `answer`."""
        self._answers[tool] = answer

    def run(self, request: ToolRequest) -> ToolResult:
        """Record `request`, then answer it as the real executor does, starting nothing."""
        # Imported here. The whole suite loads this module at start. The executor pulls in the
        # sandbox engine (`devops_cli.docker.engine`) and the canary, which most tests never need.
        from devops_cli.security.tool_executor import ToolResult, record_tool_run

        answer = self._answers.get(request.tool, ToolAnswer())
        run = record_tool_run(
            request,
            version=answer.version,
            binary_sha256=answer.binary_sha256,
            executor=FAKE_EXECUTOR,
            network=self._network,
            require_commit=self._require_commit,
            require_files=self._require_files,
        )
        self.requests.append(request)
        return ToolResult(
            run=run,
            exit_code=answer.exit_code,
            stdout=answer.stdout,
            stderr=answer.stderr,
            timed_out=answer.timed_out,
        )


@pytest.fixture
def tool_executor_fake() -> ToolExecutorFake:
    """A tool executor that starts no tool, for code that takes a `ToolExecutor`."""
    return ToolExecutorFake()
