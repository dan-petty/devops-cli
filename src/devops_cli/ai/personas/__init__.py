"""AI persona definitions for code review and chat."""

from __future__ import annotations

from collections.abc import ItemsView, Iterator, KeysView, Mapping, ValuesView
from enum import StrEnum
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, ConfigDict

_PERSONAS_DIR = Path(__file__).parent
_TASKS_DIR = _PERSONAS_DIR.parent / "tasks"


class Persona(StrEnum):
    DEVSECOPS = "devsecops"
    ARCHITECT = "architect"
    PM = "pm"
    AUDITOR = "auditor"
    QA = "qa"


class PersonaDefinition(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    title: str
    system_prompt: str  # tasks/review.md + prompt.md
    chat_prompt: str  # role.md + tasks/chat.md
    compose_prompt: str  # role.md + tasks/compose.md


def _load(path: Path) -> str:
    return path.read_text(encoding="utf-8").rstrip()


# ── Task prompts loaded once ────────────────────────────────────────────

METADATA_SYSTEM_PROMPT: str = _load(_TASKS_DIR / "metadata.md")
_TASK_REVIEW: str = _load(_TASKS_DIR / "review.md")
_TASK_CHAT: str = _load(_TASKS_DIR / "chat.md")
_TASK_COMPOSE: str = _load(_TASKS_DIR / "compose.md")


@lru_cache
def _load_persona(persona: Persona) -> PersonaDefinition:
    d = _PERSONAS_DIR / persona
    names = {
        Persona.DEVSECOPS: "Principal DevSecOps Engineer",
        Persona.ARCHITECT: "Enterprise Infrastructure Architect",
        Persona.PM: "Enterprise Project Manager",
        Persona.AUDITOR: "NIST/PCI/SOC Auditor",
        Persona.QA: "Senior Test Engineer",
    }
    role = _load(d / "role.md")
    domain = _load(d / "prompt.md")
    return PersonaDefinition(
        name=persona.value,
        title=names[persona],
        system_prompt=role + "\n\n" + _TASK_REVIEW + "\n\n" + domain,
        chat_prompt=role + "\n\n" + _TASK_CHAT,
        compose_prompt=role + "\n\n" + _TASK_COMPOSE,
    )


# ── Lazy-loading Registry ─────────────────────────────────────────────────────────────


class _PersonaRegistry(Mapping[Persona, PersonaDefinition]):
    def __getitem__(self, item: object) -> PersonaDefinition:
        if isinstance(item, Persona):
            return _load_persona(item)
        if isinstance(item, str):
            return _load_persona(Persona(item))
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
