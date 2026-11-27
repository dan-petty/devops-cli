"""The baseline of a repository: the Copier template of the template repository at one ref.

The ref is `--template-ref`, else `_commit` of `.copier-answers.yml` of the repository, else the
latest release tag of the template repository, read at run time, so no tag is written here. The
command runs the `copier` program: the Copier library needs `jinja2-ansible-filters`, which is GPL3,
and the template uses its filter `regex_search`. Copier clones the template over HTTPS and renders
it into a temporary folder, with no `--trust`, because the template has no tasks. The rendered
`github/repository.yaml` is the settings baseline. It must match the schema
`templates/github-repository.schema.json` of the template at the same ref. The rendered files and
the agent files of `devops ai agents --template` are the content of the template pull request.
`read_repository_settings` reads the `github/repository.yaml` that the repository holds on its
default branch and checks it against the same schema (#7423).
"""

from __future__ import annotations

import json
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

import yaml

from devops_cli.config.constants import CONST_MAX_ERROR_DETAIL_LENGTH
from devops_cli.config.yaml_errors import load_yaml, parse_config_yaml
from devops_cli.core.process import run_subprocess
from devops_cli.exceptions import DevOpsCLIError
from devops_cli.github.onboard.model import DOC_COPIER, PersonStep
from devops_cli.lang import ERRORS
from devops_cli.security.sanitizer import mask_secrets

if TYPE_CHECKING:
    from devops_cli.github.onboard.model import OnboardOptions
    from devops_cli.github.session import GitHubSession

ANSWERS_FILE: Final[str] = ".copier-answers.yml"
SETTINGS_FILE: Final[str] = "github/repository.yaml"
LABELS_FILE: Final[str] = ".github/labels.yml"
_SCHEMA_PATH: Final[str] = "templates/github-repository.schema.json"
_COPIER: Final[str] = "copier"
# One install that the Copier documents name; it brings the GPL3 filters with the program.
_COPIER_INSTALL: Final[str] = "uv tool install copier"
# A clone of the template and a render took a few seconds on 2026-11-22; the bound stops a hang.
_COPIER_TIMEOUT_SECONDS: Final[float] = 300.0


class BaselineUnreadableError(DevOpsCLIError):
    """The baseline cannot be read: no ref, no `copier` program, a failed render, or a settings
    file that the schema refuses. `step` is the person step that makes it readable, if any."""

    error_code = "ONBOARD_BASELINE_UNREADABLE"

    def __init__(self, message: str, *, step: PersonStep | None = None) -> None:
        self.step = step
        super().__init__(message)


class AnswerFlagError(DevOpsCLIError):
    """A flag gives an answer that differs from `.copier-answers.yml` of the repository."""

    error_code = "ONBOARD_ANSWER_DIFFERS"
    exit_code = 2


@dataclass(frozen=True)
class Baseline:
    """The rendered template: its ref, the answers of the render, each file by path, the
    settings of `github/repository.yaml`, and the text of the schema of the settings at the ref."""

    ref: str
    answers: dict[str, Any]
    files: dict[str, str]
    settings: dict[str, Any]
    schema_text: str

    @property
    def release_flow(self) -> bool:
        """Whether the baseline holds the release flow: the environments of rows 5 and 6."""
        return bool(self.settings.get("environments"))


def _scope_set(scopes: str | tuple[str, ...]) -> frozenset[str]:
    """The scope names of a comma-separated answer or of the flags."""
    items = scopes.split(",") if isinstance(scopes, str) else scopes
    return frozenset(item.strip() for item in items if item.strip())


def read_answers(session: GitHubSession, repo: str, ref: str) -> dict[str, Any] | None:
    """The answers of `.copier-answers.yml` on `ref` of `repo`, or None when the file is absent."""
    text = session.client.get_file_at(repo, ANSWERS_FILE, ref)
    if text is None:
        return None
    loaded = yaml.safe_load(text)
    if not isinstance(loaded, dict):
        raise BaselineUnreadableError(f"{ANSWERS_FILE} of {repo} holds no mapping of answers.")
    return loaded


def check_answer_flags(answers: dict[str, Any] | None, options: OnboardOptions) -> None:
    """Refuse a flag that gives another value than `.copier-answers.yml`: after the first render,
    the file holds the answers, and `copier update` changes them."""
    if answers is None:
        return
    differing: list[str] = []
    if options.scopes and _scope_set(options.scopes) != _scope_set(str(answers.get("scopes", ""))):
        differing.append("--scope")
    if options.release_flow is not None and options.release_flow != bool(
        answers.get("release_flow")
    ):
        differing.append("--release-flow")
    if options.release_type is not None and options.release_type != answers.get("release_type"):
        differing.append("--release-type")
    if options.template_ref is not None and options.template_ref != answers.get("_commit"):
        differing.append("--template-ref")
    if differing:
        raise AnswerFlagError(
            f"{', '.join(differing)} differs from {ANSWERS_FILE} of {options.repo.display}. The "
            "file holds the answers after the first render: change one with `copier update "
            "--data <question>=<answer>`, and Renovate brings each new tag."
        )


def resolve_ref(
    session: GitHubSession, template: str, options: OnboardOptions, answers: dict[str, Any] | None
) -> str:
    """The template ref: the flag, else `_commit` of the answers, else the latest release tag."""
    if options.template_ref:
        return options.template_ref
    if answers and answers.get("_commit"):
        return str(answers["_commit"])
    try:
        release = session.rest("GET", f"/repos/{template}/releases/latest")
    except DevOpsCLIError as exc:
        raise BaselineUnreadableError(
            f"The template repository {template} has no latest release to render: {exc}"
        ) from exc
    tag = release.get("tag_name") if isinstance(release, dict) else None
    if not tag:
        raise BaselineUnreadableError(f"The latest release of {template} names no tag.")
    return str(tag)


