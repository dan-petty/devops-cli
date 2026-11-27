"""Rows 0 to 6 and 10: the preflight, the repository, its settings, its release environment and
its ruleset.

Each row reads the live value with GET, compares it with the baseline as a subset
(`model.differences`), and gives each difference to the writer. GitHub leaves a field out of its
reply to a token that may not read it, so rows 2 and 10 compare only the keys that the reply holds
(`model.held_differences`): a key that the reply does not hold is unknown, and with no other
difference the row is `not readable` (#6875). A private repository on the Free plan answers 403
for its rulesets: it gets no release flow and no ruleset (D2), and the preflight adds the person
step.
"""

from __future__ import annotations

import copy
from collections.abc import Sequence
from functools import partial
from http import HTTPStatus
from typing import TYPE_CHECKING, Any, Final
from urllib.parse import quote

from devops_cli.config.constants import CONST_GITHUB_USER_AGENT, CONST_URL_GITHUB_API_BASE
from devops_cli.exceptions import DevOpsCLIError
from devops_cli.exceptions.git import GitHubNotFoundError
from devops_cli.github.onboard.baseline import read_repository_settings
from devops_cli.github.onboard.model import (
    DOC_CREATE_REPOSITORY,
    DOC_ENVIRONMENTS,
    DOC_GET_REPOSITORY,
    DOC_GET_RULESET,
    DOC_RULESETS,
    DOC_SCOPES,
    DOC_SECRETS,
    DOC_VARIABLES,
    PersonStep,
    Row,
    RowContext,
    RowState,
    change_lines,
    differences,
    held_differences,
)

if TYPE_CHECKING:
    from devops_cli.config.settings import Settings
    from devops_cli.github.onboard.baseline import Baseline
    from devops_cli.github.onboard.routes import RouteWriter
    from devops_cli.github.session import GitHubSession

_SCOPES_HEADER: Final[str] = "x-oauth-scopes"
_NEEDED_SCOPES: Final[tuple[str, ...]] = ("repo", "workflow")
# No key of the Service App goes into a repository (#6771).
_SERVICE_APP_PREFIX: Final[str] = "SERVICE_APP_"
# The roadmap jobs read the issues of each repository, so the command turns them on.
_ROADMAP_REPOSITORY: Final[dict[str, Any]] = {"has_issues": True}
_CODE_QUALITY_STATE: Final[dict[str, str]] = {"state": "configured"}
# The setting that gives the value of each variable that the baseline names.
_VARIABLE_SETTINGS: Final[dict[str, str]] = {
    "RELEASE_APP_CLIENT_ID": "github.release_app_client_id"
}
# The secret of the release key, whose value `--release-key-file` or its credential gives.
_RELEASE_KEY_SECRET: Final[str] = "RELEASE_APP_PRIVATE_KEY"
_RELEASE_KEY_CREDENTIAL: Final[str] = "github.release_app_private_key"
# A PEM key is a few KiB; a larger file is no key.
_KEY_FILE_MAX_BYTES: Final[int] = 64 * 1024
_REQUIRED_CHECKS_RULE: Final[str] = "required_status_checks"
_D2_REASON: Final[str] = (
    "a private repository on the GitHub Free plan has no rulesets and no environments (D2)"
)
# The fields that GitHub gives only to a token with a write permission: "To view merge-related
# settings, you must have the contents:read and contents:write permissions" (REST docs, Get a
# repository), and "the bypass_actors property is only returned if the user making the API request
# has write access to the ruleset" (REST docs, Get a repository ruleset).
_MERGE_SETTINGS_STEP: Final[str] = (
    "GitHub gives the merge settings only to a token with Contents write. Read row 2 with such a "
    "token, such as your own login: `devops repos onboard {repo} --plan --only 2`."
)
_BYPASS_ACTORS_STEP: Final[str] = (
    "GitHub gives the bypass actors of a ruleset only to a token with write access to the ruleset "
    "(Administration write for an App). Read row 10 with such a token, such as your own login: "
    "`devops repos onboard {repo} --plan --only 10`."
)
D2_STEP: Final[PersonStep] = PersonStep(
    "This private repository gets no release flow on the Free plan (D2). To give it one, make it "
    "public or move the account to a paid plan, then run the command again.",
    DOC_ENVIRONMENTS,
)


