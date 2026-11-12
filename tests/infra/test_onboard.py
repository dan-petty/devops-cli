"""The onboarding report of an Ansible infra repo: one row for each check, read from local files
and local tool output only (#5121).

The repo is a copy of `tests/fixtures/infra/homelab_shape/`, in the shape of dan-petty/homelab.
Each case takes one item away from the complete repo and checks the row of that item.
"""

from __future__ import annotations

import json
import shutil
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from devops_cli.config.settings import load_settings
from devops_cli.infra.onboard import check_onboarding, resolve_target
from devops_cli.models.infra import OnboardReport, OnboardState
from tests.support.fakes.process import ProcessAnswer, ProcessFake
from tests.support.infra import (
    IN_SERVICE_HOSTS,
    KUBE_CONTEXT,
    SSH_KEY_NAME,
    answer_infra_reads,
    recorded_read,
)

REPO = "example-org/infra"
PRESENT = OnboardState.PRESENT
MISSING = OnboardState.MISSING
LISTED = OnboardState.LISTED
NOT_READABLE = OnboardState.NOT_READABLE


@dataclass
class Onboarding:
    """The repo, its reads and its settings entry, which a case changes before the check."""

    repo: Path
    process: ProcessFake
    config: Callable[..., Path]
    dump: Any
    inventory: Any
    contexts: tuple[str, ...] = (KUBE_CONTEXT,)
    known_hosts: tuple[str, ...] = IN_SERVICE_HOSTS
    entry: dict[str, Any] | None = field(default_factory=dict)

    def report(self, **options: Any) -> OnboardReport:
        answer_infra_reads(
            self.process,
            self.repo,
            config=self.dump,
            inventory=self.inventory,
            contexts=self.contexts,
            known_hosts=self.known_hosts,
        )
        if self.entry is not None:
            entry = {"repo": REPO, "path": str(self.repo), "kube_context": KUBE_CONTEXT}
            self.config(infra={"repos": [entry | self.entry]})
        settings = load_settings()
        path = self.repo if self.entry is None else None
        return check_onboarding(
            resolve_target(REPO, path=path, settings=settings), settings, **options
        )


@pytest.fixture
def onboarding(
    infra_repo: Path,
    ansible_installed: Path,
    ssh_key_dir: Path,
    known_hosts: Path,
    process_fake: ProcessFake,
    config: Callable[..., Path],
    person_caller: None,
) -> Onboarding:
    known_hosts.parent.mkdir(parents=True)
    known_hosts.write_text("", encoding="utf-8")
    config(ssh={"key_dir": str(ssh_key_dir)})
    return Onboarding(
        repo=infra_repo,
        process=process_fake,
        config=config,
        dump=recorded_read("config", infra_repo),
        inventory=recorded_read("inventory", infra_repo),
    )


def _states(report: OnboardReport) -> list[tuple[int, OnboardState]]:
    return [(row.number, row.state) for row in report.rows]


def test_a_complete_repo_has_every_row_present(onboarding: Onboarding) -> None:
    report = onboarding.report()

    assert _states(report) == [(number, PRESENT) for number in range(1, 18)]
    assert [row.items for row in report.rows[3:7]] == [
        (
            "debian_nodes: 4 hosts",
            "gpu_nodes: 4 hosts",
            "k3s_agent: 3 hosts",
            "k3s_cluster: 4 hosts",
            "k3s_server: 1 host",
            "offline: 2 hosts",
        ),
        ("node-5.example.com", "node-6.example.com"),
        (
            "ansible/playbooks/00_bootstrap_user.yaml",
            "ansible/playbooks/01_bootstrap.yaml",
            "ansible/playbooks/02_nvidia.yaml",
            "ansible/playbooks/03_k3s.yaml",
            "ansible/playbooks/04_gpu_validation.yaml",
            "ansible/playbooks/05_cluster_maintenance.yaml",
            "ansible/playbooks/06_cluster_backup.yaml",
            "ansible/playbooks/07_cluster_upgrade.yaml",
            "ansible/playbooks/08_mount_nvme.yaml",
            "ansible/playbooks/09_system_update.yaml",
            "ansible/playbooks/10_rolling_restart.yaml",
            "ansible/playbooks/11_secrets_encryption.yaml",
            "ansible/playbooks/12_move_ollama_models.yaml",
            "ansible/playbooks/health_check.yaml",
            "ansible/playbooks/site.yaml",
        ),
        ("common", "k3s_agent", "k3s_server", "k8s_gpu", "nvidia"),
    ]
    assert (report.rows[10].items, report.rows[11].items) == ((SSH_KEY_NAME,), (KUBE_CONTEXT,))
    assert report.rows[1].items == (
        'extends = "ansible-k8s" (.devops/project.toml)',
        'ansible.inventory = ["ansible/inventory/hosts.yaml"] (.devops/project.toml)',
        'ansible.playbook_dir = "ansible/playbooks" (.devops/project.toml)',
        'ansible.roles_path = ["ansible/roles"] (.devops/project.toml)',
        'ansible.offline_group = "offline" (template: ansible-k8s)',
    )


