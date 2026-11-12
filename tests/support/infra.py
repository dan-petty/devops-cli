"""An Ansible infra repo in the shape of dan-petty/homelab, and the answers of its local reads (#5121).

`tests/fixtures/infra/homelab_shape/` holds the repo: the groups, host_vars and playbook names of
homelab, with `example.com` hosts and RFC 5737 addresses, and a `.devops/project.toml` that
declares its profile. `ansible_config.json` and
`ansible_inventory.json` beside it are the output of the pinned `ansible-config dump --format json
--only-changed` and `ansible-inventory -i ansible/inventory/hosts.yaml --list` in a copy of the repo, with the folder of the copy
as `{root}`. To record them again, copy the repo to a scratch folder, run the two commands there
with only `HOME`, `PATH` and `LANG` set, and put `{root}` in place of the folder.

The CI workflow of the complete repo is written into the copy, not kept under `tests/fixtures/`,
so no workflow check reads it as a workflow of this repository.

A command reads an infra repo at the head of its default branch at `origin`, exported into a
private folder (#5162). `answer_default_branch` answers the git commands of that read, and its
export writes the files of a folder, by default the checkout, as the tar file of `git archive`.
The Ansible reads run in the export, so their answers name the export where the recording names
`{root}`.

`runner_events/<run>.jsonl` holds the job events of a recorded check-mode run of the pinned
`ansible-runner` (#5124), one event on each line, in the order of their counter. The probe in
`runner_events/probe/` is a small infra repo with one host for each case: the k3s agent role of
dan-petty/homelab on node-3, the changes, skips and restart handler of a demo unit on node-1, a
reboot on node-2 and a failed task on node-4. `agent` is the run with `--limit
node-3.example.com:!offline` (exit code 0, status `successful`), and `site` is the run on all hosts
(exit code 2, status `failed`). To record them again, copy the probe to `<scratch>/project`, make
the folder `<scratch>/state` with the files `node-token` and `demo.yaml` (`value: 41`), and run
`ansible-runner run <scratch> --playbook ansible/playbooks/site.yaml --ident <run> --limit <limit>
--quiet "--cmdline=--check --diff -v -i ansible/inventory/hosts.ini -e state_dir=<scratch>/state"`
with only `HOME`, `LANG` and the environment of `runner_env` set, and `probe/bin` first on PATH.
Then put `{project}` in place of `<scratch>/project`, `/srv/example` in place of `<scratch>/state`,
and `/root` in place of the home folder and its user.
"""

from __future__ import annotations

import json
import shutil
import tarfile
from collections.abc import Callable, Collection, Sequence
from pathlib import Path
from typing import Any, Final

import pytest

from devops_cli.tools_lock import load_tools_lock, tool_install_dir
from tests.support.fakes.process import ProcessAnswer, ProcessCall, ProcessFake
from tests.support.paths import FIXTURES
from tests.support.tools import link_at_pin

INFRA_FIXTURES: Final[Path] = FIXTURES / "infra"
RUNNER_EVENTS: Final[Path] = INFRA_FIXTURES / "runner_events"
# The exit code and the status file of each recorded run.
RECORDED_RUNS: Final[dict[str, tuple[int, str]]] = {
    "agent": (0, "successful"),
    "site": (2, "failed"),
}
_PROJECT_MARK: Final[str] = "{project}"
INFRA_REPO_SHAPE: Final[Path] = INFRA_FIXTURES / "homelab_shape"
KUBE_CONTEXT: Final[str] = "homelab-example"
IN_SERVICE_HOSTS: Final[tuple[str, ...]] = tuple(f"192.0.2.{n}" for n in range(1, 5))
SSH_KEY_NAME: Final[str] = "ansible-id_ed25519-20261101"
DEFAULT_BRANCH: Final[str] = "origin/main"
ORIGIN_COMMIT: Final[str] = "f5961bd2da6856e31914037c0f048337989dfbe7"
OLD_COMMIT: Final[str] = "6b5a7fa70022cffbdc09ff0e5c6e82ac7916b864"
_OUTPUT: Final[str] = "--output="
_CONFIG_OPTION: Final[str] = "-c"
_GIT_DIR: Final[str] = ".git"
_CI_WORKFLOW: Final[str] = ".github/workflows/lint.yml"
_CI_TEXT: Final[str] = (
    "name: lint\non: [pull_request]\npermissions: {}\njobs:\n  lint:\n    runs-on: ubuntu-latest\n"
    "    steps:\n      - run: ansible-lint\n"
)