def _status(exc: DevOpsCLIError) -> int | None:
    """The HTTP status of a failed request, when GitHub answered."""
    status = exc.details.get("status")
    return int(status) if isinstance(status, int) else None


def token_scopes(session: GitHubSession) -> frozenset[str] | None:
    """The OAuth scopes of the token of the session, from `X-OAuth-Scopes` of `GET /user`, or None
    when the token reports none, as a fine-grained token does. An installation token of the App
    has no OAuth scopes, and GitHub refuses it `GET /user`, so the App sends no request (#6783)."""
    from devops_cli.http.egress import EgressLevel
    from devops_cli.http.entry import http_client

    if session.identity.renews:
        return None
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {session.token}",
        "User-Agent": CONST_GITHUB_USER_AGENT,
    }
    with http_client(EgressLevel.PUBLIC) as client:
        response = client.get(f"{CONST_URL_GITHUB_API_BASE}/user", headers=headers)
    if response.status_code != HTTPStatus.OK:
        raise DevOpsCLIError(f"GitHub answered GET /user with HTTP {response.status_code}.")
    if _SCOPES_HEADER not in response.headers:
        return None
    return frozenset(
        scope.strip() for scope in response.headers[_SCOPES_HEADER].split(",") if scope.strip()
    )


def probe_rulesets(session: GitHubSession, ctx: RowContext) -> str | None:
    """Read the rulesets of the repository for rows 0 and 10. A 403 on a private repository marks
    the limit of the Free plan (D2). Gives the reason of a failed probe, else None."""
    try:
        ctx.rulesets = list(session.paginate(f"/repos/{ctx.repo}/rulesets"))
    except DevOpsCLIError as exc:
        if _status(exc) == HTTPStatus.FORBIDDEN and ctx.private:
            ctx.plan_limited = True
            return None
        return f"the rulesets cannot be read: {exc.message}"
    return None


def _secret_names(session: GitHubSession, repo: str) -> list[str]:
    """The names of the Actions secrets of the repository."""
    return [
        str(item.get("name", ""))
        for item in session.paginate(f"/repos/{repo}/actions/secrets", iterable_key="secrets")
    ]


def _baseline_names(baseline: Baseline | None) -> list[str]:
    """Each variable and secret name of the environments of the baseline."""
    if baseline is None:
        return []
    names: list[str] = []
    for environment in baseline.settings.get("environments") or []:
        names.extend(environment.get("variables") or [])
        names.extend(environment.get("secrets") or [])
    return names


def preflight_row(
    session: GitHubSession,
    ctx: RowContext,
    baseline: Baseline | None,
    *,
    scopes: frozenset[str] | None,
    probe: str | None,
) -> Row:
    """Row 0: the scopes of the token, the probe of the rulesets, and no `SERVICE_APP_*` name."""
    problems: list[str] = []
    steps: list[PersonStep] = []
    notes: list[str] = []
    if scopes is None:
        notes.append("the token reports no OAuth scopes")
    else:
        missing = [scope for scope in _NEEDED_SCOPES if scope not in scopes]
        if missing:
            problems.append(f"the token lacks the scopes {', '.join(missing)}")
            steps.append(PersonStep(f"Run `gh auth refresh -s {','.join(missing)}`.", DOC_SCOPES))
    if probe:
        problems.append(probe)
    if ctx.plan_limited:
        notes.append(_D2_REASON)
        steps.append(D2_STEP)
    names = _baseline_names(baseline)
    if ctx.repo_payload is not None:
        names.extend(_secret_names(session, ctx.repo))
    service_names = sorted({name for name in names if name.startswith(_SERVICE_APP_PREFIX)})
    if service_names:
        problems.append(
            f"no key of the Service App goes into a repository (#6771): {', '.join(service_names)}"
        )
    if problems:
        return Row(0, "Preflight", RowState.FAILED, reason="; ".join(problems), steps=tuple(steps))
    return Row(
        0, "Preflight", RowState.PRESENT, reason="; ".join(notes) or None, steps=tuple(steps)
    )