def test_the_report_reads_only_local_tools(onboarding: Onboarding) -> None:
    """The reads are the config dump and the inventory in the repo, one `ssh-keygen -F` for each
    host in service, and the kubeconfig contexts: no SSH connection and no request."""
    onboarding.report()

    assert [
        (call.argv[0].rsplit("/", 1)[-1], *call.argv[1:3]) for call in onboarding.process.calls
    ] == [
        ("ansible-config", "dump", "--format"),
        ("ansible-inventory", "-i", "ansible/inventory/hosts.yaml"),
        *(("ssh-keygen", "-F", host) for host in IN_SERVICE_HOSTS),
        ("kubectl", "config", "get-contexts"),
    ]
    assert {call.cwd for call in onboarding.process.calls[:2]} == {onboarding.repo}


def _without_config_file(o: Onboarding) -> None:
    (o.repo / "ansible.cfg").unlink()
    o.dump = [item for item in o.dump if "name" not in item]


def _without_project_file(o: Onboarding) -> None:
    shutil.rmtree(o.repo / ".devops")


def _without_type(o: Onboarding) -> None:
    shutil.rmtree(o.repo / ".devops")
    (o.repo / "ansible.cfg").unlink()


def _without_hosts(o: Onboarding) -> None:
    o.inventory = {"_meta": {"hostvars": {}}, "all": {"children": ["ungrouped"]}}


def _without_offline_group(o: Onboarding) -> None:
    o.inventory.pop("offline")
    o.inventory["all"]["children"].remove("offline")


def _without_playbooks(o: Onboarding) -> None:
    shutil.rmtree(o.repo / "ansible" / "playbooks")


def _without_roles(o: Onboarding) -> None:
    shutil.rmtree(o.repo / "ansible" / "roles")


def _without_collections_file(o: Onboarding) -> None:
    (o.repo / "collections" / "requirements.yml").unlink()


def _with_a_collection_range(o: Onboarding) -> None:
    path = o.repo / "collections" / "requirements.yml"
    path.write_text(
        path.read_text(encoding="utf-8").replace("version: 11.4.0", "version: '>=11.0.0'"),
        encoding="utf-8",
    )


def _with_host_key_checks_off_in_the_config(o: Onboarding) -> None:
    origin = str(o.repo / "ansible.cfg")
    o.dump.insert(0, {"name": "HOST_KEY_CHECKING", "origin": origin, "value": False})
    plugins = next(item for item in o.dump if "CONNECTION_PLUGINS" in item)
    ssh = plugins["CONNECTION_PLUGINS"][0]["ssh"]
    ssh.append({"name": "host_key_checking", "origin": origin, "value": False})
    for setting in ssh:
        if setting["name"] == "ssh_args":
            setting["value"] += " -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"


def _with_host_key_checks_off_in_the_inventory(o: Onboarding) -> None:
    for hostvars in o.inventory["_meta"]["hostvars"].values():
        hostvars["ansible_ssh_common_args"] = "-o StrictHostKeyChecking=no"


def _with_a_host_key_unknown(o: Onboarding) -> None:
    o.known_hosts = IN_SERVICE_HOSTS[1:]


def _without_ssh_key(o: Onboarding) -> None:
    for path in Path(load_settings().ssh.key_dir).iterdir():
        path.unlink()


def _with_a_kube_context_not_in_the_kubeconfig(o: Onboarding) -> None:
    o.contexts = ("other-cluster",)


def _without_ci(o: Onboarding) -> None:
    shutil.rmtree(o.repo / ".github")


def _with_a_host_without_node_service(o: Onboarding) -> None:
    o.inventory["_meta"]["hostvars"]["node-2.example.com"].pop("devops_infra_node_service")


