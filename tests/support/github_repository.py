"""One GitHub repository held as state, answered through `GitHubApiFake.serve`, and the render of
the repository template that a `copier` child would write, for the tests of `devops repos onboard`
(#6773).

`RepositoryState` answers the reads and the writes of the onboard rows from its fields, so a write
changes what the next read gets, as GitHub does: a second run of the command over the state that a
first run wrote finds no difference. `merge_template_pull` merges the open template pull request.
`render_template` writes the files that `copier copy` renders into the folder of its last argument,
and `serve_template` answers the `copier` child with it.
"""

from __future__ import annotations

import base64
import copy
import itertools
import json
import re
import subprocess
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote

import httpx2
import pytest
import yaml
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from nacl.public import PrivateKey

from devops_cli.ai.instruction_generator import scaffold_agent_instructions
from devops_cli.config.defaults import DEFAULT_RAG_COLLECTION, DEFAULT_RAG_DOCS_COLLECTION
from devops_cli.roadmap.workflow_labels import WORKFLOW_LABELS
from tests.support.fakes.embeddings import FakeEmbedder
from tests.support.fakes.github import GitHubApiFake, github_json
from tests.support.fakes.keyring import FakeKeyring
from tests.support.fakes.process import ProcessAnswer, ProcessCall, ProcessFake
from tests.support.fakes.qdrant import seed_chunk

TEMPLATE = "example-org/templates"
TEMPLATE_TAG = "v0.3.0"
TEMPLATE_BRANCH = "ci/repository-template"
SCHEMA_PATH = "templates/github-repository.schema.json"
CHECK_NAME = "PR title / Semantic PR title"
WEBHOOK_URL = "https://webhooks.example.com/github"
CLIENT_ID = "Iv23example"
# The prefix of an installation token of a GitHub App.
_INSTALLATION_TOKEN = "ghs_"

# A schema of the settings file in the form of the template: it refuses a key that it does not name.
SETTINGS_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "additionalProperties": False,
    "properties": {
        name: {}
        for name in (
            "repository",
            "vulnerability_alerts",
            "private_vulnerability_reporting",
            "immutable_releases",
            "code_scanning_default_setup",
            "actions_workflow_permissions",
            "rulesets",
            "environments",
        )
    },
}

REPOSITORY_SETTINGS: dict[str, Any] = {
    "allow_squash_merge": True,
    "allow_merge_commit": False,
    "allow_rebase_merge": False,
    "squash_merge_commit_title": "PR_TITLE",
    "squash_merge_commit_message": "PR_BODY",
    "allow_auto_merge": True,
    "allow_update_branch": True,
    "delete_branch_on_merge": True,
    "security_and_analysis": {
        "secret_scanning": {"status": "enabled"},
        "secret_scanning_push_protection": {"status": "enabled"},
    },
}