def read_repository(session: GitHubSession, ctx: RowContext) -> None:
    """Read the repository into the context: None when GitHub has no repository of the name."""
    try:
        ctx.repo_payload = session.rest("GET", f"/repos/{ctx.repo}")
    except GitHubNotFoundError:
        ctx.repo_payload = None


def create_row(session: GitHubSession, writer: RouteWriter, ctx: RowContext) -> Row:
    """Row 1: the repository exists, or `--create` makes it with `POST /user/repos`."""
    options = ctx.options
    if ctx.repo_payload is not None:
        return Row(1, "Create", RowState.PRESENT)
    if not options.create or options.visibility is None:
        return Row(
            1,
            "Create",
            RowState.FAILED,
            reason="GitHub has no repository of this name",
            changes=("Run with --create --visibility public|private.",),
        )
    login = session.login
    if login.casefold() != options.repo.owner.casefold():
        return Row(
            1,
            "Create",
            RowState.FAILED,
            reason=f"--create makes a repository of the login {login} only",
            steps=(
                PersonStep("Create the repository of the organization.", DOC_CREATE_REPOSITORY),
            ),
        )
    body = {
        "name": options.repo.name,
        "private": options.visibility == "private",
        "auto_init": True,
    }
    answer = writer.rest("create-repository", "/user/repos", body)
    if isinstance(answer, dict):
        ctx.repo_payload = answer
    state = RowState.APPLIED if writer.confirm else RowState.PENDING
    return Row(1, "Create", state, changes=(f"{options.visibility} repository {ctx.repo}",))


def _available_settings(
    desired: dict[str, Any], live: dict[str, Any]
) -> tuple[dict[str, Any], list[str]]:
    """`desired` without the security features that the live answer does not hold, which the
    plan of the repository does not have, and their names."""
    wanted = dict(desired.get("security_and_analysis") or {})
    if not wanted:
        return desired, []
    held = live.get("security_and_analysis") or {}
    kept = {key: value for key, value in wanted.items() if key in held}
    left_out = sorted(set(wanted) - set(kept))
    result = {key: value for key, value in desired.items() if key != "security_and_analysis"}
    if kept:
        result["security_and_analysis"] = kept
    return result, left_out


def _unknown(keys: Sequence[str], step: PersonStep) -> tuple[str | None, tuple[PersonStep, ...]]:
    """The reason and the person step of a row whose reply does not hold `keys`, or none."""
    if not keys:
        return None, ()
    return (
        f"the reply of GitHub does not hold these keys, so they are unknown: {', '.join(keys)}",
        (step,),
    )


def _write_state(writer: RouteWriter) -> RowState:
    """The state of a row that wrote, or would write, a difference."""
    return RowState.APPLIED if writer.confirm else RowState.PENDING


# GitHub needs the title of a commit with its message: "Required when using
# squash_merge_commit_message" (REST docs, Update a repository).
_TITLE_OF_MESSAGE: Final[tuple[tuple[str, str], ...]] = (
    ("squash_merge_commit_message", "squash_merge_commit_title"),
    ("merge_commit_message", "merge_commit_title"),
)


def repository_row(writer: RouteWriter, ctx: RowContext, baseline: Baseline) -> Row:
    """Row 2: the `repository` body of the baseline and `has_issues`, in one PATCH. A key that the
    reply does not hold, such as a merge setting for a token without Contents write, is unknown:
    with no other difference the row is `not readable` (#6875)."""
    live = ctx.repo_payload or {}
    desired = {**(baseline.settings.get("repository") or {}), **_ROADMAP_REPOSITORY}
    desired, left_out = _available_settings(desired, live)
    diff, unread = held_differences(desired, live)
    unknown, steps = _unknown(
        unread, PersonStep(_MERGE_SETTINGS_STEP.format(repo=ctx.repo), DOC_GET_REPOSITORY)
    )
    notes = [f"not available on this plan: {', '.join(left_out)}"] if left_out else []
    if unknown:
        notes.append(unknown)
    reason = "; ".join(notes) or None
    if diff is None:
        state = RowState.NOT_READABLE if unread else RowState.PRESENT
        return Row(2, "Repository", state, reason=reason, steps=steps)
    for message, title in _TITLE_OF_MESSAGE:
        if message in diff and title in desired:
            diff.setdefault(title, desired[title])
    writer.rest("repository", f"/repos/{ctx.repo}", diff)
    return Row(
        2,
        "Repository",
        _write_state(writer),
        changes=tuple(change_lines(diff)),
        reason=reason,
        steps=steps,
    )


