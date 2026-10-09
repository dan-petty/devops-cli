"""The review loop's documents name only metrics, commands and paths the code has (#952).

`docs/SELF_IMPROVEMENT.md` once listed five review metrics no code sends, and the knowledge base
taught `devops review` options and subcommands that do not exist, so an agent following either
measured nothing or ran a command that fails.
"""

from __future__ import annotations

from collections.abc import Iterable
from functools import cache
from os.path import commonprefix
from pathlib import Path, PurePosixPath

from devops_cli.ai.review.exporter import export_invalidated_feedback
from devops_cli.config.constants import CONST_FEEDBACK_DATASET_NAME
from devops_cli.config.defaults import DEFAULT_DATA_DIR, DEFAULT_FEEDBACK_DATASET_PATH
from devops_cli.core.command_resolver import (
    ArgvToken,
    CommandReferenceFinding,
    resolve_devops_argv,
)
from devops_cli.telemetry.instruments import INSTRUMENTS
from tests.markdown_examples import code_snippets, devops_commands, shell_words

_ROOT = Path(__file__).resolve().parents[1]
_SELF_IMPROVEMENT = _ROOT / "docs" / "SELF_IMPROVEMENT.md"
# The documents that are not checked, each for a reason:
# - docs/agent/: task files record each item as it was delivered, and no other item edits them;
# - docs/ROADMAP.md: rendered from GitHub at the cut (ADR 0001);
# - docs/CLI_REFERENCE.md and docs/commands/: `devops docs generate` renders them from the Typer
#   app itself, and `devops docs check` keeps them equal to a fresh render.
_UNCHECKED = (
    Path("docs/agent"),
    Path("docs/ROADMAP.md"),
    Path("docs/CLI_REFERENCE.md"),
    Path("docs/commands"),
)


def _documents() -> list[Path]:
    """AGENTS.md, the hand-written pages under docs/, and the knowledge base."""
    pages = [
        *sorted((_ROOT / "docs").rglob("*.md")),
        *sorted((_ROOT / "src/devops_cli/ai/knowledge_base").rglob("*.md")),
    ]
    return [
        _ROOT / "AGENTS.md",
        *(p for p in pages if not any(p.relative_to(_ROOT).is_relative_to(u) for u in _UNCHECKED)),
    ]


def _is_review_command(argv: list[ArgvToken]) -> bool:
    return argv[:1] == ["review"] or argv[:2] == ["ai", "review"]


def _may_show_a_review_command(path: Path) -> bool:
    """Whether a document can show a `devops review` command, whose words follow one another
    across any whitespace or line continuation. Only such a document is parsed."""
    words = " ".join(path.read_text(encoding="utf-8").replace("\\\n", " ").split())
    return "devops review" in words or "devops ai review" in words


def _review_examples(paths: Iterable[Path]) -> dict[str, list[ArgvToken]]:
    """Each `devops review` and `devops ai review` command the documents show, by where it is."""
    return {
        f"{path.name}:{line}: devops {' '.join(map(str, argv))}": argv
        for path in paths
        if _may_show_a_review_command(path)
        for snippet in code_snippets(path)
        for line, argv in devops_commands(snippet)
        if _is_review_command(argv)
    }


@cache
def _resolved(argv: tuple[ArgvToken, ...]) -> CommandReferenceFinding | None:
    """The token the Typer app refuses in `argv`; the documents repeat commands, so each distinct
    one is parsed once."""
    return resolve_devops_argv(argv)


def _unparsed(examples: dict[str, list[ArgvToken]]) -> list[str]:
    """Each example the Typer app refuses, with the token it refused."""
    return sorted(
        f"{where}: {finding.describe()}"
        for where, argv in examples.items()
        if (finding := _resolved(tuple(argv))) is not None
    )


def _dataset_paths(paths: Iterable[Path]) -> dict[str, str]:
    """Each path the documents' code names for the feedback dataset, by where it is.

    The value of an option or an environment assignment (`--output=<path>`) counts as the path.
    """
    return {
        f"{path.name}:{snippet.line}: {word}": word.rpartition("=")[2]
        for path in paths
        if CONST_FEEDBACK_DATASET_NAME in path.read_text(encoding="utf-8")
        for snippet in code_snippets(path)
        for line in snippet.text.splitlines()
        for word in shell_words(line)
        if PurePosixPath(word.rpartition("=")[2]).name == CONST_FEEDBACK_DATASET_NAME
    }


def test_every_metric_self_improvement_names_is_one_devops_cli_sends() -> None:
    """A metric name in SELF_IMPROVEMENT is a registered instrument or one of its series.
    Section 4 once listed `devops_cli_review_sessions_total` and four more metrics nothing sends."""
    sent = {name for i in INSTRUMENTS for name in (i.name, *i.series)}
    namespace = commonprefix([instrument.name for instrument in INSTRUMENTS])
    named = {s.text for s in code_snippets(_SELF_IMPROVEMENT) if s.text.startswith(namespace)}
    assert (sorted(named - sent), bool(named)) == ([], True)


def test_every_devops_review_example_in_the_documents_parses() -> None:
    """Each `devops review` example in AGENTS.md, docs/ and the knowledge base parses with the
    Typer app. The knowledge base taught `devops ai review patch` and `--provider`, which do not
    exist."""
    examples = _review_examples(_documents())
    assert (_unparsed(examples), len(examples) > 50) == ([], True)


def test_every_feedback_dataset_path_the_documents_name_is_where_the_exporter_writes(
    isolate_data_dir: Path,
) -> None:
    """The exporter appends to `feedback_dataset.jsonl` in the data directory, `.data` unless
    `DEVOPS_CLI_DATA_DIR` moves it, and every path the documents name for the dataset is that
    one."""
    _, written = export_invalidated_feedback()
    named = _dataset_paths(_documents())
    allowed = {CONST_FEEDBACK_DATASET_NAME, DEFAULT_FEEDBACK_DATASET_PATH.as_posix()}
    wrong = sorted(where for where, path in named.items() if path not in allowed)
    expected = isolate_data_dir / DEFAULT_FEEDBACK_DATASET_PATH.relative_to(DEFAULT_DATA_DIR)
    assert (written, wrong, bool(named)) == (expected, [], True)


def test_the_checks_catch_a_wrong_example_and_a_wrong_dataset_path(tmp_path: Path) -> None:
    """Negative control: the forms the documents carried before #949 and #950, a positional
    finding index and the dataset under `.data/reviews/`, are caught, in a fence and a span. A
    command that a shell operator touches (`stats;`, `stats|head`) ends at the operator, so it is
    not reported."""
    page = tmp_path / "page.md"
    page.write_text(
        "Judge it with `devops review verify 20260910-143644 3 --status VERIFIED`.\n\n"
        "Count them with `devops review stats; echo done`.\n\n"
        "- Then export:\n\n"
        "  ```bash\n"
        "  devops review stats|head\n"
        "  devops review export-feedback --status ALL \\\n"
        "    --output .data/reviews/feedback_dataset.jsonl\n"
        "  ```\n",
        encoding="utf-8",
    )
    examples = _review_examples([page])
    unparsed = _unparsed(examples)
    stats = [argv for argv in examples.values() if argv[1:2] == ["stats"]]
    assert (
        len(unparsed),
        "'3'" in unparsed[0],
        stats,
        list(_dataset_paths([page]).values()),
    ) == (
        1,
        True,
        [["review", "stats"], ["review", "stats"]],
        [".data/reviews/feedback_dataset.jsonl"],
    )