RULESET: dict[str, Any] = {
    "name": "main",
    "target": "branch",
    "enforcement": "active",
    "bypass_actors": [],
    "conditions": {"ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}},
    "rules": [
        {"type": "deletion"},
        {"type": "non_fast_forward"},
        {
            "type": "required_status_checks",
            "parameters": {
                "do_not_enforce_on_create": True,
                "required_status_checks": [],
                "strict_required_status_checks_policy": False,
            },
        },
    ],
}

RELEASE_ENVIRONMENT: dict[str, Any] = {
    "name": "release",
    "deployment_branch_policy": {"protected_branches": False, "custom_branch_policies": True},
    "branch_policies": [{"name": "main", "type": "branch"}],
    "variables": ["RELEASE_APP_CLIENT_ID"],
    "secrets": ["RELEASE_APP_PRIVATE_KEY"],
}


def baseline_settings(*, release_flow: bool, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    """The settings of `github/repository.yaml` as the template renders them."""
    settings: dict[str, Any] = {
        "repository": copy.deepcopy(REPOSITORY_SETTINGS),
        "vulnerability_alerts": True,
        "private_vulnerability_reporting": True,
        "immutable_releases": True,
        "code_scanning_default_setup": {"state": "configured", "query_suite": "default"},
        "actions_workflow_permissions": {
            "default_workflow_permissions": "read",
            "can_approve_pull_request_reviews": False,
        },
        "rulesets": [copy.deepcopy(RULESET)],
    }
    if release_flow:
        settings["environments"] = [copy.deepcopy(RELEASE_ENVIRONMENT)]
    settings.update(extra or {})
    return settings


def labels_text(scopes: str) -> str:
    """The `.github/labels.yml` that the template renders for `scopes`."""
    names = ["ci", "deps", "docs", *(s.strip() for s in scopes.split(",") if s.strip())]
    return yaml.safe_dump(
        [{"name": f"scope/{name}", "color": "DCDCD6", "description": name} for name in names],
        sort_keys=False,
    )


# The `openspec/config.yaml` of the repository template of dan-petty/github-workflows: a comment
# block, the schema that the planner reads, a context line that a person fills in, and the rule of
# each artifact. Row 9 adds it to a repository that lacks it (#3770).
OPENSPEC_CONFIG = """\
# The planning setup of this repository: OpenSpec (https://github.com/Fission-AI/OpenSpec).
# A change of this repository is one folder under openspec/changes/.
# The spec of each capability is under openspec/specs/.
# Replace the context line below with the context of this project.
# Each rule gives its artifact the form that the planner needs.
schema: spec-driven

context: |
  Product: <one line: what this repository makes, for whom, and its main constraints>.

rules:
  proposal:
    - Cite the issue as #<issue> in Why, and name the open tool that covers the need.
  specs:
    - Write each scenario so that a test under tests/ can assert it offline.
  design:
    - Record each rejected alternative with the evidence that rejected it.
  tasks:
    - Order the tasks of a behavior group as failing test, then implementation.
"""


def _answers(argv: tuple[str, ...]) -> dict[str, Any]:
    """The answers of the `--data` options of a `copier copy` argv."""
    given: dict[str, Any] = {}
    for flag, value in itertools.pairwise(argv):
        if flag == "--data":
            key, _, text = value.partition("=")
            given[key] = yaml.safe_load(text) if text in {"true", "false"} else text
    return given


def render_template(argv: tuple[str, ...], *, extra: dict[str, Any] | None = None) -> None:
    """Write what `copier copy` renders into the folder of the last argument of `argv`."""
    dest = Path(argv[-1])
    answers = _answers(argv)
    ref = argv[argv.index("--vcs-ref") + 1]
    release_flow = bool(answers.get("release_flow"))
    scopes = str(answers.get("scopes", ""))
    files = {
        ".copier-answers.yml": yaml.safe_dump(
            {"_commit": ref, "_src_path": argv[-2], **answers}, sort_keys=True
        ),
        ".github/labels.yml": labels_text(scopes),
        ".github/renovate.json": '{"extends": ["github>example-org/templates//renovate/base"]}\n',
        ".pre-commit-config.yaml": "repos: []\n",
        "github/repository.yaml": yaml.safe_dump(
            baseline_settings(release_flow=release_flow, extra=extra), sort_keys=False
        ),
        "openspec/config.yaml": OPENSPEC_CONFIG,
        "openspec/specs/.gitkeep": "",
    }
    for path, text in files.items():
        target = dest / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")


def _is_copier(call: ProcessCall) -> bool:
    return Path(call.argv[0]).name == "copier" and call.argv[1:2] == ("copy",)


def serve_template(
    processes: ProcessFake, *, extra: dict[str, Any] | None = None, fails: bool = False
) -> None:
    """Answer each `copier copy` child with the render of `render_template`."""

    def render(call: ProcessCall) -> subprocess.CompletedProcess[str]:
        if fails:
            return subprocess.CompletedProcess(list(call.argv), 1, "", "template not found")
        render_template(call.argv, extra=extra)
        return subprocess.CompletedProcess(list(call.argv), 0, "", "")

    processes.answer(_is_copier, ProcessAnswer(side_effect=render))


def rendered_files(*, release_flow: bool, scopes: str = "") -> dict[str, str]:
    """The files that the template renders for the answers, as `render_template` writes them."""
    flow = "true" if release_flow else "false"
    with tempfile.TemporaryDirectory() as folder:
        dest = Path(folder) / "out"
        argv = (
            "copier",
            "copy",
            "--vcs-ref",
            TEMPLATE_TAG,
            "--data",
            f"release_flow={flow}",
            "--data",
            f"scopes={scopes}",
            f"https://github.com/{TEMPLATE}.git",
            str(dest),
        )
        render_template(argv)
        return {
            path.relative_to(dest).as_posix(): path.read_text(encoding="utf-8")
            for path in sorted(dest.rglob("*"))
            if path.is_file()
        }


def _folder_entries(files: dict[str, str], path: str) -> list[dict[str, str]]:
    """The direct children of the folder `path` of `files`, as the contents endpoint lists them:
    one item for each file or folder, and no item for a path that holds none."""
    prefix = f"{path.strip('/')}/"
    entries: dict[str, dict[str, str]] = {}
    for name in files:
        if not name.startswith(prefix):
            continue
        child, slash, _rest = name[len(prefix) :].partition("/")
        entries[child] = {
            "type": "dir" if slash else "file",
            "name": child,
            "path": f"{prefix}{child}",
        }
    return list(entries.values())


@dataclass
class Environment:
    """One environment: its branch policy, its policies, its variables and its secret names."""

    deployment_branch_policy: dict[str, Any]
    policies: list[dict[str, Any]] = field(default_factory=list)
    variables: dict[str, str] = field(default_factory=dict)
    secrets: set[str] = field(default_factory=set)


@dataclass
class RepositoryState:
    """The state of one repository and the template repository on GitHub."""

    repo: str
    exists: bool = True
    private: bool = False
    rulesets_forbidden: bool = False
    payload: dict[str, Any] = field(default_factory=dict)
    vulnerability_alerts: bool = False
    private_reporting: bool = False
    immutable_releases: bool = False
    code_scanning: dict[str, Any] = field(default_factory=lambda: {"state": "not-configured"})
    workflow_permissions: dict[str, Any] = field(
        default_factory=lambda: {
            "default_workflow_permissions": "write",
            "can_approve_pull_request_reviews": True,
        }
    )
    code_quality: dict[str, Any] | None = None
    environments: dict[str, Environment] = field(default_factory=dict)
    rulesets: list[dict[str, Any]] = field(default_factory=list)
    labels: list[dict[str, Any]] = field(default_factory=list)
    commits: dict[str, dict[str, str]] = field(default_factory=dict)
    refs: dict[str, str] = field(default_factory=dict)
    pulls: list[dict[str, Any]] = field(default_factory=list)
    check_runs: list[dict[str, Any]] = field(
        default_factory=lambda: [
            {"name": CHECK_NAME, "status": "completed", "conclusion": "success"}
        ]
    )
    merge_state: str = "BLOCKED"
    pull_author: str | None = None
    # A person pushes to the template branch while the run reads the checks of its head.
    push_during_checks: bool = False
    hooks: list[dict[str, Any]] = field(default_factory=list)
    installed: bool = True
    actions_secrets: list[str] = field(default_factory=list)
    scopes: str | None = "repo, workflow"
    schema: dict[str, Any] = field(default_factory=lambda: copy.deepcopy(SETTINGS_SCHEMA))
    graphql: list[str] = field(default_factory=list)
    _ids: itertools.count[int] = field(default_factory=lambda: itertools.count(100))

    def __post_init__(self) -> None:
        owner, _, name = self.repo.partition("/")
        self.payload = {
            "name": name,
            "full_name": self.repo,
            "owner": {"login": owner},
            "private": self.private,
            "visibility": "private" if self.private else "public",
            "default_branch": "main",
            "has_issues": False,
            "allow_squash_merge": True,
            "allow_merge_commit": True,
            "allow_rebase_merge": True,
            "squash_merge_commit_title": "COMMIT_OR_PR_TITLE",
            "squash_merge_commit_message": "COMMIT_MESSAGES",
            "allow_auto_merge": False,
            "allow_update_branch": False,
            "delete_branch_on_merge": False,
            "security_and_analysis": None
            if self.private
            else {
                "secret_scanning": {"status": "disabled"},
                "secret_scanning_push_protection": {"status": "disabled"},
            },
            **self.payload,
        }
        if not self.commits:
            self.commits["c0"] = {"README.md": "# readme\n"}
            self.refs["main"] = "c0"

    # The state of a repository that matches the baseline, as a confirmed run leaves it.
    def onboard(self, *, release_flow: bool, scopes: str = "") -> None:
        """Make the state match the baseline, with the template pull request merged."""
        for key, value in REPOSITORY_SETTINGS.items():
            self.payload[key] = copy.deepcopy(value)
        self.payload["has_issues"] = True
        self.vulnerability_alerts = self.private_reporting = self.immutable_releases = True
        self.code_scanning = {"state": "configured", "query_suite": "default", "languages": []}
        self.workflow_permissions = {
            "default_workflow_permissions": "read",
            "can_approve_pull_request_reviews": False,
        }
        if release_flow:
            self.environments["release"] = Environment(
                deployment_branch_policy=copy.deepcopy(
                    RELEASE_ENVIRONMENT["deployment_branch_policy"]
                ),
                policies=[{"id": 1, "name": "main", "type": "branch"}],
                variables={"RELEASE_APP_CLIENT_ID": CLIENT_ID},
                secrets={"RELEASE_APP_PRIVATE_KEY"},
            )
        ruleset = copy.deepcopy(RULESET)
        ruleset["rules"][2]["parameters"]["required_status_checks"] = [
            {"context": CHECK_NAME, "integration_id": 15368}
        ]
        self.rulesets = [{"id": 7, **ruleset}]
        self.labels = [
            {"name": spec.name, "color": spec.color, "description": spec.description}
            for spec in WORKFLOW_LABELS
        ]
        for item in yaml.safe_load(labels_text(scopes)):
            self.labels.append(dict(item))
        files = rendered_files(release_flow=release_flow, scopes=scopes)
        self.commits["c1"] = {**self.commits[self.refs["main"]], **files, **_agent_files(self.repo)}
        self.refs["main"] = "c1"

    def merge_template_pull(self) -> None:
        """Merge the open template pull request: its files reach the default branch."""
        pull = next(item for item in self.pulls if item["state"] == "open")
        head = self.refs[TEMPLATE_BRANCH]
        self.commits["merged"] = {**self.commits[self.refs["main"]], **self.commits[head]}
        self.refs["main"] = "merged"
        pull.update(state="closed", merged=True)

    def answer(self, request: httpx2.Request) -> httpx2.Response | None:
        """The answer of GitHub for `request`, or None for a request of another route."""
        method, path = request.method, unquote(request.url.path)
        if path == "/user" and _INSTALLATION_TOKEN in request.headers.get("authorization", ""):
            # GitHub refuses `GET /user` to an installation token of an App.
            return github_json({"message": "Resource not accessible by integration"}, status=403)
        query = {key: values[0] for key, values in parse_qs(request.url.query.decode()).items()}
        body = json.loads(request.content) if request.content else None
        for route_method, pattern, handler in self._routes():
            found = re.fullmatch(pattern, path)
            if method == route_method and found:
                return handler(found, query, body)
        return None

    def _routes(self) -> list[tuple[str, str, Callable[..., httpx2.Response | None]]]:
        repo = re.escape(f"/repos/{self.repo}")
        template = re.escape(f"/repos/{TEMPLATE}")
        env = rf"{repo}/environments/(?P<env>[^/]+)"
        return [
            ("GET", r"/user", self._user),
            ("POST", r"/user/repos", self._create),
            ("GET", repo, self._repo),
            ("PATCH", repo, self._patch_repo),
            (
                "GET",
                rf"{template}/releases/latest",
                lambda *_: github_json({"tag_name": TEMPLATE_TAG}),
            ),
            ("GET", rf"{template}/contents/(?P<path>.+)", self._template_file),
            ("GET", rf"{repo}/contents/(?P<path>.+)", self._file),
            ("GET", rf"{repo}/rulesets", self._rulesets),
            ("GET", rf"{repo}/rulesets/(?P<id>\d+)", self._ruleset),
            ("POST", rf"{repo}/rulesets", self._create_ruleset),
            ("PUT", rf"{repo}/rulesets/(?P<id>\d+)", self._update_ruleset),
            (
                "GET",
                rf"{repo}/actions/secrets",
                lambda *_: github_json(
                    {
                        "total_count": len(self.actions_secrets),
                        "secrets": [{"name": n} for n in self.actions_secrets],
                    }
                ),
            ),
            *self._toggle_routes(repo),
            (
                "GET",
                rf"{repo}/code-scanning/default-setup",
                lambda *_: github_json(self.code_scanning),
            ),
            ("PATCH", rf"{repo}/code-scanning/default-setup", self._set("code_scanning")),
            (
                "GET",
                rf"{repo}/actions/permissions/workflow",
                lambda *_: github_json(self.workflow_permissions),
            ),
            (
                "PUT",
                rf"{repo}/actions/permissions/workflow",
                self._set("workflow_permissions", status=204),
            ),
            ("GET", rf"{repo}/code-quality/setup", self._code_quality),
            ("PATCH", rf"{repo}/code-quality/setup", self._set("code_quality")),
            ("GET", env, self._environment),
            ("PUT", env, self._put_environment),
            ("GET", rf"{env}/deployment-branch-policies", self._policies),
            ("POST", rf"{env}/deployment-branch-policies", self._add_policy),
            ("GET", rf"{env}/variables/(?P<name>[^/]+)", self._variable),
            ("POST", rf"{env}/variables", self._create_variable),
            ("PATCH", rf"{env}/variables/(?P<name>[^/]+)", self._update_variable),
            ("GET", rf"{env}/secrets/(?P<name>[^/]+)", self._secret),
            (
                "GET",
                rf"{repo}/installation",
                lambda *_: (
                    github_json({"id": 1})
                    if self.installed
                    else github_json({"message": "Not Found"}, status=404)
                ),
            ),
            ("GET", rf"{repo}/labels", lambda *_: github_json(self.labels)),
            ("POST", rf"{repo}/labels", self._create_label),
            ("GET", rf"{repo}/pulls", self._pulls),
            ("POST", rf"{repo}/pulls", self._create_pull),
            ("POST", rf"{repo}/pulls/(?P<number>\d+)/requested_reviewers", self._request_reviewers),
            ("GET", rf"{repo}/pulls/(?P<number>\d+)", self._pull),
            ("GET", rf"{repo}/git/ref/heads/(?P<branch>.+)", self._ref),
            (
                "GET",
                rf"{repo}/git/commits/(?P<sha>\w+)",
                lambda found, *_: github_json(
                    {"sha": found["sha"], "tree": {"sha": f"tree-{found['sha']}"}}
                ),
            ),
            ("POST", rf"{repo}/git/trees", self._tree),
            ("POST", rf"{repo}/git/commits", self._commit),
            ("POST", rf"{repo}/git/refs", self._create_ref),
            ("PATCH", rf"{repo}/git/refs/heads/(?P<branch>.+)", self._update_ref),
            ("GET", rf"{repo}/commits/(?P<sha>\w+)/check-runs", self._check_runs),
            ("GET", rf"{repo}/hooks", lambda *_: github_json(self.hooks)),
            ("POST", rf"{repo}/hooks", self._create_hook),
            ("PATCH", rf"{repo}/hooks/(?P<id>\d+)", self._update_hook),
            ("POST", r"/graphql", self._graphql),
        ]

    def _toggle_routes(
        self, repo: str
    ) -> list[tuple[str, str, Callable[..., httpx2.Response | None]]]:
        routes: list[tuple[str, str, Callable[..., httpx2.Response | None]]] = []
        for attribute, suffix, empty in (
            ("vulnerability_alerts", "vulnerability-alerts", True),
            ("private_reporting", "private-vulnerability-reporting", False),
            ("immutable_releases", "immutable-releases", False),
        ):

            def read(*_: Any, attribute: str = attribute, empty: bool = empty) -> httpx2.Response:
                on = getattr(self, attribute)
                if empty:
                    return (
                        httpx2.Response(204)
                        if on
                        else github_json({"message": "Not Found"}, status=404)
                    )
                return github_json({"enabled": on})

            def write(on: bool, attribute: str = attribute) -> Callable[..., httpx2.Response]:
                def change(*_: Any) -> httpx2.Response:
                    setattr(self, attribute, on)
                    return httpx2.Response(204)

                return change

            routes += [
                ("GET", rf"{repo}/{suffix}", read),
                ("PUT", rf"{repo}/{suffix}", write(True)),
                ("DELETE", rf"{repo}/{suffix}", write(False)),
            ]
        return routes

    def _set(self, attribute: str, *, status: int = 200) -> Callable[..., httpx2.Response]:
        def change(_found: Any, _query: Any, body: Any) -> httpx2.Response:
            setattr(self, attribute, {**(getattr(self, attribute) or {}), **body})
            return httpx2.Response(204) if status == 204 else github_json(getattr(self, attribute))

        return change

    def _user(self, *_: Any) -> httpx2.Response:
        headers = {} if self.scopes is None else {"x-oauth-scopes": self.scopes}
        return github_json({"login": self.repo.partition("/")[0], "id": 1}, headers=headers)

    def _create(self, _found: Any, _query: Any, body: dict[str, Any]) -> httpx2.Response:
        self.exists = True
        self.private = bool(body["private"])
        self.payload.update(
            private=self.private, visibility="private" if self.private else "public"
        )
        return github_json(self.payload, status=201)

    def _repo(self, *_: Any) -> httpx2.Response:
        if not self.exists:
            return github_json({"message": "Not Found"}, status=404)
        return github_json(self.payload)

    def _patch_repo(self, _found: Any, _query: Any, body: dict[str, Any]) -> httpx2.Response:
        # GitHub needs the title of a commit with its message: "Required when using
        # squash_merge_commit_message" (REST docs, Update a repository).
        for message, title in (
            ("squash_merge_commit_message", "squash_merge_commit_title"),
            ("merge_commit_message", "merge_commit_title"),
        ):
            if message in body and title not in body:
                return github_json({"message": f"{title} is required"}, status=422)
        for key, value in body.items():
            if isinstance(value, dict) and isinstance(self.payload.get(key), dict):
                self.payload[key] = {**self.payload[key], **value}
            else:
                self.payload[key] = value
        return github_json(self.payload)

    def _contents(self, files: dict[str, str] | None, path: str) -> httpx2.Response:
        """A file of `files` as the contents endpoint gives it, or the listing of a folder of
        `files`: GitHub answers a folder path with one item for each direct child."""
        if files is None:
            return github_json({"message": "Not Found"}, status=404)
        if path in files:
            encoded = base64.b64encode(files[path].encode()).decode()
            return github_json(
                {"type": "file", "encoding": "base64", "content": encoded, "path": path}
            )
        entries = _folder_entries(files, path)
        if not entries:
            return github_json({"message": "Not Found"}, status=404)
        return github_json(entries)

    def _template_file(
        self, found: re.Match[str], query: dict[str, str], _body: Any
    ) -> httpx2.Response:
        files = {SCHEMA_PATH: json.dumps(self.schema)} if query.get("ref") == TEMPLATE_TAG else None
        return self._contents(files, found["path"])

    def _file(self, found: re.Match[str], query: dict[str, str], _body: Any) -> httpx2.Response:
        ref = query.get("ref", "main")
        sha = self.refs.get(ref, ref)
        return self._contents(self.commits.get(sha), found["path"])

    def _rulesets(self, *_: Any) -> httpx2.Response:
        if self.rulesets_forbidden:
            return github_json({"message": "Upgrade to GitHub Pro"}, status=403)
        return github_json([{"id": item["id"], "name": item["name"]} for item in self.rulesets])

    def _ruleset(self, found: re.Match[str], *_: Any) -> httpx2.Response:
        return github_json(next(item for item in self.rulesets if item["id"] == int(found["id"])))

    def _create_ruleset(self, _found: Any, _query: Any, body: dict[str, Any]) -> httpx2.Response:
        self.rulesets.append({"id": next(self._ids), **body})
        return github_json(self.rulesets[-1], status=201)

    def _update_ruleset(
        self, found: re.Match[str], _query: Any, body: dict[str, Any]
    ) -> httpx2.Response:
        index = next(i for i, item in enumerate(self.rulesets) if item["id"] == int(found["id"]))
        self.rulesets[index] = {"id": int(found["id"]), **body}
        return github_json(self.rulesets[index])

    def _code_quality(self, *_: Any) -> httpx2.Response:
        if self.code_quality is None:
            return github_json({"message": "Code Quality is not available"}, status=404)
        return github_json(self.code_quality)

    def _environment(self, found: re.Match[str], *_: Any) -> httpx2.Response:
        if self.private and self.rulesets_forbidden:
            return github_json({"message": "Not available on this plan"}, status=403)
        environment = self.environments.get(found["env"])
        if environment is None:
            return github_json({"message": "Not Found"}, status=404)
        return github_json(
            {"name": found["env"], "deployment_branch_policy": environment.deployment_branch_policy}
        )

    def _put_environment(
        self, found: re.Match[str], _query: Any, body: dict[str, Any]
    ) -> httpx2.Response:
        environment = self.environments.setdefault(
            found["env"], Environment(deployment_branch_policy={})
        )
        environment.deployment_branch_policy = body["deployment_branch_policy"]
        return github_json({"name": found["env"]})

    def _policies(self, found: re.Match[str], *_: Any) -> httpx2.Response:
        policies = self.environments[found["env"]].policies
        return github_json({"total_count": len(policies), "branch_policies": policies})

    def _add_policy(
        self, found: re.Match[str], _query: Any, body: dict[str, Any]
    ) -> httpx2.Response:
        self.environments[found["env"]].policies.append({"id": next(self._ids), **body})
        return github_json(body)

    def _variable(self, found: re.Match[str], *_: Any) -> httpx2.Response:
        environment = self.environments.get(found["env"])
        if environment is None or found["name"] not in environment.variables:
            return github_json({"message": "Not Found"}, status=404)
        return github_json({"name": found["name"], "value": environment.variables[found["name"]]})

    def _create_variable(
        self, found: re.Match[str], _query: Any, body: dict[str, Any]
    ) -> httpx2.Response:
        self.environments[found["env"]].variables[body["name"]] = body["value"]
        return github_json({}, status=201)

    def _update_variable(
        self, found: re.Match[str], _query: Any, body: dict[str, Any]
    ) -> httpx2.Response:
        self.environments[found["env"]].variables[found["name"]] = body["value"]
        return httpx2.Response(204)

    def _secret(self, found: re.Match[str], *_: Any) -> httpx2.Response:
        environment = self.environments.get(found["env"])
        if environment is None or found["name"] not in environment.secrets:
            return github_json({"message": "Not Found"}, status=404)
        return github_json({"name": found["name"]})

    def _create_label(self, _found: Any, _query: Any, body: dict[str, Any]) -> httpx2.Response:
        self.labels.append(dict(body))
        return github_json(body, status=201)

    def _pulls(self, _found: Any, query: dict[str, str], _body: Any) -> httpx2.Response:
        head = query.get("head", "").partition(":")[2]
        state = query.get("state", "open")
        return github_json(
            [
                pull
                for pull in self.pulls
                if pull["head"]["ref"] == head and state in {pull["state"], "all"}
            ]
        )

    def _create_pull(self, _found: Any, _query: Any, body: dict[str, Any]) -> httpx2.Response:
        number = len(self.pulls) + 1
        author = self.pull_author or self.repo.partition("/")[0]
        pull = {
            "number": number,
            "node_id": f"PR_{number}",
            "state": "open",
            "draft": body["draft"],
            "merged": False,
            "auto_merge": None,
            "title": body["title"],
            "user": {"login": author},
            "requested_reviewers": [],
            "head": {"ref": body["head"], "sha": self.refs[body["head"]]},
        }
        self.pulls.append(pull)
        return github_json(pull, status=201)

    def _request_reviewers(
        self, found: re.Match[str], _query: Any, body: dict[str, Any]
    ) -> httpx2.Response:
        pull = self.pulls[int(found["number"]) - 1]
        author = str((pull.get("user") or {}).get("login") or "").lower()
        reviewers = [str(name) for name in body.get("reviewers", ())]
        if any(name.lower() == author for name in reviewers):
            return github_json(
                {"message": "Review cannot be requested from pull request author."}, status=422
            )
        existing = {
            str(entry.get("login") or "").lower() for entry in pull.get("requested_reviewers", [])
        }
        for name in reviewers:
            if name.lower() not in existing:
                pull.setdefault("requested_reviewers", []).append({"login": name})
                existing.add(name.lower())
        return github_json({"requested_reviewers": pull.get("requested_reviewers", [])}, status=201)

    def _pull(self, found: re.Match[str], *_: Any) -> httpx2.Response:
        pull = self.pulls[int(found["number"]) - 1]
        return github_json(
            {**pull, "head": {**pull["head"], "sha": self.refs.get(pull["head"]["ref"], "")}}
        )

    def _check_runs(self, *_: Any) -> httpx2.Response:
        answer = github_json({"total_count": len(self.check_runs), "check_runs": self.check_runs})
        if self.push_during_checks and TEMPLATE_BRANCH in self.refs:
            self.push_during_checks = False
            self.commits["pushed"] = dict(self.commits[self.refs[TEMPLATE_BRANCH]])
            self.refs[TEMPLATE_BRANCH] = "pushed"
        return answer

    def _ref(self, found: re.Match[str], *_: Any) -> httpx2.Response:
        sha = self.refs.get(found["branch"])
        if sha is None:
            return github_json({"message": "Not Found"}, status=404)
        return github_json({"ref": f"refs/heads/{found['branch']}", "object": {"sha": sha}})

    def _tree(self, _found: Any, _query: Any, body: dict[str, Any]) -> httpx2.Response:
        base = self.commits[body["base_tree"].removeprefix("tree-")]
        sha = f"t{next(self._ids)}"
        self.commits[sha] = {**base, **{entry["path"]: entry["content"] for entry in body["tree"]}}
        return github_json({"sha": sha}, status=201)

    def _commit(self, _found: Any, _query: Any, body: dict[str, Any]) -> httpx2.Response:
        sha = f"c{next(self._ids)}"
        self.commits[sha] = self.commits[body["tree"]]
        return github_json({"sha": sha}, status=201)

    def _create_ref(self, _found: Any, _query: Any, body: dict[str, Any]) -> httpx2.Response:
        self.refs[body["ref"].removeprefix("refs/heads/")] = body["sha"]
        return github_json({"ref": body["ref"]}, status=201)

    def _update_ref(
        self, found: re.Match[str], _query: Any, body: dict[str, Any]
    ) -> httpx2.Response:
        self.refs[found["branch"]] = body["sha"]
        return github_json({"ref": found["branch"]})

    def _create_hook(self, _found: Any, _query: Any, body: dict[str, Any]) -> httpx2.Response:
        hook = {"id": next(self._ids), **body}
        self.hooks.append(hook)
        return github_json(hook, status=201)

    def _update_hook(
        self, found: re.Match[str], _query: Any, body: dict[str, Any]
    ) -> httpx2.Response:
        hook = next(item for item in self.hooks if item["id"] == int(found["id"]))
        hook.update(body)
        return github_json(hook)

    def _graphql(self, _found: Any, _query: Any, body: dict[str, Any]) -> httpx2.Response:
        query = body["query"]
        name = next(
            word
            for word in (
                "markPullRequestReadyForReview",
                "enablePullRequestAutoMerge",
                "mergePullRequest",
                "mergeStateStatus",
            )
            if word in query
        )
        self.graphql.append(name)
        number = int(body["variables"]["id"].removeprefix("PR_"))
        pull = self.pulls[number - 1]
        expected = body["variables"].get("head")
        if expected is not None and expected != self.refs.get(pull["head"]["ref"]):
            return github_json({"errors": [{"message": "Head branch was modified."}]})
        if name == "markPullRequestReadyForReview":
            pull["draft"] = False
        elif name == "enablePullRequestAutoMerge":
            pull["auto_merge"] = {"merge_method": "squash"}
        elif name == "mergePullRequest":
            self.merge_template_pull()
        return github_json({"data": {"node": {"mergeStateStatus": self.merge_state}}})


def _agent_files(repo: str) -> dict[str, str]:
    """The agent files that `devops ai agents --template` writes into a folder named after the
    repository that holds the rendered template."""
    with tempfile.TemporaryDirectory() as folder:
        dest = Path(folder) / repo.partition("/")[2]
        files = rendered_files(release_flow=False)
        for path, text in files.items():
            (dest / path).parent.mkdir(parents=True, exist_ok=True)
            (dest / path).write_text(text, encoding="utf-8")
        written = scaffold_agent_instructions(dest, force=False, template=True)
        return {
            path.relative_to(dest.resolve()).as_posix(): path.read_text(encoding="utf-8")
            for path in written
        }


REPO = "example-org/app"
RELEASE_KEY = "TEST-RELEASE-KEY-VALUE-6773"
APP_SETTINGS = {"app_id": 1001, "installation_id": 42, "slug": "example-service"}
CANONICAL_REMOTE = "https://github.com/dan-petty/devops-cli.git"
CHECKOUT_HEAD = "0123456789abcdef0123456789abcdef01234567"


@dataclass
class OnboardHarness:
    """The edges of an onboarding run: the fake GitHub and its repository state, the process
    edge (copier, gh, git, devops), the keyring and Qdrant, and the checkout of row 13."""

    api: GitHubApiFake
    processes: ProcessFake
    state: RepositoryState
    keyring: FakeKeyring
    qdrant: Any
    workdir: Path

    def writes(self) -> list[str]:
        """Each request to GitHub that is not a GET, as `<method> <path>`, in order."""
        return [
            f"{request.method} {unquote(request.url.path)}"
            for request in self.api.sent
            if request.method != "GET"
        ]

    def calls(self, word: str) -> list[ProcessCall]:
        """Each child process whose argv holds `word`."""
        return [call for call in self.processes.calls if word in call.argv]

    def seed_index(self, *, visibility: str = "public") -> None:
        """Hold points of REPO in both RAG collections, as the pass writes them."""
        embedder = FakeEmbedder()
        for collection, path in (
            (DEFAULT_RAG_COLLECTION, "src/main.py"),
            (DEFAULT_RAG_DOCS_COLLECTION, "docs/index.md"),
        ):
            seed_chunk(
                self.qdrant,
                embedder,
                f"text of {path}\n",
                collection=collection,
                file_path=path,
                project_name=REPO,
                visibility=visibility,
            )


@pytest.fixture(scope="session")
def onboard_app_key() -> str:
    """The private key of the Service App, made for this run, in PEM form."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()


@pytest.fixture
def onboard_github(
    github_api_and_gh: tuple[GitHubApiFake, ProcessFake],
    config: Callable[..., Path],
    keyring_store: FakeKeyring,
    qdrant: Any,
    onboard_app_key: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> OnboardHarness:
    """A new public repository REPO on the fake GitHub, the template of TEMPLATE at TEMPLATE_TAG,
    the Service App, the release key and the client ID in the configuration, and a clean
    checkout of origin/main of devops-cli for row 13."""
    from devops_cli.config.constants import CONST_GITHUB_APP_PRIVATE_KEY_ENV

    api, processes = github_api_and_gh
    monkeypatch.delenv(CONST_GITHUB_APP_PRIVATE_KEY_ENV, raising=False)
    state = RepositoryState(REPO)
    api.serve(state.answer)
    serve_template(processes)
    public_key = base64.b64encode(bytes(PrivateKey.generate().public_key)).decode()
    processes.answer(
        lambda call: call.argv[:2] == ("gh", "api") and call.argv[-1].endswith("/public-key"),
        ProcessAnswer(stdout=json.dumps({"key_id": "k1", "key": public_key})),
    )

    def quota(_call: ProcessCall) -> ProcessAnswer:
        # A wait of the checks moves the clock past the reset that the fake reported first.
        fresh = {"limit": 5000, "remaining": 5000, "used": 0, "reset": int(time.time()) + 86400}
        return ProcessAnswer(stdout=json.dumps({"resources": {"core": fresh, "graphql": fresh}}))

    processes.answer(lambda call: call.argv[:3] == ("gh", "api", "rate_limit"), quota)

    def seal(call: ProcessCall) -> subprocess.CompletedProcess[str]:
        # gh api -X PUT repos/<repo>/environments/<env>/secrets/<name> --input -
        parts = call.argv[4].split("/")
        state.environments[parts[4]].secrets.add(parts[6])
        return subprocess.CompletedProcess(list(call.argv), 0, "", "")

    processes.answer(
        lambda call: call.argv[:4] == ("gh", "api", "-X", "PUT"), ProcessAnswer(side_effect=seal)
    )
    processes.answer(
        lambda call: call.argv[:3] == ("git", "remote", "get-url"),
        ProcessAnswer(stdout=f"{CANONICAL_REMOTE}\n"),
    )
    processes.answer(
        lambda call: call.argv[:2] == ("git", "rev-parse"),
        ProcessAnswer(stdout=f"{CHECKOUT_HEAD}\n"),
    )
    keyring_store.values["service_github_app_private_key"] = onboard_app_key
    keyring_store.values["github_release_app_private_key"] = RELEASE_KEY
    config(
        service={"repos": [], "webhook_url": WEBHOOK_URL, "github_app": APP_SETTINGS},
        github={"template_repository": TEMPLATE, "release_app_client_id": CLIENT_ID},
    )
    checkout = tmp_path / "devops-cli"
    (checkout / ".git").mkdir(parents=True)
    harness = OnboardHarness(api, processes, state, keyring_store, qdrant, checkout)
    harness.seed_index()
    return harness