def _enabled(session: GitHubSession, path: str, *, empty_answer: bool) -> bool:
    """Whether a feature is on: a 204 (`empty_answer`) or `enabled: true`, and off on 404."""
    try:
        answer = session.rest("GET", path)
    except GitHubNotFoundError:
        return False
    if empty_answer:
        return True
    return bool(isinstance(answer, dict) and answer.get("enabled"))


# The toggles of row 3: the baseline key, the path under the repository, whether GitHub answers a
# GET with 204 and no body, and the routes that turn the feature on and off.
_TOGGLES: Final[tuple[tuple[str, str, bool, str, str], ...]] = (
    (
        "vulnerability_alerts",
        "vulnerability-alerts",
        True,
        "vulnerability-alerts-on",
        "vulnerability-alerts-off",
    ),
    (
        "private_vulnerability_reporting",
        "private-vulnerability-reporting",
        False,
        "private-reporting-on",
        "private-reporting-off",
    ),
    (
        "immutable_releases",
        "immutable-releases",
        False,
        "immutable-releases-on",
        "immutable-releases-off",
    ),
)


def _settings_endpoint(
    session: GitHubSession,
    writer: RouteWriter,
    path: str,
    key: str,
    desired: dict[str, Any],
    route: str,
) -> tuple[list[str], bool]:
    """Compare one settings endpoint with `desired` and write it on a difference. Gives the
    changes, and whether the plan of the repository has no such endpoint (403 or 404)."""
    try:
        live = session.rest("GET", path)
    except DevOpsCLIError as exc:
        if _status(exc) in {HTTPStatus.FORBIDDEN, HTTPStatus.NOT_FOUND}:
            return [], True
        raise
    diff = differences(desired, live)
    if diff is None:
        return [], False
    writer.rest(route, path, desired)
    return change_lines(diff, f"{key}."), False


def security_row(
    session: GitHubSession, writer: RouteWriter, ctx: RowContext, baseline: Baseline
) -> Row:
    """Row 3: the vulnerability alerts, the private reporting, the immutable releases, the
    CodeQL default setup and the permissions of the job token."""
    settings = baseline.settings
    base = f"/repos/{ctx.repo}"
    changes: list[str] = []
    unavailable: list[str] = []
    for key, suffix, empty_answer, on, off in _TOGGLES:
        if key not in settings:
            continue
        wanted = bool(settings[key])
        if _enabled(session, f"{base}/{suffix}", empty_answer=empty_answer) != wanted:
            writer.rest(on if wanted else off, f"{base}/{suffix}")
            changes.append(f"{key}: {str(wanted).lower()}")
    for key, suffix, route in (
        ("code_scanning_default_setup", "code-scanning/default-setup", "code-scanning"),
        ("actions_workflow_permissions", "actions/permissions/workflow", "workflow-permissions"),
    ):
        if not settings.get(key):
            continue
        found, missing = _settings_endpoint(
            session, writer, f"{base}/{suffix}", key, settings[key], route
        )
        changes.extend(found)
        if missing:
            unavailable.append(key)
    reason = f"not available on this plan: {', '.join(unavailable)}" if unavailable else None
    if not changes:
        return Row(3, "Security", RowState.PRESENT, reason=reason)
    return Row(3, "Security", _write_state(writer), changes=tuple(changes), reason=reason)


def code_quality_row(session: GitHubSession, writer: RouteWriter, ctx: RowContext) -> Row:
    """Row 4: Code Quality, which GitHub gives only on a Team or Enterprise plan."""
    path = f"/repos/{ctx.repo}/code-quality/setup"
    try:
        live = session.rest("GET", path)
    except GitHubNotFoundError:
        return Row(
            4,
            "Code Quality",
            RowState.NOT_AVAILABLE,
            reason="GitHub answers 404: the plan of the account has no Code Quality",
        )
    if differences(_CODE_QUALITY_STATE, live) is None:
        return Row(4, "Code Quality", RowState.PRESENT)
    writer.rest("code-quality", path, dict(_CODE_QUALITY_STATE))
    return Row(4, "Code Quality", _write_state(writer), changes=("state: configured",))