def render_answers(
    answers: dict[str, Any] | None, options: OnboardOptions, *, plan_limited: bool
) -> dict[str, Any]:
    """The answers of the render: those of `.copier-answers.yml`, else the flags. A private
    repository on the Free plan gets no release flow, also with `--release-flow`, because it can
    have no environment (D2). Any other repository gets it unless `--no-release-flow` is given."""
    if answers is not None:
        return {key: value for key, value in answers.items() if not key.startswith("_")}
    release_flow = not plan_limited and options.release_flow is not False
    given: dict[str, Any] = {
        "scopes": ",".join(sorted(_scope_set(options.scopes))),
        "release_flow": release_flow,
    }
    if release_flow and options.release_type:
        given["release_type"] = options.release_type
    return given


def _data_value(value: Any) -> str:
    """An answer as `copier --data` takes it: YAML for a bool, the text for a string."""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _copier_argv(
    program: str, template: str, ref: str, answers: dict[str, Any], dest: Path
) -> list[str]:
    """The argv of the render of `template` at `ref` into `dest`."""
    argv = [program, "copy", "--vcs-ref", ref, "--defaults", "--quiet"]
    for key, value in sorted(answers.items()):
        argv.extend(["--data", f"{key}={_data_value(value)}"])
    return [*argv, f"https://github.com/{template}.git", str(dest)]


def _read_tree(root: Path) -> dict[str, str]:
    """Each file under `root` as its relative POSIX path and text, without `.git`."""
    files: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if path.is_file() and ".git" not in relative.parts:
            files[relative.as_posix()] = path.read_text(encoding="utf-8")
    return files


def _checked_settings(settings: Any, schema_text: str, name: str) -> dict[str, Any]:
    """`settings`, the content of the settings file `name`, checked against the schema of the
    template."""
    # jsonschema ships no type information.
    from jsonschema.validators import validator_for  # type: ignore[import-untyped]

    schema = json.loads(schema_text)
    errors = sorted(validator_for(schema)(schema).iter_errors(settings), key=str)
    if errors:
        detail = errors[0].message[:CONST_MAX_ERROR_DETAIL_LENGTH]
        raise BaselineUnreadableError(f"{name} does not match {_SCHEMA_PATH}: {detail}")
    if not isinstance(settings, dict):
        raise BaselineUnreadableError(f"{name} holds no mapping of settings.")
    return settings


def read_repository_settings(
    session: GitHubSession, repo: str, branch: str, baseline: Baseline
) -> dict[str, Any] | None:
    """The settings of the `github/repository.yaml` that `repo` holds on `branch`, checked against
    the schema of the baseline, or None when the branch holds no such file (#7423).

    A person can change the file after the render, so a file that is not YAML raises
    `ConfigurationError` with no text of the file, and a file that the schema refuses raises
    `BaselineUnreadableError`.
    """
    text = session.client.get_file_at(repo, SETTINGS_FILE, branch)
    if text is None:
        return None
    name = f"{SETTINGS_FILE} of {repo} on {branch}"
    settings = load_yaml(
        lambda: parse_config_yaml(text), name=name, action=ERRORS.config.not_yaml_read
    )
    return _checked_settings(settings, baseline.schema_text, name)


def render_baseline(
    session: GitHubSession,
    template: str,
    repo_name: str,
    ref: str,
    answers: dict[str, Any],
) -> Baseline:
    """Render the template at `ref` with `answers`, add the agent files, and read the settings.

    Raises `BaselineUnreadableError` when `copier` is not on PATH, the render fails, or the
    settings file does not match the schema.
    """
    from devops_cli.ai.instruction_generator import scaffold_agent_instructions

    program = shutil.which(_COPIER)
    if program is None:
        raise BaselineUnreadableError(
            "The program copier is not on PATH.",
            step=PersonStep(f"Install the program copier: `{_COPIER_INSTALL}`.", DOC_COPIER),
        )
    with tempfile.TemporaryDirectory(prefix="onboard-") as folder:
        dest = Path(folder) / repo_name
        result = run_subprocess(
            _copier_argv(program, template, ref, answers, dest),
            timeout=_COPIER_TIMEOUT_SECONDS,
            quiet=True,
        )
        if result.returncode != 0:
            # The last line of a failed run names the error; the lines above it are a traceback.
            lines = mask_secrets((result.stderr or result.stdout or "").strip()).splitlines()
            said = lines[-1] if lines else ""
            raise BaselineUnreadableError(
                f"copier could not render {template} at {ref} (exit {result.returncode}): "
                f"{said[:CONST_MAX_ERROR_DETAIL_LENGTH]}"
            )
        scaffold_agent_instructions(dest, force=False, template=True)
        files = _read_tree(dest)
    if SETTINGS_FILE not in files:
        raise BaselineUnreadableError(f"The template at {ref} renders no {SETTINGS_FILE}.")
    schema_text = session.client.get_file_at(template, _SCHEMA_PATH, ref)
    if schema_text is None:
        raise BaselineUnreadableError(f"The template at {ref} holds no {_SCHEMA_PATH}.")
    settings = _checked_settings(yaml.safe_load(files[SETTINGS_FILE]), schema_text, SETTINGS_FILE)
    return Baseline(
        ref=ref, answers=answers, files=files, settings=settings, schema_text=schema_text
    )


__all__ = [
    "ANSWERS_FILE",
    "LABELS_FILE",
    "SETTINGS_FILE",
    "AnswerFlagError",
    "Baseline",
    "BaselineUnreadableError",
    "check_answer_flags",
    "read_answers",
    "read_repository_settings",
    "render_answers",
    "render_baseline",
    "resolve_ref",
]
