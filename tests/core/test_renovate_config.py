"""The Renovate configuration: the shared preset `.github/renovate/base.json` that every Service
repository extends, and the repository parts in `.github/renovate.json`. Together they give each
pin of the repository a manager, a fixed schedule, limits for the CI cap, security updates at
once, and titles that pass the `Semantic PR title` check (#4896)."""

from __future__ import annotations

import fnmatch
import json
import re
import shlex
import subprocess
import tomllib
from collections.abc import Iterator
from functools import cache
from pathlib import Path
from typing import Any

import pytest
import yaml

from devops_cli.config.constants import CONST_OPENSPEC_GENERATED_GLOBS
from devops_cli.config.defaults import DEFAULT_PYTHON_VERSION
from devops_cli.roadmap.runner_tools import NODE_MAJOR, UV_VERSION
from devops_cli.roadmap.workflow_labels import WORKFLOW_LABELS
from devops_cli.tools_lock import load_tools_lock
from tests.support.paths import REPO_ROOT

_PRESET = "github>dan-petty/devops-cli//.github/renovate/base"

_IMAGE_WITH_TAG = re.compile(
    r"^\s*-?\s*image:\s*\S+:[\w][\w.-]*(?:@sha256:[0-9a-f]{64})?\s*$", re.MULTILINE
)

# The default file patterns of the built-in managers at Renovate 44.235.1
# (lib/modules/manager/<name>/index.ts). A configured pattern adds to them.
_DEFAULT_PATTERNS: dict[str, list[str]] = {
    "dockerfile": [
        "/(^|/|\\.)([Dd]ocker|[Cc]ontainer)file$/",
        "/(^|/)([Dd]ocker|[Cc]ontainer)file[^/]*$/",
    ],
    "github-actions": [
        "/(^|/)(workflow-templates|\\.(?:github|gitea|forgejo)/(?:workflows|actions))/.+\\.ya?ml$/",
        "/(^|/)action\\.ya?ml$/",
    ],
    "pre-commit": ["/(^|/)\\.pre-commit-config\\.ya?ml$/"],
    "pyenv": ["/(^|/)\\.python-version$/"],
    "nodenv": ["/(^|/)\\.node-version$/"],
    "pep621": ["/(^|/)pyproject\\.toml$/"],
    "devcontainer": [
        "/^.devcontainer/devcontainer.json$/",
        "/^.devcontainer.json$/",
        "/^.devcontainer/[^/]+/devcontainer.json$/",
    ],
    "terraform": ["**/*.tf", "**/*.tofu"],
    "npm": ["/(^|/)package\\.json$/"],
    "pip-compile": [],
    "helm-values": ["/(^|/)values\\.ya?ml$/"],
    "argocd": [],
    "kubernetes": [],
}

# The managers that Renovate 44.235.1 turns off by default.
_OFF_BY_DEFAULT = {"pre-commit"}

# The non-major updates of each ecosystem come in one pull request on the schedule.
_ECOSYSTEM_GROUPS = [
    "python dependencies",
    "github actions",
    "container images",
    "helm charts",
    "pre-commit hooks",
    "devcontainer features",
    "opentofu providers",
]

# A test compares the files of each group, so one pull request updates them all.
_COUPLED_GROUPS: dict[str, list[str]] = {
    "trivy": ["aquasecurity/trivy"],
    "argo": ["argoproj/argo-workflows", "quay.io/argoproj/workflow-controller"],
    "cloudflared": ["cloudflare/cloudflared"],
    "uv": ["astral-sh/uv", "ghcr.io/astral-sh/uv"],
    "gh": ["cli/cli"],
    "node": ["node"],
    "python runtime": ["python"],
    "ruff": ["ruff", "astral-sh/ruff-pre-commit"],
    "bandit": ["bandit"],
    "actionlint": ["kjanat/actionlint", "docker.io/kjanat/actionlint"],
    "openspec": ["@fission-ai/openspec"],
    "dcgm-exporter": ["dcgm-exporter", "nvcr.io/nvidia/k8s/dcgm-exporter"],
}

_SUMMARY_LIMIT = 60


def _load(*parts: str) -> dict[str, Any]:
    return json.loads(REPO_ROOT.joinpath(*parts).read_text(encoding="utf-8"))


def _renovate() -> dict[str, Any]:
    return _load(".github", "renovate.json")