def _environments(baseline: Baseline) -> list[dict[str, Any]]:
    """The environments of the baseline: the release flow."""
    return list(baseline.settings.get("environments") or [])


def _no_release_flow(number: int, name: str, ctx: RowContext, baseline: Baseline) -> Row | None:
    """The row of a repository with no release flow, else None."""
    if ctx.plan_limited:
        return Row(number, name, RowState.SKIPPED, reason=_D2_REASON)
    if not _environments(baseline):
        return Row(number, name, RowState.SKIPPED, reason="the baseline has no release flow")
    return None


def _environment_path(repo: str, name: str) -> str:
    return f"/repos/{repo}/environments/{quote(name, safe='')}"


def _read_or_none(session: GitHubSession, path: str) -> Any:
    """The answer of a GET, or None on 404."""
    try:
        return session.rest("GET", path)
    except GitHubNotFoundError:
        return None


def _branch_policy_changes(
    session: GitHubSession,
    writer: RouteWriter,
    base: str,
    environment: dict[str, Any],
    exists: bool,
) -> list[str]:
    """Write each deployment branch policy of `environment` that GitHub lacks."""
    live = (
        list(session.paginate(f"{base}/deployment-branch-policies", iterable_key="branch_policies"))
        if exists
        else []
    )
    changes: list[str] = []
    for policy in environment.get("branch_policies") or []:
        wanted = {"name": policy["name"], "type": policy.get("type", "branch")}
        if not any(differences(wanted, item) is None for item in live):
            writer.rest("branch-policy", f"{base}/deployment-branch-policies", wanted)
            changes.append(f"branch policy {wanted['name']}")
    return changes


def _variable_changes(
    session: GitHubSession,
    writer: RouteWriter,
    base: str,
    environment: dict[str, Any],
    settings: Settings,
    *,
    exists: bool,
) -> tuple[list[str], list[PersonStep]]:
    """Write each variable of `environment` whose value differs from its setting."""
    from devops_cli.config.settings import dotted_get

    changes: list[str] = []
    steps: list[PersonStep] = []
    for variable in environment.get("variables") or []:
        setting = _VARIABLE_SETTINGS.get(variable)
        value = dotted_get(settings, setting) if setting else None
        if not value:
            command = f"devops config set {setting} <value>" if setting else "a setting"
            steps.append(
                PersonStep(f"Give the variable {variable} its value: {command}.", DOC_VARIABLES)
            )
            continue
        live = _read_or_none(session, f"{base}/variables/{variable}") if exists else None
        body = {"name": variable, "value": str(value)}
        if live is None:
            writer.rest("variable-create", f"{base}/variables", body)
            changes.append(f"variable {variable}: created")
        elif live.get("value") != str(value):
            writer.rest("variable-update", f"{base}/variables/{variable}", body)
            changes.append(f"variable {variable}: new value")
    return changes, steps


def environment_row(
    session: GitHubSession,
    writer: RouteWriter,
    ctx: RowContext,
    baseline: Baseline,
    settings: Settings,
) -> Row:
    """Row 5: each environment of the release flow, its branch policies and its variables."""
    skipped = _no_release_flow(5, "Environment", ctx, baseline)
    if skipped is not None:
        return skipped
    changes: list[str] = []
    steps: list[PersonStep] = []
    for environment in _environments(baseline):
        base = _environment_path(ctx.repo, environment["name"])
        try:
            live = _read_or_none(session, base)
        except DevOpsCLIError as exc:
            if _status(exc) != HTTPStatus.FORBIDDEN:
                raise
            step = PersonStep(
                f"GitHub refuses the environment {environment['name']}: {exc.message}",
                DOC_ENVIRONMENTS,
            )
            return Row(5, "Environment", RowState.PERSON, reason=_D2_REASON, steps=(step,))
        wanted = {"deployment_branch_policy": environment.get("deployment_branch_policy")}
        if live is None or differences(wanted, live) is not None:
            writer.rest("environment", base, wanted)
            changes.append(f"environment {environment['name']}")
        changes.extend(_branch_policy_changes(session, writer, base, environment, live is not None))
        found, needed = _variable_changes(
            session, writer, base, environment, settings, exists=live is not None
        )
        changes.extend(found)
        steps.extend(needed)
    if changes:
        return Row(
            5, "Environment", _write_state(writer), changes=tuple(changes), steps=tuple(steps)
        )
    state = RowState.PERSON if steps else RowState.PRESENT
    return Row(5, "Environment", state, steps=tuple(steps))


