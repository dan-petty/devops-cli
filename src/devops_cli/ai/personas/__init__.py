"""AI persona definitions for code review and chat."""

from __future__ import annotations

from collections.abc import ItemsView, Iterator, KeysView, Mapping, ValuesView
from enum import StrEnum
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from devops_cli.lang import MESSAGES

_PERSONAS_DIR = Path(__file__).parent
_TASKS_DIR = _PERSONAS_DIR.parent / "tasks"


class Persona(StrEnum):
    DEVSECOPS = "devsecops"
    ARCHITECT = "architect"
    PM = "pm"
    AUDITOR = "auditor"
    QA = "qa"
    CHALLENGER = "challenger"


class PersonaDefinition(BaseModel):
    """Immutable Pydantic model for review and chat persona definitions."""

    model_config = ConfigDict(frozen=True)

    name: str
    title: str
    system_prompt: str  # tasks/review.md + prompt.md
    chat_prompt: str  # role.md + tasks/chat.md
    compose_prompt: str  # role.md + tasks/compose.md


def _load(path: Path) -> str:
    return path.read_text(encoding="utf-8").rstrip()


@lru_cache
def _get_task_review() -> str:
    return _load(_TASKS_DIR / "review.md")


@lru_cache
def _get_task_chat() -> str:
    return _load(_TASKS_DIR / "chat.md")


@lru_cache
def _get_task_compose() -> str:
    return _load(_TASKS_DIR / "compose.md")


@lru_cache
def _load_persona(persona: Persona) -> PersonaDefinition:
    d = _PERSONAS_DIR / persona
    names = {
        Persona.DEVSECOPS: MESSAGES.persona_titles.devsecops,
        Persona.ARCHITECT: MESSAGES.persona_titles.architect,
        Persona.PM: MESSAGES.persona_titles.pm,
        Persona.AUDITOR: MESSAGES.persona_titles.auditor,
        Persona.QA: MESSAGES.persona_titles.qa,
        Persona.CHALLENGER: MESSAGES.persona_titles.challenger,
    }
    role = _load(d / "role.md")
    domain = _load(d / "prompt.md")
    return PersonaDefinition(
        name=persona.value,
        title=names[persona],
        system_prompt=role + "\n\n" + _get_task_review() + "\n\n" + domain,
        chat_prompt=role + "\n\n" + _get_task_chat(),
        compose_prompt=role + "\n\n" + _get_task_compose(),
    )


def review_prompt_digest(tasks_dir: Path = _TASKS_DIR, personas_dir: Path = _PERSONAS_DIR) -> str:
    """A digest of every prompt a review can load: each `.md` file under the two directories.

    It covers each file's path relative to its directory and its text, so editing, adding or
    removing a prompt changes it, and nothing else does. Reviews run with one digest form one arm
    of a prompt benchmark. Prompt text built in code is covered by a run's commit instead.
    """
    from devops_cli.ai.run_store import digest

    return digest(
        {
            label: {
                path.relative_to(directory).as_posix(): path.read_text(encoding="utf-8")
                for path in directory.rglob("*.md")
            }
            for label, directory in (("tasks", tasks_dir), ("personas", personas_dir))
        }
    )


def __getattr__(name: str) -> str:
    if name == "METADATA_SYSTEM_PROMPT":
        return _load(_TASKS_DIR / "metadata.md")
    if name == "ANALYZE_PSEUDOCODE_SYSTEM_PROMPT":
        return _load(_TASKS_DIR / "analyze_pseudocode_system.md")
    if name == "ANALYZE_PSEUDOCODE_TASK_PROMPT":
        return _load(_TASKS_DIR / "analyze_pseudocode.md")
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


# ── Lazy-loading Registry ─────────────────────────────────────────────────────────────


class _PersonaRegistry(Mapping[Persona, PersonaDefinition]):
    def __getitem__(self, item: object) -> PersonaDefinition:
        if isinstance(item, Persona):
            return _load_persona(item)
        if isinstance(item, str):
            try:
                return _load_persona(Persona(item))
            except ValueError as exc:
                raise KeyError(item) from exc
        raise KeyError(item)

    def __contains__(self, item: object) -> bool:
        if isinstance(item, Persona):
            return True
        if isinstance(item, str):
            return item in [p.value for p in Persona]
        return False

    def __len__(self) -> int:
        return len(Persona)

    def __iter__(self) -> Iterator[Persona]:
        return iter(Persona)

    def keys(self) -> KeysView[Persona]:
        return dict.fromkeys(Persona).keys()

    def values(self) -> ValuesView[PersonaDefinition]:
        return {p: _load_persona(p) for p in Persona}.values()

    def items(self) -> ItemsView[Persona, PersonaDefinition]:
        return {p: _load_persona(p) for p in Persona}.items()


PERSONAS: Mapping[Persona, PersonaDefinition] = _PersonaRegistry()


def load_custom_repo_persona(repo_path: Path, persona_name: str) -> PersonaDefinition | None:
    """Load a custom team persona prompt defined in .devops/personas/<name>.md under *repo_path*."""
    safe_name = Path(persona_name).name
    if not safe_name or safe_name != persona_name:
        return None
    custom_dir = repo_path / ".devops" / "personas"
    if custom_dir.is_symlink():
        return None
    custom_file = custom_dir / f"{safe_name}.md"
    if custom_file.is_symlink() or not custom_file.is_file():
        return None
    try:
        resolved_repo = repo_path.resolve(strict=True)
        resolved_file = custom_file.resolve(strict=True)
        if not resolved_file.is_relative_to(resolved_repo):
            return None
    except Exception:
        return None
    content = _load(custom_file)
    return PersonaDefinition(
        name=safe_name,
        title=f"Custom Persona ({safe_name.title()})",
        system_prompt=content + "\n\n" + _get_task_review(),
        chat_prompt=content + "\n\n" + _get_task_chat(),
        compose_prompt=content + "\n\n" + _get_task_compose(),
    )