def _preset() -> dict[str, Any]:
    return _load(".github", "renovate", "base.json")


def _rules() -> list[dict[str, Any]]:
    """The package rules in the order Renovate applies them: the preset's, then the repository's."""
    return [*_preset()["packageRules"], *_renovate()["packageRules"]]


def _without_description(rule: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in rule.items() if key != "description"}


@cache
def _tracked(*pathspecs: str) -> list[str]:
    out = subprocess.run(
        ["git", "ls-files", "--", *pathspecs],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return out.splitlines()


def _tracked_k8s_yaml() -> list[str]:
    return [name for name in _tracked("k8s") if name.endswith((".yaml", ".yml"))]


@cache
def _text(name: str) -> str:
    return (REPO_ROOT / name).read_text(encoding="utf-8")


def _python_pattern(js_pattern: str) -> re.Pattern[str]:
    """A Renovate match string as a Python pattern: JavaScript writes a named group `(?<n>…)`.
    Renovate compiles a match string with the flag `g` only, as Python's default."""
    return re.compile(js_pattern.replace("(?<", "(?P<"))


def _matches_file(pattern: str, name: str) -> bool:
    """Whether a Renovate file pattern, a `/regex/` or a glob, matches the path `name`."""
    if pattern.startswith("/") and pattern.endswith("/"):
        return _python_pattern(pattern[1:-1]).search(name) is not None
    return fnmatch.fnmatch(name, pattern)


def _manager_patterns(manager: str) -> list[str]:
    return [
        *_DEFAULT_PATTERNS[manager],
        *_renovate().get(manager, {}).get("managerFilePatterns", []),
    ]


def _manager_is_on(manager: str) -> bool:
    configured = {**_preset().get(manager, {}), **_renovate().get(manager, {})}
    turned_off = [
        rule
        for rule in _rules()
        if manager in rule.get("matchManagers", [])
        and rule.get("enabled") is False
        and set(_without_description(rule)) == {"matchManagers", "enabled"}
    ]
    return configured.get("enabled", manager not in _OFF_BY_DEFAULT) and not turned_off


def _custom_deps(name: str) -> list[tuple[str, str]]:
    """The (depName, currentValue) pairs that the custom managers find in the file `name`."""
    text = _text(name)
    found = []
    for manager in _renovate()["customManagers"]:
        if not any(_matches_file(p, name) for p in manager["managerFilePatterns"]):
            continue
        for pattern in manager["matchStrings"]:
            for match in _python_pattern(pattern).finditer(text):
                groups = match.groupdict()
                found.append(
                    (groups.get("depName") or manager["depNameTemplate"], groups["currentValue"])
                )
    return found


def test_the_repository_config_extends_only_the_shared_preset() -> None:
    """Every Service repository extends the same preset, and the preset extends
    `config:recommended`. `config:best-practices` adds a minimum release age to npm (#4810)."""
    assert (_renovate()["extends"], _preset()["extends"]) == ([_PRESET], ["config:recommended"])


def test_renovate_sets_no_minimum_release_age() -> None:
    """A release with a security or bug fix gets its pull request on the day it is published
    (CONTRIBUTING.md, Dependency Versions)."""
    assert ["minimumReleaseAge" in json.dumps(config) for config in (_preset(), _renovate())] == [
        False,
        False,
    ]


def test_updates_come_on_monday_and_a_patch_comes_at_once() -> None:
    """A patch release holds bug and security fixes, so it skips the weekly schedule in a branch
    of its own. Other updates wait for Monday (UTC), when one run opens a group per ecosystem."""
    preset = _preset()
    patch_rules = [
        _without_description(rule)
        for rule in preset["packageRules"]
        if rule.get("matchUpdateTypes") == ["patch"] and "schedule" in rule
    ]

    assert (
        preset["timezone"],
        preset["schedule"],
        preset["separateMinorPatch"],
        preset["lockFileMaintenance"]["schedule"],
        patch_rules,
    ) == (
        "UTC",
        ["* * * * 1"],
        True,
        ["* * * * 1"],
        [{"matchUpdateTypes": ["patch"], "schedule": ["at any time"]}],
    )


def test_the_limits_keep_renovate_within_the_ci_cap() -> None:
    """The account runs at most 20 jobs at a time, and one push starts about 25. Renovate opens
    at most 2 pull requests an hour and keeps 8 open, and it pushes an open one again only on a
    conflict: each push holds the current main, so no catch-up push follows a merge (#4667)."""
    preset = _preset()

    assert (
        preset["prHourlyLimit"],
        preset["prConcurrentLimit"],
        preset["vulnerabilityAlerts"]["prConcurrentLimit"],
        preset["rebaseWhen"],
        "rebaseWhen" in _renovate(),
    ) == (2, 8, 4, "conflicted", False)


def test_a_security_fix_comes_at_once_as_a_fix_with_the_newest_release() -> None:
    """OSV alerts work without Dependabot alerts. An alert pull request skips the schedule and the
    hourly limit, takes the newest release, and the Dashboard lists each unresolved CVE."""
    preset = _preset()

    assert (
        preset["osvVulnerabilityAlerts"],
        preset["vulnerabilityAlerts"],
        preset["dependencyDashboard"],
        preset["abandonmentThreshold"],
    ) == (
        True,
        {
            "labels": ["type/security", "scope/deps"],
            "commitMessagePrefix": "fix(deps):",
            "commitMessageSuffix": "",
            "prConcurrentLimit": 4,
            "vulnerabilityFixStrategy": "highest",
        },
        {
            "enabled": True,
            "title": "Dependency Dashboard",
            "labels": ["type/chore", "scope/deps"],
            "osvVulnerabilitySummary": "unresolved",
            "reportAbandonment": True,
        },
        "1 year",
    )


def test_a_migration_waits_for_an_approval_on_the_dashboard() -> None:
    """A Python minor or major, and a major of Node, PostgreSQL or Mattermost, need a migration.
    The Dashboard lists them until a person or an agent approves one."""
    approvals = [
        (rule["matchPackageNames"], rule["matchUpdateTypes"])
        for rule in _rules()
        if rule.get("dependencyDashboardApproval")
    ]

    assert approvals == [
        (["python"], ["minor", "major"]),
        (
            ["node", "ghcr.io/cloudnative-pg/postgresql", "mattermost/mattermost-team-edition"],
            ["major"],
        ),
    ]


def test_each_ecosystem_groups_its_non_major_updates() -> None:
    groups = [
        (rule["groupName"], rule["matchUpdateTypes"])
        for rule in _preset()["packageRules"]
        if "groupName" in rule
    ]

    assert [name for name, _ in groups] == _ECOSYSTEM_GROUPS
    assert all("major" not in update_types for _, update_types in groups)


def test_coupled_pins_come_in_one_pull_request_of_every_update_type() -> None:
    """A coupled group has no update type: its majors and minors also move every file at once.
    It comes after the ecosystem groups, so it wins for its packages."""
    rules = _rules()
    first_coupled = min(
        index for index, rule in enumerate(rules) if rule.get("groupName") in _COUPLED_GROUPS
    )
    last_ecosystem = max(
        index for index, rule in enumerate(rules) if rule.get("groupName") in _ECOSYSTEM_GROUPS
    )
    coupled = {
        rule["groupName"]: (rule["matchPackageNames"], "matchUpdateTypes" in rule)
        for rule in rules
        if rule.get("groupName") in _COUPLED_GROUPS
    }

    assert first_coupled > last_ecosystem
    assert coupled == {name: (packages, False) for name, packages in _COUPLED_GROUPS.items()}


def test_a_new_python_minor_gets_a_branch_of_its_own() -> None:
    """Its approval holds a whole branch, so the weekly digest and patch updates of the Python
    images go on in the other branch of the group."""
    (rule,) = [rule for rule in _rules() if rule.get("groupName") == "python runtime"]

    assert rule["separateMultipleMinor"] is True


@pytest.mark.parametrize(
    "manager",
    [
        "pep621",
        "pip-compile",
        "npm",
        "helm-values",
        "pre-commit",
        "dockerfile",
        "github-actions",
        "devcontainer",
        "terraform",
        "pyenv",
        "nodenv",
        "argocd",
        "kubernetes",
    ],
)
def test_the_manager_of_each_pin_class_is_on(manager: str) -> None:
    """No rule turns a manager off. The pre-commit manager is off by default, so the preset turns
    it on."""
    assert _manager_is_on(manager)


@cache
def _pin_files() -> dict[str, str]:
    """Each tracked file that pins a version, by the built-in manager that reads it."""
    files = {
        "pyproject.toml": "pep621",
        ".python-version": "pyenv",
        ".node-version": "nodenv",
        "Dockerfile": "dockerfile",
        ".devcontainer/Dockerfile": "dockerfile",
        ".pre-commit-config.yaml": "pre-commit",
        ".devcontainer/image/devcontainer.json": "devcontainer",
    }
    files |= dict.fromkeys(
        _tracked(".github/workflows/*.yml", ".github/actions/*/action.yml"), "github-actions"
    )
    files |= dict.fromkeys(_tracked("src/devops_cli/tools_lock/*.txt"), "pip-compile")
    files |= dict.fromkeys(_tracked("src/devops_cli/tools_lock/*/package.json"), "npm")
    files |= dict.fromkeys(_tracked("tf/*.tf", "tf/**/*.tf"), "terraform")
    files |= dict.fromkeys(_applications_that_pin_a_chart(), "argocd")
    files |= dict.fromkeys(
        [
            name
            for name in _tracked_k8s_yaml()
            if re.search(r"values[^/]*\.ya?ml$", name) and _pins_a_repository_tag(_yaml(name))
        ],
        "helm-values",
    )
    return files


def _pins_a_repository_tag(value: Any) -> bool:
    """Whether a values tree holds an object with a `repository` and a non-empty `tag`, the form
    that the helm-values manager reads."""
    if isinstance(value, dict):
        if value.get("repository") and value.get("tag"):
            return True
        return any(_pins_a_repository_tag(child) for child in value.values())
    if isinstance(value, list):
        return any(_pins_a_repository_tag(child) for child in value)
    return False


def test_each_pinned_file_matches_a_pattern_of_its_manager() -> None:
    unmatched = sorted(
        (name, manager)
        for name, manager in _pin_files().items()
        if not any(_matches_file(p, name) for p in _manager_patterns(manager))
    )

    assert (len(_pin_files()) > 40, unmatched) == (True, [])


def test_the_pip_compile_manager_reads_the_header_of_each_tools_lock_requirements_file() -> None:
    """Renovate 44 reads the uv command of the header to compile the file again. It refuses an
    option that takes its argument after a space, and the short option `-o`
    (lib/modules/manager/pip-compile/common.ts), so each option is written with `=`."""
    headers = {
        name: shlex.split(_text(name).splitlines()[1].removeprefix("#"))
        for name in _tracked("src/devops_cli/tools_lock/*.txt")
    }

    assert headers == {
        name: [
            "uv",
            "pip",
            "compile",
            "--universal",
            "--generate-hashes",
            f"--python-version={DEFAULT_PYTHON_VERSION}",
            f"{Path(name).stem}.in",
            f"--output-file={Path(name).name}",
        ]
        for name in headers
    }


def test_lock_file_maintenance_refreshes_the_python_lock_on_monday() -> None:
    """`uv.lock` holds about 240 resolved packages. The pep621 manager updates a direct pin, and
    the weekly maintenance runs `uv lock --upgrade` for the rest."""
    assert _preset()["lockFileMaintenance"] == {
        "enabled": True,
        "schedule": ["* * * * 1"],
        "commitMessageAction": "lock file maintenance",
    }


@cache
def _expected_custom_deps() -> dict[str, list[tuple[str, str]]]:
    """Each pin that only a custom manager reads, by file, from the files that hold it."""
    lock = load_tools_lock()
    python_minor = ("python", DEFAULT_PYTHON_VERSION)
    expected: dict[str, list[tuple[str, str]]] = {
        "src/devops_cli/roadmap/runner_tools.py": [
            ("ghcr.io/astral-sh/uv", UV_VERSION),
            ("node", NODE_MAJOR),
        ],
        ".github/actions/setup-toolchain/action.yml": [python_minor],
        ".github/workflows/release-merge.yml": [python_minor],
        ".github/workflows/release.yml": [python_minor] * 3,
        ".devcontainer/Dockerfile": [python_minor] * 3,
        "pyproject.toml": [python_minor] * 2,
        "src/devops_cli/config/defaults.py": [python_minor],
        "src/devops_cli/tools_lock/semgrep.txt": [python_minor],
        "src/devops_cli/tools_lock/bandit.txt": [python_minor],
        "src/devops_cli/tools_lock/tools.lock": [
            python_minor,
            python_minor,
            *((name, tool.version) for name, tool in lock.python.items()),
            ("@fission-ai/openspec", lock.npm["openspec"].version),
            ("@devcontainers/cli", lock.npm["devcontainers-cli"].version),
        ],
        "k8s/gitea/values.yaml": [
            ("docker.gitea.com/gitea", _yaml("k8s/gitea/values.yaml")["image"]["tag"])
        ],
        "k8s/monitoring/dcgm-exporter-values.yaml": [
            (
                "nvcr.io/nvidia/k8s/dcgm-exporter",
                _yaml("k8s/monitoring/dcgm-exporter-values.yaml")["image"]["tag"],
            )
        ],
        "k8s/argo-workflows/values.yaml": [
            (
                "quay.io/argoproj/workflow-controller",
                _yaml("k8s/argo-workflows/values.yaml")["images"]["tag"],
            )
        ],
        "k8s/monitoring/grafana-values.yaml": [
            (name, version)
            for name, version in (
                entry.split("@", 1) for entry in _yaml(_GRAFANA_VALUES)["plugins"]
            )
        ],
    }
    for name in _tracked_k8s_yaml():
        for document in yaml.safe_load_all(_text(name)):
            if not isinstance(document, dict):
                continue
            spec = document.get("spec") or {}
            if document.get("kind") == "Cluster" and "imageName" in spec:
                image, tag = spec["imageName"].split(":", 1)
                expected.setdefault(name, []).append((image, tag))
            if document.get("kind") == "Mattermost":
                expected.setdefault(name, []).append((spec["image"], spec["version"]))
    return expected


@cache
def _yaml(name: str) -> Any:
    return yaml.safe_load(_text(name))


def test_the_custom_managers_read_each_pin_that_no_built_in_manager_reads() -> None:
    """The Python minor, the runner tools table, the tools lock, the PostgreSQL image of a
    CloudNativePG Cluster, the Mattermost version, the values tags with no repository and the
    Grafana plugins. Each manager finds these pins and no other text."""
    expected = _expected_custom_deps()
    patterns = [p for m in _renovate()["customManagers"] for p in m["managerFilePatterns"]]
    scanned = [name for name in _tracked() if any(_matches_file(p, name) for p in patterns)]
    found = {name: sorted(deps) for name in scanned if (deps := _custom_deps(name))}

    assert found == {name: sorted(deps) for name, deps in expected.items()}


def test_each_coupled_custom_pin_is_in_the_group_of_its_package() -> None:
    """A custom pin outside the group of its coupled pins gets a pull request of its own, and the
    test that compares the files fails on it."""
    custom = {dep for deps in _expected_custom_deps().values() for dep, _ in deps}
    pins = {
        "uv": "ghcr.io/astral-sh/uv",
        "node": "node",
        "python runtime": "python",
        "argo": "quay.io/argoproj/workflow-controller",
        "bandit": "bandit",
        "openspec": "@fission-ai/openspec",
    }

    assert {
        group: (dep in custom, dep in _COUPLED_GROUPS[group]) for group, dep in pins.items()
    } == (dict.fromkeys(pins, (True, True)))


def test_an_openspec_bump_writes_the_generated_skills_again() -> None:
    """The skills that OpenSpec generates embed its version, so the branch runs the regeneration
    and commits each generated file."""
    (rule,) = [rule for rule in _rules() if rule.get("groupName") == "openspec"]
    tasks = rule["postUpgradeTasks"]

    assert (tasks["commands"], tasks["fileFilters"], tasks["executionMode"]) == (
        [
            "uv run --frozen devops install-tools --tool openspec",
            "uv run --frozen devops openspec regenerate",
        ],
        list(CONST_OPENSPEC_GENERATED_GLOBS),
        "branch",
    )


def _labels(value: Any) -> Iterator[str]:
    """Each label that a config sets, at any depth."""
    if isinstance(value, dict):
        for key, child in value.items():
            if key in {"labels", "addLabels"}:
                yield from child
            else:
                yield from _labels(child)
    elif isinstance(value, list):
        for child in value:
            yield from _labels(child)


def test_each_label_exists() -> None:
    """The `scope/*` labels come from `.github/labels.yml`, the `type/*` labels from the workflow
    labels. A label that does not exist would be created by Renovate with no color."""
    declared = {entry["name"] for entry in _yaml(".github/labels.yml")}
    declared |= {label.name for label in WORKFLOW_LABELS}
    used = {*_labels(_preset()), *_labels(_renovate())}

    assert (sorted(used - declared), {"type/chore", "scope/deps"} <= used) == ([], True)


def test_manager_updates_carry_the_ci_or_the_infra_label() -> None:
    added = {
        tuple(rule["matchManagers"]): rule["addLabels"]
        for rule in _preset()["packageRules"]
        if "addLabels" in rule
    }

    assert (_preset()["labels"], added) == (
        ["type/chore", "scope/deps"],
        {
            ("github-actions", "pre-commit", "devcontainer"): ["scope/ci"],
            (
                "dockerfile",
                "docker-compose",
                "kubernetes",
                "argocd",
                "helm-values",
                "terraform",
            ): ["scope/infra"],
        },
    )


def test_actions_and_dockerfiles_pin_digests() -> None:
    """GitHub Actions and Dockerfile images pin a digest beside the version."""
    pinned = [rule["matchManagers"] for rule in _preset()["packageRules"] if rule.get("pinDigests")]

    assert pinned == [["github-actions", "dockerfile"]]


def _python_versions() -> Iterator[tuple[str, str, str]]:
    for package in tomllib.loads(_text("uv.lock"))["package"]:
        if "version" in package:
            yield "pep621", package["name"], package["version"]
    for name in _tracked("src/devops_cli/tools_lock/*.txt"):
        for match in re.finditer(r"^([A-Za-z0-9._-]+)==(\S+)", _text(name), re.M):
            yield "pip-compile", match[1], match[2]


def _node_versions() -> Iterator[tuple[str, str, str]]:
    for name in _tracked("src/devops_cli/tools_lock/*/package-lock.json"):
        for key, package in json.loads(_text(name))["packages"].items():
            if key:
                yield "npm", key.rsplit("node_modules/", 1)[1], package["version"]


def _action_versions() -> Iterator[tuple[str, str, str]]:
    for name in _tracked(".github/workflows/*.yml", ".github/actions/*/action.yml"):
        for match in re.finditer(r"uses:\s*([^\s@]+)@[0-9a-f]{40}\s*#\s*(\S+)", _text(name)):
            yield "github-actions", match[1], match[2]


def _image_versions() -> Iterator[tuple[str, str, str]]:
    """Each image with a tag, and its digest update where the reference pins a digest."""
    for name in [*_tracked_k8s_yaml(), "Dockerfile", ".devcontainer/Dockerfile"]:
        for match in re.finditer(
            r"(?:image:|FROM)\s+([^\s:@]+):([\w][\w.-]*)(@sha256:)?", _text(name)
        ):
            yield "docker", match[1], match[2]
            if match[3]:
                yield "docker-digest", match[1], "0123456"


def _infrastructure_versions() -> Iterator[tuple[str, str, str]]:
    """Each devcontainer feature, Argo CD chart and OpenTofu provider."""
    for reference in _load(".devcontainer", "image", "devcontainer.json")["features"]:
        name, _, tag = reference.rpartition(":")
        yield "devcontainer", name, tag
    for name in _applications_that_pin_a_chart():
        for document in yaml.safe_load_all(_text(name)):
            spec = document.get("spec", {}) if isinstance(document, dict) else {}
            for source in [
                *([spec["source"]] if "source" in spec else []),
                *spec.get("sources", []),
            ]:
                if "chart" in source:
                    yield "argocd", source["chart"], source["targetRevision"]
    provider = r'source\s*=\s*"([^"]+)"\s*\n\s*version\s*=\s*"[~>=< ]*([^"]+)"'
    for name in _tracked("tf/**/*.tf"):
        for match in re.finditer(provider, _text(name)):
            yield "terraform", match[1], match[2]


def _dependency_versions() -> Iterator[tuple[str, str, str]]:
    """(manager, depName, version) of each dependency that the repository pins."""
    yield from _python_versions()
    yield from _node_versions()
    yield from _action_versions()
    yield from _image_versions()
    yield from _infrastructure_versions()
    for deps in _expected_custom_deps().values():
        for dep, version in deps:
            yield "custom", dep, version


def _summary(manager: str, dep: str, version: str) -> str:
    """The title summary after `chore(deps): ` that the preset's message parts give an update of
    one dependency: `update <topic> to v<version>`, or `update <topic> digest to <digest>`."""
    if manager == "docker-digest":
        return f"update {dep} digest to {version}"
    topic = f"feature {re.sub('^.+/', '', dep)}" if manager == "devcontainer" else dep
    return f"update {topic} to v{version.removeprefix('v')}"


def test_each_title_summary_fits_the_semantic_title_check() -> None:
    """The `Semantic PR title` check allows 60 characters after `<type>(<scope>): `. The topic is
    the dependency name, an action has no word `action`, a feature is named by the last part of
    its reference, and an alert has no `[SECURITY]` suffix: its prefix is `fix(deps):`. A pin of a
    coupled group always gets the title of its group."""
    preset = _preset()
    (action_rule,) = [
        rule
        for rule in preset["packageRules"]
        if rule.get("commitMessageTopic") and rule.get("matchManagers") == ["github-actions"]
    ]
    (feature_rule,) = [
        rule
        for rule in preset["packageRules"]
        if rule.get("commitMessageTopic") and rule.get("matchManagers") == ["devcontainer"]
    ]
    coupled = {package for packages in _COUPLED_GROUPS.values() for package in packages}
    summaries = [
        _summary(manager, dep, version)
        for manager, dep, version in _dependency_versions()
        if dep not in coupled
    ]
    groups = [f"update {rule['groupName']} (patch)" for rule in _rules() if "groupName" in rule]
    too_long = sorted({s for s in [*summaries, *groups] if len(s) > _SUMMARY_LIMIT})

    assert (
        preset["commitMessagePrefix"],
        preset["commitMessageAction"],
        preset["commitMessageTopic"],
        action_rule["commitMessageTopic"],
        feature_rule["commitMessageTopic"],
        len(summaries) > 500,
        too_long,
    ) == (
        "chore(deps):",
        "update",
        "{{{depName}}}",
        "{{{depName}}}",
        "feature {{{replace '^.+/' '' depName}}}",
        True,
        [],
    )


def test_kubernetes_manager_has_a_file_pattern() -> None:
    """The `kubernetes` manager matches no file by default, so the config must name `k8s/`."""
    patterns = _renovate().get("kubernetes", {}).get("managerFilePatterns", [])

    assert patterns == ["/^k8s/.+\\.ya?ml$/"]


def test_every_manifest_that_pins_an_image_tag_matches_a_pattern() -> None:
    patterns = _manager_patterns("kubernetes")
    pinned = [name for name in _tracked_k8s_yaml() if _IMAGE_WITH_TAG.search(_text(name))]
    unmatched = [name for name in pinned if not any(_matches_file(p, name) for p in patterns)]

    assert (bool(pinned), unmatched) == (True, [])


def test_a_searxng_bump_tells_the_person_to_refresh_the_engine_names_and_names_no_tag_age() -> None:
    """The tests hold the engine names of the pinned image, so the text of the pull request carries
    the refresh (#3924). The project sets no minimum release age, so the text names none (#4810).
    Each tag ends in a commit hash, which the versioning ignores, so a newer date is an update."""
    (rule,) = [
        r
        for r in _rules()
        if "prBodyNotes" in r and "searxng/searxng" in r.get("matchPackageNames", [])
    ]
    (note,) = rule["prBodyNotes"]
    versioning = _python_pattern(rule["versioning"].removeprefix("regex:"))

    assert (
        "docker.io/searxng/searxng" in rule["matchPackageNames"],
        "days old" in note,
        "tests/fixtures/searxng/default_engine_names.txt" in note,
        bool(versioning.match("2026.10.23-629368e40")),
    ) == (True, False, True, True)


@cache
def _applications_that_pin_a_chart() -> list[str]:
    """Each tracked file under `k8s/` that holds an Argo CD Application with a Helm chart source."""
    found = []
    for name in _tracked_k8s_yaml():
        documents = yaml.safe_load_all(_text(name))
        for document in documents:
            if not isinstance(document, dict) or document.get("kind") != "Application":
                continue
            spec = document.get("spec", {})
            sources = [*([spec["source"]] if "source" in spec else []), *spec.get("sources", [])]
            if any("chart" in source for source in sources):
                found.append(name)
                break
    return found


def test_the_argocd_manager_reads_every_application_that_pins_a_chart() -> None:
    """The `argocd` manager matches no file by default, so a chart pin in an Application gets no
    update pull request unless the config names its file (#1659)."""
    patterns = _manager_patterns("argocd")
    pinned = _applications_that_pin_a_chart()
    unmatched = [name for name in pinned if not any(_matches_file(p, name) for p in patterns)]

    assert (bool(pinned), unmatched) == (True, [])


def test_argocd_leaves_the_git_sources_alone() -> None:
    """Renovate reads a source with no chart as a git dependency at `main`, which Argo CD tracks
    on purpose (ADR 0013), so those dependencies are off."""
    rules = [
        _without_description(rule) for rule in _rules() if rule.get("matchManagers") == ["argocd"]
    ]

    assert rules == [
        {"matchManagers": ["argocd"], "matchDatasources": ["git-tags"], "enabled": False}
    ]


_GRAFANA_VALUES = "k8s/monitoring/grafana-values.yaml"
_GRAFANA_PLUGIN_VERSIONS_URL = "https://grafana.com/api/plugins/{{packageName}}/versions"


def _grafana_plugin_manager() -> dict[str, Any]:
    (manager,) = [
        manager
        for manager in _renovate()["customManagers"]
        if manager.get("datasourceTemplate") == "custom.grafana_plugins"
    ]
    return manager


def test_the_grafana_plugin_datasource_reads_the_versions_that_grafana_com_publishes() -> None:
    """The manager's datasource reads `grafana.com/api/plugins/<id>/versions` and maps its `items`
    to Renovate releases with a JSONata transform."""
    manager = _grafana_plugin_manager()
    kind, _, name = manager["datasourceTemplate"].partition(".")
    datasource = _renovate()["customDatasources"][name]

    assert (
        kind,
        manager["versioningTemplate"],
        datasource["defaultRegistryUrlTemplate"],
        datasource["format"],
        len(datasource["transformTemplates"]),
        "items." in datasource["transformTemplates"][0],
    ) == ("custom", "semver", _GRAFANA_PLUGIN_VERSIONS_URL, "json", 1, True)


def test_grafana_plugin_updates_stay_on_the_pinned_major_one_plugin_a_pull_request() -> None:
    """Each release names the Grafana it needs as `grafanaDependency`, which Renovate cannot read.
    A plugin's minor release can need a newer Grafana minor than the next plugin's, so each plugin
    gets its own pull request, held to the pinned major, with a note that links the release's
    record. A custom manager of a file under `k8s/` carries the infra label."""
    manager = _grafana_plugin_manager()
    (rule,) = [
        rule for rule in _rules() if rule.get("matchDatasources") == [manager["datasourceTemplate"]]
    ]
    majors = {
        int(version.split(".", 1)[0]) for _, version in _expected_custom_deps()[_GRAFANA_VALUES]
    }
    (infra,) = [
        rule
        for rule in _rules()
        if rule.get("matchManagers") == ["custom.regex"] and "addLabels" in rule
    ]

    assert (
        len(majors),
        rule["allowedVersions"],
        "groupName" in rule,
        any("grafanaDependency" in note for note in rule["prBodyNotes"]),
        any("{{{depName}}}/versions/{{{newVersion}}}" in note for note in rule["prBodyNotes"]),
        infra["matchFileNames"],
        infra["addLabels"],
    ) == (1, f"<{max(majors) + 1}.0.0", False, True, True, ["k8s/**"], ["scope/infra"])


def test_opentofu_providers_come_from_the_opentofu_registry() -> None:
    (rule,) = [
        rule
        for rule in _rules()
        if rule.get("matchDatasources") == ["terraform-provider"] and "registryUrls" in rule
    ]

    assert rule["registryUrls"] == ["https://registry.opentofu.org"]


def test_the_preset_writes_no_git_author() -> None:
    """GitHub writes and signs each commit as the App bot with its noreply address, so no
    config holds an email address."""
    text = json.dumps([_preset(), _renovate()])

    assert (
        _preset()["platformCommit"],
        "gitAuthor" in text,
        re.findall(r"[\w.+-]+@[\w-]+\.[\w.-]+", text),
    ) == ("enabled", False, [])


def test_the_pull_request_body_has_no_controls_and_no_footer() -> None:
    """The pull request body becomes the squash commit message."""
    template = _preset()["prBodyTemplate"]

    assert (
        "{{{controls}}}" in template,
        "{{{footer}}}" in template,
        template.startswith("{{{header}}}"),
    ) == (
        False,
        False,
        True,
    )