def _read_key_file(path: Any) -> str:
    """The text of the key file, refused when it is too large to be a key. The error names the
    path only."""
    size = path.stat().st_size
    if size > _KEY_FILE_MAX_BYTES:
        raise DevOpsCLIError(f"{path} is {size} bytes, too large to be a private key.")
    return str(path.read_text(encoding="utf-8"))


def _secret_value(secret: str, ctx: RowContext, settings: Settings) -> str | None:
    """The value of `secret`: the key file, else the credential of the release key. The baseline
    names no other secret."""
    from devops_cli.config.settings import get_release_app_private_key

    if secret != _RELEASE_KEY_SECRET:
        return None
    if ctx.options.release_key_file is not None:
        return _read_key_file(ctx.options.release_key_file)
    return get_release_app_private_key(settings)


def _secret_present(session: GitHubSession, path: str) -> bool:
    """Whether GitHub holds a secret of the name. GitHub never gives the value."""
    return _read_or_none(session, path) is not None


def release_secret_row(
    session: GitHubSession,
    writer: RouteWriter,
    ctx: RowContext,
    baseline: Baseline,
    settings: Settings,
) -> Row:
    """Row 6: each secret of the release flow, sealed into its environment by the code of
    `devops gh secret sync --env`. Its value comes by reference and goes into no output."""
    from devops_cli.github.secrets import sync_repository_secrets

    skipped = _no_release_flow(6, "Release secret", ctx, baseline)
    if skipped is not None:
        return skipped
    changes: list[str] = []
    steps: list[PersonStep] = []
    for environment in _environments(baseline):
        name = environment["name"]
        base = _environment_path(ctx.repo, name)
        for secret in environment.get("secrets") or []:
            path = f"{base}/secrets/{secret}"
            if _secret_present(session, path) and not ctx.options.rotate_release_key:
                continue
            value = _secret_value(secret, ctx, settings)
            if not value:
                steps.append(
                    PersonStep(
                        f"Store the value of {secret}: devops config set "
                        f"{_RELEASE_KEY_CREDENTIAL} --from-file <file>, or give --release-key-file. "
                        "GitHub never gives a secret value back.",
                        DOC_SECRETS,
                    )
                )
                continue
            result = writer.run(
                "release-secret",
                partial(sync_repository_secrets, ctx.repo, [secret], environment=name, value=value),
                target=path,
            )
            if result is not None and (result.failed_secrets or result.missing_secrets):
                return Row(6, "Release secret", RowState.FAILED, reason=f"GitHub refused {secret}")
            changes.append(f"secret {secret} of environment {name}: sealed")
    if changes:
        return Row(
            6, "Release secret", _write_state(writer), changes=tuple(changes), steps=tuple(steps)
        )
    state = RowState.PERSON if steps else RowState.PRESENT
    return Row(6, "Release secret", state, steps=tuple(steps))


def _checks_rules(ruleset: dict[str, Any] | None) -> list[dict[str, Any]]:
    """The required checks rules of `ruleset`."""
    return [
        rule
        for rule in (ruleset or {}).get("rules") or []
        if rule.get("type") == _REQUIRED_CHECKS_RULE
    ]


