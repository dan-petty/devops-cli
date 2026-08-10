"""AI persona definitions for code review and chat."""

from __future__ import annotations

from enum import StrEnum
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


# ── Registry ────────────────────────────────────────────────────────────────────────────

PERSONAS: dict[Persona, PersonaDefinition] = {p: _load_persona(p) for p in Persona}
