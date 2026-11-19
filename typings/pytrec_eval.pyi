"""The part of pytrec_eval that devops-cli calls. pytrec_eval ships no type information."""

class RelevanceEvaluator:
    def __init__(
        self, qrels: dict[str, dict[str, int]], measures: set[str] | list[str]
    ) -> None: ...
    def evaluate(self, run: dict[str, dict[str, float]]) -> dict[str, dict[str, float]]: ...