def ansible_bin_dir() -> Path:
    """The `bin` folder of the pinned Ansible tool environment under the user data root."""
    tool = load_tools_lock().python["ansible-core"]
    return tool_install_dir("ansible-core", tool.version).joinpath(*tool.command_dir)


def recorded_read(name: str, root: Path) -> Any:
    """The recorded output `ansible_<name>.json`, with `root` in place of `{root}`."""
    text = (INFRA_FIXTURES / f"ansible_{name}.json").read_text(encoding="utf-8")
    return json.loads(text.replace("{root}", str(root)))


def recorded_events(run: str, project: Path) -> list[dict[str, Any]]:
    """The job events of the recorded run `run`, with `project` in place of `{project}`."""
    text = (RUNNER_EVENTS / f"{run}.jsonl").read_text(encoding="utf-8")
    return [json.loads(line) for line in text.replace(_PROJECT_MARK, str(project)).splitlines()]


def answer_runner(fake: ProcessFake, bin_dir: Path, run: str, *, status: str | None = None) -> None:
    """Answer `ansible-runner run <private data folder>` as the recorded run `run` ended: its job
    events in `artifacts/<ident>/job_events/<counter>-<uuid>.json` with the project folder of the
    call, its `status` and `rc` files, and its exit code. `status` gives another status file,
    such as `timeout`."""
    returncode, recorded = RECORDED_RUNS[run]

    def answer(call: ProcessCall) -> ProcessAnswer:
        private = Path(call.argv[2])
        ident = call.argv[call.argv.index("--ident") + 1]
        artifacts = private / "artifacts" / ident
        job_events = artifacts / "job_events"
        job_events.mkdir(parents=True)
        for event in recorded_events(run, private / "project"):
            name = f"{event['counter']}-{event['uuid']}.json"
            (job_events / name).write_text(json.dumps(event), encoding="utf-8")
        (artifacts / "status").write_text(status or recorded, encoding="utf-8")
        (artifacts / "rc").write_text(str(returncode), encoding="utf-8")
        return ProcessAnswer(returncode=returncode)

    fake.answer([str(bin_dir / "ansible-runner"), "run"], answer)


def answer_default_branch(
    fake: ProcessFake,
    checkout: Path,
    *,
    tree: Path | None = None,
    commit: str = ORIGIN_COMMIT,
    checkout_branch: str = "main",
    checkout_commit: str | None = None,
) -> None:
    """Answer the git commands that read the default branch of the checkout at `checkout`: the
    fetch, `origin/main` at `commit`, the checkout on `checkout_branch` at `checkout_commit`
    (default `commit`), and the export, which writes the files of `tree` (default the checkout,
    as they are at the time of the call) as a tar file."""
    fake.answer(git_command(checkout, "fetch", "--quiet", "origin"), ProcessAnswer())
    fake.answer(
        git_command(checkout, "rev-parse", "refs/remotes/origin/HEAD"),
        ProcessAnswer(stdout=f"{commit}\n{DEFAULT_BRANCH}\n"),
    )
    fake.answer(
        git_command(checkout, "rev-parse", "HEAD"),
        ProcessAnswer(stdout=f"{checkout_commit or commit}\n{checkout_branch}\n"),
    )
    fake.answer(git_command(checkout, "archive"), _export(tree or checkout))


def git_words(call: ProcessCall) -> tuple[str, ...]:
    """The words of a `git -C <folder>` call after the folder and each `-c <value>`."""
    words = call.argv[3:]
    while words[:1] == (_CONFIG_OPTION,):
        words = words[2:]
    return words


