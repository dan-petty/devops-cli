"""The ansible-runner ad-hoc tasks of `devops infra`: the SSH check of `status --ping` (#5123), and
the render of the node service, the unit restart and the reboot of `devops infra node` (#5128).

An ad-hoc task runs one Ansible module on the hosts of a pattern, in the export of an infra repo:
`ansible-runner run <export> --artifact-dir <folder> --ident <ident> --omit-env-files --quiet
--hosts <pattern> -m <module> -a <args> --cmdline=<words>`. The words after `--cmdline=` go to
`ansible`: the inventory, the connection bound of 10 s, `--become` for a task that changes a host
(else `ansible_become=false`), the task bound when the task has one, and the key of `devops ssh`
when there is one. The run uses the `ansible.cfg` of the export, and host key checks stay on:
ansible-runner turns them off unless the environment sets `ANSIBLE_HOST_KEY_CHECKING`. The job
events (`<folder>/<ident>/job_events/*.json`) give the result of each host, and the artifact
folder is removed after the read.
"""

from __future__ import annotations

import json
import os
import shlex
import shutil
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from devops_cli.core.process import run_subprocess
from devops_cli.infra.ansible_facts import RUNNER_COMMAND, AnsibleTool
from devops_cli.lang import MESSAGES
from devops_cli.security.sanitizer import mask_secrets

# The bound of the SSH connection to one host (`ansible -T`): it ends before the bound of the run.
SSH_CONNECT_TIMEOUT_SECONDS: Final[int] = 10
EVENT_OK: Final[str] = "runner_on_ok"
EVENT_FAILED: Final[str] = "runner_on_failed"
EVENT_UNREACHABLE: Final[str] = "runner_on_unreachable"
_HOST_EVENTS: Final[frozenset[str]] = frozenset({EVENT_OK, EVENT_FAILED, EVENT_UNREACHABLE})
_ARTIFACT_PREFIX: Final[str] = "devops-infra-ad-hoc-"
_JOB_EVENTS: Final[str] = "job_events"
_PARTIAL_SUFFIX: Final[str] = "-partial.json"
_MESSAGE: Final[str] = "msg"


def tool_env(tool: AnsibleTool) -> dict[str, str]:
    """The environment that a run of the Ansible tool environment adds: its folder first on PATH,
    so ansible-runner finds `ansible`, and host key checks on."""
    path = os.environ.get("PATH", "")
    return {
        "PATH": os.pathsep.join(filter(None, (str(tool.bin_dir or ""), path))),
        "ANSIBLE_HOST_KEY_CHECKING": "True",
    }


@dataclass(frozen=True)
class AdHocTask:
    """One Ansible module with its arguments, whether it runs with become, and its bound in
    seconds (`ansible --task-timeout`), when it has one."""

    module: str
    args: str
    become: bool = False
    task_timeout: int | None = None


def ad_hoc_argv(
    tool: AnsibleTool,
    root: Path,
    sources: tuple[str, ...],
    key: Path | None,
    task: AdHocTask,
    *,
    pattern: str,
    artifact_dir: Path,
    ident: str,
    limit: str | None = None,
) -> list[str]:
    """`ansible-runner run` of `task` on the hosts of `pattern` (and `limit`) of the export at
    `root`."""
    words = [word for source in sources for word in ("-i", source)]
    words += ["-T", str(SSH_CONNECT_TIMEOUT_SECONDS)]
    words += ["--become"] if task.become else ["-e", "ansible_become=false"]
    if task.task_timeout is not None:
        words += ["--task-timeout", str(task.task_timeout)]
    if key is not None:
        words += ["-e", f"ansible_ssh_private_key_file={key}"]
    argv = tool.argv(
        RUNNER_COMMAND,
        "run",
        str(root),
        "--artifact-dir",
        str(artifact_dir),
        "--ident",
        ident,
        "--omit-env-files",
        "--quiet",
        "--hosts",
        pattern,
    )
    if limit:
        argv += ["--limit", limit]
    return [*argv, "-m", task.module, "-a", task.args, f"--cmdline={shlex.join(words)}"]


