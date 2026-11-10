"""The kinds of question and the typed answer of `devops ai ask-jev` (#4306).

The module holds no client, so the command imports it at start without loading `pydantic_ai`.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict

__all__ = ["JevAnswer", "JevAskKind"]


class JevAskKind(StrEnum):
    """The kind of question that Jev answers."""

    CHOICE = "choice"
    NOUL = "noul"
    SCORE = "score"


class JevAnswer(BaseModel):
    """The typed answer of Jev to one question.

    `answer` is the picked option for `choice`, `yes` or `no` for `noul`, and the score for
    `score`. `probability` is the probability of the picked option (`choice`) or of yes (`noul`),
    and None for `score`. `confidence` is the confidence of Jev in a `choice` or a `score`, and
    None for `noul`. `probabilities` holds one probability for each option, or for each level of a
    rubric. The token counts are those of the one request.
    """

    model_config = ConfigDict(frozen=True)

    kind: JevAskKind
    answer: str
    probability: float | None = None
    confidence: float | None = None
    score: float | None = None
    probabilities: dict[str, float]
    model: str
    input_tokens: int
    output_tokens: int