def _with_a_task_that_runs_in_check_mode(o: Onboarding) -> None:
    path = o.repo / "ansible" / "playbooks" / "health_check.yaml"
    path.write_text(
        path.read_text(encoding="utf-8") + "      check_mode: false\n", encoding="utf-8"
    )


def _with_node_targets_in_the_makefile(o: Onboarding) -> None:
    path = o.repo / "Makefile"
    path.write_text(
        path.read_text(encoding="utf-8")
        + "\ndrain-node-2: ## Drain node-2\n\t./drain.sh node-2\n"
        + "\nrolling-restart: ## Reboot each node\n\tansible-playbook restart.yaml\n",
        encoding="utf-8",
    )


def _without_entry(o: Onboarding) -> None:
    o.entry = None


@pytest.mark.parametrize(
    ("change", "number", "state", "items"),
    [
        pytest.param(
            _without_project_file,
            2,
            LISTED,
            (
                'extends = "ansible-k8s" (detected: ansible.cfg)',
                'ansible.inventory = ["ansible/inventory/hosts.yaml"] (detected: ansible.cfg)',
                'ansible.playbook_dir = "ansible/playbooks" (detected: ansible/playbooks)',
                'ansible.roles_path = ["ansible/roles"] (detected: ansible.cfg)',
            ),
            id="project-file",
        ),
        pytest.param(_without_type, 2, MISSING, (), id="project-type"),
        pytest.param(_without_config_file, 3, MISSING, (), id="ansible.cfg"),
        pytest.param(_without_hosts, 4, MISSING, (), id="inventory"),
        pytest.param(_without_offline_group, 5, MISSING, (), id="offline-group"),
        pytest.param(_without_playbooks, 6, MISSING, (), id="playbooks"),
        pytest.param(_without_roles, 7, MISSING, (), id="roles"),
        pytest.param(_without_collections_file, 8, MISSING, (), id="collections-file"),
        pytest.param(
            _with_a_collection_range,
            8,
            MISSING,
            ("community.general >=11.0.0",),
            id="collection-range",
        ),
        pytest.param(
            _with_host_key_checks_off_in_the_config,
            9,
            MISSING,
            (
                "ansible.cfg: host_key_checking = False",
                "ansible.cfg: ssh_args StrictHostKeyChecking=no",
                "ansible.cfg: ssh_args UserKnownHostsFile=/dev/null",
            ),
            id="host-key-checks-config",
        ),
        pytest.param(
            _with_host_key_checks_off_in_the_inventory,
            9,
            MISSING,
            ("inventory: ansible_ssh_common_args StrictHostKeyChecking=no (6 hosts)",),
            id="host-key-checks-inventory",
        ),
        pytest.param(
            _with_a_host_key_unknown, 10, MISSING, ("node-1.example.com",), id="known-hosts"
        ),
        pytest.param(_without_ssh_key, 11, MISSING, (), id="ssh-key"),
        pytest.param(
            _with_a_kube_context_not_in_the_kubeconfig,
            12,
            MISSING,
            ("other-cluster",),
            id="kube-context",
        ),
        pytest.param(_without_ci, 13, MISSING, (), id="ci"),
        pytest.param(
            _with_a_host_without_node_service,
            14,
            LISTED,
            ("node-2.example.com",),
            id="node-service",
        ),
        pytest.param(
            _with_a_task_that_runs_in_check_mode,
            15,
            LISTED,
            ("ansible/playbooks/health_check.yaml:5 Read the uptime",),
            id="check-mode-false",
        ),
        pytest.param(
            _with_node_targets_in_the_makefile,
            16,
            LISTED,
            ("drain-node-2", "rolling-restart"),
            id="makefile-node-targets",
        ),
        pytest.param(_without_entry, 17, MISSING, (), id="settings-entry"),
    ],
)
def test_a_repo_that_lacks_an_item_has_its_row_changed(
    onboarding: Onboarding,
    change: Callable[[Onboarding], None],
    number: int,
    state: OnboardState,
    items: tuple[str, ...],
) -> None:
    change(onboarding)

    report = onboarding.report()

    row = report.rows[number - 1]
    assert (row.number, row.state, row.items) == (number, state, items)
    assert row.step if state is MISSING else True


def test_collections_row_names_the_collections_that_the_plays_use(onboarding: Onboarding) -> None:
    _without_collections_file(onboarding)

    row = onboarding.report().rows[7]

    assert row.reason == (
        "collections/requirements.yml is not in the repository. The plays use ansible.posix, "
        "community.general, kubernetes.core."
    )