def read_job_events(folder: Path) -> list[dict[str, Any]]:
    """The job events in `folder`, in the order of their counter; none when the run wrote none.
    ansible-runner writes each event as `<counter>-<uuid>.json` with a rename, and a run that
    stops can leave the callback's `<uuid>-partial.json`, which is not an event."""
    events = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in folder.glob("*.json")
        if not path.name.endswith(_PARTIAL_SUFFIX)
    ]
    return sorted(events, key=lambda event: int(event.get("counter") or 0))


@dataclass(frozen=True)
class HostResult:
    """The result of a task on one host: its event and the `res` of the event."""

    event: str
    res: dict[str, Any]

    @property
    def ok(self) -> bool:
        return self.event == EVENT_OK

    @property
    def reason(self) -> str:
        """The message of the result, with each secret masked."""
        return mask_secrets(str(self.res.get(_MESSAGE) or ""))


@dataclass(frozen=True)
class AdHocOutcome:
    """How one ad-hoc run ended: its module, the result of each host that it reached, its exit
    code and the last line of its output."""

    module: str
    hosts: dict[str, HostResult]
    returncode: int
    detail: str

    def problem(self, host: str) -> str | None:
        """Why the task did not end well on `host`; none when it did."""
        texts = MESSAGES.infra
        result = self.hosts.get(host)
        if result is None:
            return texts.node_task_no_result.format(
                host=host, code=self.returncode, detail=self.detail
            )
        if result.event == EVENT_UNREACHABLE:
            return texts.node_task_unreachable.format(
                module=self.module, host=host, reason=result.reason
            )
        if not result.ok:
            return texts.node_task_failed.format(
                module=self.module, host=host, reason=result.reason
            )
        return None

    def value(self, host: str, key: str) -> Any:
        """The value of `key` in the result of `host`; none when the host gave no result."""
        result = self.hosts.get(host)
        return result.res.get(key) if result is not None else None


@dataclass(frozen=True)
class AdHoc:
    """The ad-hoc tasks of the export of an infra repo at `root`, with its inventory and the key
    of `devops ssh`."""

    tool: AnsibleTool
    root: Path
    sources: tuple[str, ...]
    key: Path | None

    def run(
        self, task: AdHocTask, pattern: str, *, timeout: float, limit: str | None = None
    ) -> AdHocOutcome:
        """Run `task` on the hosts of `pattern` within `timeout` seconds, and read the result of
        each host. The artifact folder is removed after the read."""
        artifact_dir = Path(tempfile.mkdtemp(prefix=_ARTIFACT_PREFIX))
        ident = uuid.uuid4().hex
        try:
            result = run_subprocess(
                ad_hoc_argv(
                    self.tool,
                    self.root,
                    self.sources,
                    self.key,
                    task,
                    pattern=pattern,
                    artifact_dir=artifact_dir,
                    ident=ident,
                    limit=limit,
                ),
                env=tool_env(self.tool),
                quiet=True,
                timeout=timeout,
            )
            events = read_job_events(artifact_dir / ident / _JOB_EVENTS)
        finally:
            shutil.rmtree(artifact_dir, ignore_errors=True)
        hosts: dict[str, HostResult] = {}
        for event in events:
            data = event.get("event_data") or {}
            host = data.get("host")
            if event.get("event") in _HOST_EVENTS and host:
                hosts[str(host)] = HostResult(str(event["event"]), dict(data.get("res") or {}))
        return AdHocOutcome(
            module=task.module,
            hosts=hosts,
            returncode=result.returncode,
            detail=_last_line(result.stderr or result.stdout),
        )


def _last_line(text: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return mask_secrets(lines[-1]) if lines else ""


__all__ = [
    "EVENT_FAILED",
    "EVENT_OK",
    "EVENT_UNREACHABLE",
    "SSH_CONNECT_TIMEOUT_SECONDS",
    "AdHoc",
    "AdHocOutcome",
    "AdHocTask",
    "HostResult",
    "ad_hoc_argv",
    "read_job_events",
    "tool_env",
]