def _check_entries(ruleset: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Each required check of `ruleset`."""
    return [
        entry
        for rule in _checks_rules(ruleset)
        for entry in (rule.get("parameters") or {}).get("required_status_checks") or []
    ]


def _with_required_checks(
    desired: dict[str, Any],
    own: dict[str, Any] | None,
    live: dict[str, Any] | None,
    reported: tuple[str, ...],
) -> dict[str, Any]:
    """`desired` with each required check of `own`, of the baseline, of the live ruleset and of
    the checks that reported on the template pull request (D3).

    `own` is the ruleset of the same name in the `github/repository.yaml` that the repository
    holds (#7423). It wins for each parameter of the required checks rule that it sets and for
    the entry of each check that it names. A baseline ruleset with no required checks rule gets
    the rule of `own`. No source removes a check that another source requires.
    """
    result = copy.deepcopy(desired)
    own_rules = _checks_rules(own)
    rules = _checks_rules(result)
    if not rules and own_rules:
        added: dict[str, Any] = {"type": _REQUIRED_CHECKS_RULE, "parameters": {}}
        rules = [added]
        result["rules"] = [*(result.get("rules") or []), added]
    own_parameters = {
        key: copy.deepcopy(value)
        for rule in own_rules
        for key, value in (rule.get("parameters") or {}).items()
        if key != "required_status_checks"
    }
    for rule in rules:
        parameters = rule.setdefault("parameters", {})
        baseline_checks = parameters.get("required_status_checks") or []
        parameters.update(own_parameters)
        by_context: dict[str, dict[str, Any]] = {}
        for entry in [*_check_entries(own), *baseline_checks, *_check_entries(live)]:
            by_context.setdefault(str(entry.get("context")), copy.deepcopy(entry))
        for name in reported:
            by_context.setdefault(name, {"context": name})
        parameters["required_status_checks"] = [by_context[key] for key in sorted(by_context)]
    return result


def ruleset_row(
    session: GitHubSession, writer: RouteWriter, ctx: RowContext, baseline: Baseline
) -> Row:
    """Row 10: each ruleset of the baseline, with the required checks of D3 and of the
    `github/repository.yaml` that the repository holds on its default branch (#7423). A key that
    the reply does not hold, such as `bypass_actors` for a token without write access to the
    ruleset, is unknown: with no other difference the row is `not readable` (#6875)."""
    if ctx.plan_limited:
        step = PersonStep("Rulesets need a public repository or a paid plan.", DOC_RULESETS)
        return Row(10, "Ruleset", RowState.SKIPPED, reason=_D2_REASON, steps=(step,))
    own = read_repository_settings(session, ctx.repo, ctx.default_branch, baseline) or {}
    own_rulesets = {item.get("name"): item for item in own.get("rulesets") or []}
    changes: list[str] = []
    unread: list[str] = []
    for ruleset in baseline.settings.get("rulesets") or []:
        match = next(
            (item for item in ctx.rulesets or [] if item.get("name") == ruleset.get("name")), None
        )
        live = session.rest("GET", f"/repos/{ctx.repo}/rulesets/{match['id']}") if match else None
        own_ruleset = own_rulesets.get(ruleset.get("name"))
        desired = _with_required_checks(ruleset, own_ruleset, live, ctx.reported_checks)
        checks = [
            entry["context"]
            for rule in desired.get("rules") or []
            if rule.get("type") == _REQUIRED_CHECKS_RULE
            for entry in rule["parameters"]["required_status_checks"]
        ]
        if match is None or live is None:
            writer.rest("ruleset-create", f"/repos/{ctx.repo}/rulesets", desired)
        else:
            diff, missing = held_differences(desired, live)
            unread.extend(f"{key} of ruleset {ruleset.get('name')}" for key in missing)
            if diff is None:
                continue
            writer.rest("ruleset-update", f"/repos/{ctx.repo}/rulesets/{match['id']}", desired)
        required = ", ".join(checks) or "none yet"
        changes.append(f"ruleset {ruleset.get('name')}: required checks {required}")
    reason, steps = _unknown(
        unread, PersonStep(_BYPASS_ACTORS_STEP.format(repo=ctx.repo), DOC_GET_RULESET)
    )
    if not changes:
        state = RowState.NOT_READABLE if unread else RowState.PRESENT
        return Row(10, "Ruleset", state, reason=reason, steps=steps)
    return Row(
        10, "Ruleset", _write_state(writer), changes=tuple(changes), reason=reason, steps=steps
    )


__all__ = [
    "D2_STEP",
    "code_quality_row",
    "create_row",
    "environment_row",
    "preflight_row",
    "probe_rulesets",
    "read_repository",
    "release_secret_row",
    "repository_row",
    "ruleset_row",
    "security_row",
    "token_scopes",
]