def git_command(checkout: Path, *words: str) -> Callable[[ProcessCall], bool]:
    """Whether a call is `git -C <checkout>` whose words after each `-c <value>` start with
    `words`."""

    def matches(call: ProcessCall) -> bool:
        return call.argv[:3] == ("git", "-C", str(checkout)) and (
            git_words(call)[: len(words)] == words
        )

    return matches


def _export(source: Path) -> Callable[[ProcessCall], ProcessAnswer]:
    """The answer of `git archive --output=<file>`: a tar file of the files of `source`, with no
    `.git` folder."""

    def answer(call: ProcessCall) -> ProcessAnswer:
        output = next(word[len(_OUTPUT) :] for word in call.argv if word.startswith(_OUTPUT))
        with tarfile.open(output, "w") as tar:
            for path in sorted(source.rglob("*")):
                relative = path.relative_to(source)
                if relative.parts[0] != _GIT_DIR:
                    tar.add(path, arcname=relative.as_posix(), recursive=False)
        return ProcessAnswer()

    return answer


def in_export(text: str, root: Path) -> Callable[[ProcessCall], ProcessAnswer]:
    """An answer that prints `text` with the folder of the call, the export, in place of
    `root`."""
    return lambda call: ProcessAnswer(stdout=text.replace(str(root), str(call.cwd)))


def answer_infra_reads(
    fake: ProcessFake,
    root: Path,
    *,
    config: Any = None,
    inventory: Any = None,
    contexts: Sequence[str] = (KUBE_CONTEXT,),
    known_hosts: Collection[str] = IN_SERVICE_HOSTS,
) -> None:
    """Answer the reads of an onboarding of the repo at `root`: the read of its default branch,
    whose export holds the files of the checkout, the config dump and the inventory in the export
    (recorded unless given, with each path of `root` in the export), the kubeconfig contexts, and
    `ssh-keygen -F`, which finds each host of `known_hosts`."""
    answer_default_branch(fake, root)
    bin_dir = ansible_bin_dir()
    dump = recorded_read("config", root) if config is None else config
    listing = recorded_read("inventory", root) if inventory is None else inventory
    fake.answer([str(bin_dir / "ansible-config"), "dump"], in_export(json.dumps(dump), root))
    fake.answer([str(bin_dir / "ansible-inventory")], in_export(json.dumps(listing), root))
    fake.answer(
        ["kubectl", "config", "get-contexts"],
        ProcessAnswer(stdout="".join(f"{name}\n" for name in contexts)),
    )

    def keygen(call: ProcessCall) -> ProcessAnswer:
        host = call.argv[2]
        if host in known_hosts:
            return ProcessAnswer(stdout=f"# Host {host} found: line 1\n{host} ssh-ed25519 AAAA\n")
        return ProcessAnswer(returncode=1)

    fake.answer(["ssh-keygen", "-F"], keygen)


@pytest.fixture
def infra_repo(tmp_path: Path) -> Path:
    """A copy of the homelab-shaped repo at `<tmp_path>/repo`, with a CI workflow."""
    repo = tmp_path / "repo"
    shutil.copytree(INFRA_REPO_SHAPE, repo)
    workflow = repo / _CI_WORKFLOW
    workflow.parent.mkdir(parents=True)
    workflow.write_text(_CI_TEXT, encoding="utf-8")
    return repo


@pytest.fixture
def ansible_installed(tmp_path: Path) -> Path:
    """The pinned Ansible tool environment, laid out as `devops install-tools` leaves it."""
    target = tmp_path / "bin"
    link_at_pin("ansible-core", target)
    return ansible_bin_dir()


@pytest.fixture
def ssh_key_dir(tmp_path: Path) -> Path:
    """A `devops ssh` key folder with one key of the prefix `ansible`."""
    key_dir = tmp_path / "ssh"
    key_dir.mkdir()
    (key_dir / SSH_KEY_NAME).write_text("private\n", encoding="utf-8")
    (key_dir / f"{SSH_KEY_NAME}.pub").write_text("ssh-ed25519 AAAA ansible\n", encoding="utf-8")
    return key_dir