def test_a_kube_context_that_no_option_or_entry_names_is_missing(onboarding: Onboarding) -> None:
    onboarding.entry = {"kube_context": None}
    onboarding.contexts = ("homelab-example", "other-cluster")

    row = onboarding.report().rows[11]

    assert (row.state, row.items) == (MISSING, ("homelab-example", "other-cluster"))


def test_options_set_the_entry_that_confirm_writes(onboarding: Onboarding) -> None:
    onboarding.entry = None

    report = onboarding.report(kube_context=KUBE_CONTEXT, ssh_key_prefix="ansible")

    assert report.entry == {
        "repo": REPO,
        "path": str(onboarding.repo),
        "kube_context": KUBE_CONTEXT,
        "ssh_key_prefix": "ansible",
        "agent_access": "none",
    }


def test_without_the_tool_environment_the_ansible_rows_are_not_readable(
    infra_repo: Path,
    ssh_key_dir: Path,
    known_hosts: Path,
    process_fake: ProcessFake,
    config: Callable[..., Path],
    person_caller: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No install of `devops install-tools`, and no `ansible-runner` on PATH."""
    found = shutil.which
    monkeypatch.setattr(
        shutil, "which", lambda cmd, *a, **k: None if cmd == "ansible-runner" else found(cmd)
    )
    config(
        ssh={"key_dir": str(ssh_key_dir)},
        infra={"repos": [{"repo": REPO, "path": str(infra_repo), "kube_context": KUBE_CONTEXT}]},
    )
    answer_infra_reads(process_fake, infra_repo)
    settings = load_settings()

    report = check_onboarding(resolve_target(REPO, path=None, settings=settings), settings)

    assert [state for _, state in _states(report)] == [
        MISSING,
        PRESENT,
        NOT_READABLE,
        NOT_READABLE,
        NOT_READABLE,
        PRESENT,
        PRESENT,
        PRESENT,
        NOT_READABLE,
        NOT_READABLE,
        PRESENT,
        PRESENT,
        PRESENT,
        NOT_READABLE,
        PRESENT,
        PRESENT,
        PRESENT,
    ]
    assert [call.argv[0] for call in process_fake.calls] == ["kubectl"]


def test_the_ansible_runner_on_path_names_the_tool_environment(
    infra_repo: Path,
    ssh_key_dir: Path,
    known_hosts: Path,
    process_fake: ProcessFake,
    config: Callable[..., Path],
    person_caller: None,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """With no install of `devops install-tools`, the commands come from the folder of the
    `ansible-runner` on PATH, as the devcontainer image links it."""
    image_bin = tmp_path / "devops-tools" / "ansible-core" / "bin"
    image_bin.mkdir(parents=True)
    (image_bin / "ansible-runner").write_text("#!/bin/sh\n", encoding="utf-8")
    link = tmp_path / "usr-local-bin" / "ansible-runner"
    link.parent.mkdir()
    link.symlink_to(image_bin / "ansible-runner")
    found = shutil.which
    monkeypatch.setattr(
        shutil, "which", lambda cmd, *a, **k: str(link) if cmd == "ansible-runner" else found(cmd)
    )
    config(
        ssh={"key_dir": str(ssh_key_dir)},
        infra={"repos": [{"repo": REPO, "path": str(infra_repo), "kube_context": KUBE_CONTEXT}]},
    )
    dump = json.dumps(recorded_read("config", infra_repo))
    process_fake.answer([str(image_bin / "ansible-config"), "dump"], ProcessAnswer(stdout=dump))
    settings = load_settings()

    report = check_onboarding(resolve_target(REPO, path=None, settings=settings), settings)

    assert (report.rows[0].state, report.rows[0].reason, report.rows[2].state) == (
        PRESENT,
        f"the ansible-runner on PATH, in {image_bin}",
        PRESENT,
    )


def test_the_playbook_folder_comes_from_the_project_profile(onboarding: Onboarding) -> None:
    path = onboarding.repo / ".devops" / "project.toml"
    path.write_text(
        path.read_text(encoding="utf-8").replace('"ansible/playbooks"', '"plays"'), encoding="utf-8"
    )

    row = onboarding.report().rows[5]

    assert (row.state, row.reason) == (MISSING, "No playbook is in plays.")
