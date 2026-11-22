"""The routes that `devops repos onboard` writes through, and the writer that holds them.

`ROUTES` lists each write of the command with its row, method, path form and owner. A row writes
only through `RouteWriter`, which refuses a route that the table does not hold or a path that does
not match the form of its route. With `--plan` the writer records each write and sends nothing; with
`--confirm` it sends it. So a plan and a confirmed run take the same path through the rows, and the
route-ownership test reads the one table to show that no route writes a setting of another owner.
`READS` lists the reads of each row for the dry run, which sends no request.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Final

from devops_cli.exceptions import DevOpsCLIError

if TYPE_CHECKING:
    from devops_cli.github.session import GitHubSession

# The branch of the template pull request. The route that moves a branch names it, so no route
# can move the default branch.
TEMPLATE_BRANCH: Final[str] = "ci/repository-template"


class RouteOwner(StrEnum):
    """Who owns what a route writes (ADR 0035)."""

    # The repository settings of the baseline (D1).
    COMMAND = "command"
    # The files of the template, which reach the default branch only through the pull request.
    TEMPLATE_PULL = "template pull request"
    # The ready mark and the merge of the template pull request, with the login of the person (D3).
    PERSON_LOGIN = "person login"
    # The config file, the keyring and the cluster of the person (D4).
    PERSON_CONFIG = "person config"
    # The ingestion pass of the RAG index, the one writer of its points (#1389).
    RAG_PASS = "rag pass"


@dataclass(frozen=True)
class Route:
    """One write of the command: its key, its row, its method, the form of its path and its
    owner. A path form names each part that varies in braces, such as `{repo}`."""

    key: str
    row: int
    method: str
    path: str
    owner: RouteOwner
    what: str

    def matches(self, method: str, path: str) -> bool:
        """Whether `method` and `path` are a write of this route."""
        return method == self.method and _path_pattern(self.path).fullmatch(path) is not None


def _path_pattern(form: str) -> re.Pattern[str]:
    """The pattern of a path form: `{repo}` is `owner/name`, each other part one segment."""
    pattern = ""
    for literal, part in re.findall(r"([^{]*)(?:\{(\w+)\})?", form):
        pattern += re.escape(literal)
        if part == "repo":
            pattern += r"[^/?]+/[^/?]+"
        elif part:
            pattern += r"[^/?]+"
    return re.compile(pattern)


_ENVIRONMENT: Final[str] = "/repos/{repo}/environments/{environment}"

ROUTES: Final[tuple[Route, ...]] = (
    Route(
        "create-repository", 1, "POST", "/user/repos", RouteOwner.COMMAND, "create the repository"
    ),
    Route("repository", 2, "PATCH", "/repos/{repo}", RouteOwner.COMMAND, "repository settings"),
    Route(
        "vulnerability-alerts-on",
        3,
        "PUT",
        "/repos/{repo}/vulnerability-alerts",
        RouteOwner.COMMAND,
        "turn on vulnerability alerts",
    ),
    Route(
        "vulnerability-alerts-off",
        3,
        "DELETE",
        "/repos/{repo}/vulnerability-alerts",
        RouteOwner.COMMAND,
        "turn off vulnerability alerts",
    ),
    Route(
        "private-reporting-on",
        3,
        "PUT",
        "/repos/{repo}/private-vulnerability-reporting",
        RouteOwner.COMMAND,
        "turn on private vulnerability reporting",
    ),
    Route(
        "private-reporting-off",
        3,
        "DELETE",
        "/repos/{repo}/private-vulnerability-reporting",
        RouteOwner.COMMAND,
        "turn off private vulnerability reporting",
    ),
    Route(
        "immutable-releases-on",
        3,
        "PUT",
        "/repos/{repo}/immutable-releases",
        RouteOwner.COMMAND,
        "turn on immutable releases",
    ),
    Route(
        "immutable-releases-off",
        3,
        "DELETE",
        "/repos/{repo}/immutable-releases",
        RouteOwner.COMMAND,
        "turn off immutable releases",
    ),
    Route(
        "code-scanning",
        3,
        "PATCH",
        "/repos/{repo}/code-scanning/default-setup",
        RouteOwner.COMMAND,
        "CodeQL default setup",
    ),
    Route(
        "workflow-permissions",
        3,
        "PUT",
        "/repos/{repo}/actions/permissions/workflow",
        RouteOwner.COMMAND,
        "permissions of the job token",
    ),
    Route(
        "code-quality",
        4,
        "PATCH",
        "/repos/{repo}/code-quality/setup",
        RouteOwner.COMMAND,
        "Code Quality setup",
    ),
    Route("environment", 5, "PUT", _ENVIRONMENT, RouteOwner.COMMAND, "environment"),
    Route(
        "branch-policy",
        5,
        "POST",
        f"{_ENVIRONMENT}/deployment-branch-policies",
        RouteOwner.COMMAND,
        "deployment branch policy",
    ),
    Route(
        "variable-create",
        5,
        "POST",
        f"{_ENVIRONMENT}/variables",
        RouteOwner.COMMAND,
        "environment variable",
    ),
    Route(
        "variable-update",
        5,
        "PATCH",
        f"{_ENVIRONMENT}/variables/{{variable}}",
        RouteOwner.COMMAND,
        "environment variable",
    ),
    Route(
        "release-secret",
        6,
        "PUT",
        f"{_ENVIRONMENT}/secrets/{{secret}}",
        RouteOwner.COMMAND,
        "sealed environment secret, through gh with the body on stdin",
    ),
    Route("label", 8, "POST", "/repos/{repo}/labels", RouteOwner.COMMAND, "missing label"),
    Route(
        "template-tree",
        9,
        "POST",
        "/repos/{repo}/git/trees",
        RouteOwner.TEMPLATE_PULL,
        "tree of the missing template files",
    ),
    Route(
        "template-commit",
        9,
        "POST",
        "/repos/{repo}/git/commits",
        RouteOwner.TEMPLATE_PULL,
        "commit of the template files",
    ),
    Route(
        "template-branch-create",
        9,
        "POST",
        "/repos/{repo}/git/refs",
        RouteOwner.TEMPLATE_PULL,
        f"branch {TEMPLATE_BRANCH}",
    ),
    Route(
        "template-branch-update",
        9,
        "PATCH",
        f"/repos/{{repo}}/git/refs/heads/{TEMPLATE_BRANCH}",
        RouteOwner.TEMPLATE_PULL,
        f"branch {TEMPLATE_BRANCH}",
    ),
    Route(
        "template-pull",
        9,
        "POST",
        "/repos/{repo}/pulls",
        RouteOwner.TEMPLATE_PULL,
        "draft template pull request",
    ),
    Route(
        "ruleset-create",
        10,
        "POST",
        "/repos/{repo}/rulesets",
        RouteOwner.COMMAND,
        "ruleset main",
    ),
    Route(
        "ruleset-update",
        10,
        "PUT",
        "/repos/{repo}/rulesets/{ruleset}",
        RouteOwner.COMMAND,
        "ruleset main",
    ),
    Route(
        "pull-ready",
        11,
        "POST",
        "/graphql",
        RouteOwner.PERSON_LOGIN,
        "markPullRequestReadyForReview of the template pull request",
    ),
    Route(
        "pull-auto-merge",
        11,
        "POST",
        "/graphql",
        RouteOwner.PERSON_LOGIN,
        "enablePullRequestAutoMerge, or mergePullRequest when GitHub has nothing to wait for",
    ),
    Route("hook-create", 12, "POST", "/repos/{repo}/hooks", RouteOwner.COMMAND, "Service webhook"),
    Route(
        "hook-update",
        12,
        "PATCH",
        "/repos/{repo}/hooks/{hook}",
        RouteOwner.COMMAND,
        "Service webhook",
    ),
    Route(
        "webhook-secret",
        12,
        "KEYRING",
        "service.webhook_secrets",
        RouteOwner.PERSON_CONFIG,
        "secret of the webhook in the keyring map",
    ),
    Route(
        "service-repos",
        13,
        "CONFIG",
        "service.repos",
        RouteOwner.PERSON_CONFIG,
        "repository in the config file",
    ),
    Route(
        "push-secrets",
        13,
        "RUN",
        "devops k8s push-secrets",
        RouteOwner.PERSON_CONFIG,
        "Secret devops/devops-cli",
    ),
    Route(
        "deploy-stack",
        13,
        "RUN",
        "devops k8s deploy-stack",
        RouteOwner.PERSON_CONFIG,
        "stack devops",
    ),
    Route(
        "rag-pass",
        15,
        "RUN",
        "ingestion pass",
        RouteOwner.RAG_PASS,
        "points of the repository",
    ),
)

_ROUTES_BY_KEY: Final[dict[str, Route]] = {route.key: route for route in ROUTES}

# The reads of each row, for the dry run: the method and the path form.
READS: Final[tuple[tuple[int, str], ...]] = (
    (0, "GET /user (header X-OAuth-Scopes)"),
    (0, "GET /repos/{repo}/rulesets"),
    (0, "GET /repos/{repo}/actions/secrets"),
    (1, "GET /repos/{repo}"),
    (2, "GET /repos/{repo}/contents/.copier-answers.yml"),
    (2, "GET /repos/{template}/releases/latest"),
    (2, "copier copy --vcs-ref <ref> https://github.com/{template}.git <dir> (a git clone)"),
    (2, "GET /repos/{template}/contents/templates/github-repository.schema.json?ref=<ref>"),
    (3, "GET /repos/{repo}/vulnerability-alerts"),
    (3, "GET /repos/{repo}/private-vulnerability-reporting"),
    (3, "GET /repos/{repo}/immutable-releases"),
    (3, "GET /repos/{repo}/code-scanning/default-setup"),
    (3, "GET /repos/{repo}/actions/permissions/workflow"),
    (4, "GET /repos/{repo}/code-quality/setup"),
    (5, "GET /repos/{repo}/environments/{environment}"),
    (5, "GET /repos/{repo}/environments/{environment}/deployment-branch-policies"),
    (5, "GET /repos/{repo}/environments/{environment}/variables/{variable}"),
    (6, "GET /repos/{repo}/environments/{environment}/secrets/{secret}"),
    (6, "GET /repos/{repo}/environments/{environment}/secrets/public-key"),
    (7, "GET /repos/{repo}/installation (JWT of each configured App)"),
    (8, "GET /repos/{repo}/labels"),
    (9, "GET /repos/{repo}/contents/<each template file>?ref=<branch>"),
    (9, "GET /repos/{repo}/pulls?head=<owner>:" + TEMPLATE_BRANCH),
    (9, "GET /repos/{repo}/git/ref/heads/<branch>"),
    (9, "GET /repos/{repo}/commits/<head>/check-runs"),
    (10, "GET /repos/{repo}/rulesets/{ruleset}"),
    (11, "GET /repos/{repo}/pulls/{pull}"),
    (11, "POST /graphql mergeStateStatus (a read that --confirm sends after the ready mark)"),
    (12, "GET /repos/{repo}/hooks"),
    (13, "git fetch origin main; git rev-parse HEAD origin/main; git status --porcelain"),
    (15, "Qdrant count and scroll of the points of the repository"),
)


class RouteRefusedError(DevOpsCLIError):
    """A row asked for a write that no route of `ROUTES` holds."""

    error_code = "ONBOARD_ROUTE_REFUSED"


class RouteWriteError(DevOpsCLIError):
    """A write of a route failed: the row that sent it fails, and the next run continues."""

    error_code = "ONBOARD_WRITE_FAILED"


def route_for(key: str) -> Route:
    """The route of `key`, or `RouteRefusedError` when the table holds none."""
    try:
        return _ROUTES_BY_KEY[key]
    except KeyError:
        raise RouteRefusedError(f"No route of the onboard command is named {key}.") from None


class RouteWriter:
    """The one way a row writes. With `confirm` it sends each write; else it records it only.

    `recorded` holds each write as `<method> <target>`, sent or planned, in order.
    """

    def __init__(self, session: GitHubSession, *, confirm: bool) -> None:
        self._session = session
        self.confirm = confirm
        self.recorded: list[str] = []

    def _record(self, key: str, method: str, target: str) -> Route:
        route = route_for(key)
        if not route.matches(method, target):
            raise RouteRefusedError(
                f"The route {key} writes {route.method} {route.path}, not {method} {target}."
            )
        self.recorded.append(f"{method} {target}")
        return route

    def rest(self, key: str, path: str, body: Any = None) -> Any:
        """Send the REST write of route `key` to `path` with `body`, or record it in a plan."""
        route = route_for(key)
        self._record(key, route.method, path)
        if not self.confirm:
            return None
        return _sent(key, lambda: self._session.rest(route.method, path, body=body))

    def graphql(self, key: str, query: str, variables: dict[str, Any]) -> dict[str, Any] | None:
        """Send the GraphQL mutation of route `key`, or record it in a plan."""
        self._record(key, "POST", "/graphql")
        if not self.confirm:
            return None
        return _sent(key, lambda: self._session.client.graphql(query, variables))

    def run[T](self, key: str, action: Callable[[], T], *, target: str | None = None) -> T | None:
        """Run the write of route `key` that does not go through the session, such as a config
        or keyring write, a program, or a gh request at `target`, or record it in a plan."""
        route = route_for(key)
        self._record(key, route.method, target or route.path)
        if not self.confirm:
            return None
        return _sent(key, action)


def _sent[T](key: str, send: Callable[[], T]) -> T:
    """What `send` gives, or `RouteWriteError` that names the route and the failure."""
    try:
        return send()
    except DevOpsCLIError as exc:
        raise RouteWriteError(f"The write {key} failed: {exc.message}") from exc


__all__ = [
    "READS",
    "ROUTES",
    "TEMPLATE_BRANCH",
    "Route",
    "RouteOwner",
    "RouteRefusedError",
    "RouteWriteError",
    "RouteWriter",
    "route_for",
]
