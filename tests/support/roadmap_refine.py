"""The helpers that the `devops roadmap refine` test files share: the checkout and store fixtures,
the scripted gateway and the builders of items and proposals (#1335).
"""

from __future__ import annotations

import fnmatch
import json
from collections import Counter
from collections.abc import Callable, Mapping
from datetime import UTC, date, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from tests.support.fakes.model import ModelFake
import httpx2
import pytest

from devops_cli.ai.client.models import (
    AIClientError,
)
from devops_cli.config import constants
from devops_cli.config.settings import reset_settings_cache
from devops_cli.roadmap.body_hash import hash_text
from devops_cli.roadmap.refine.refine import (
    AcceptanceCriterion,
    QuestionAnswer,
    RefinementProposal,
    RefinePlan,
    apply_refine,
    plan_refine,
)
from devops_cli.roadmap.stores.store import (
    AlternativesRecordKey,
    GitHubState,
    Item,
    ItemField,
    RefineRecordKey,
    install_roadmap_store,
)
from tests.support.fakes.clock import ClockFake
from tests.support.fakes.git import GitFake
from tests.support.fakes.http import WebFake
from tests.support.fakes.process import ProcessAnswer
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.llm_stream_fakes import serve_llm
from tests.support.roadmap_jobs import due_job_runner

run_refine_adapter = due_job_runner("refine")


REPO = "example/roadmap"


REFINE_HEAD_SHA = "0123456789abcdef0123456789abcdef01234567"


# One acceptance criterion in the shape of an OpenSpec requirement, and the existing-tool answer
# that every proposal carries (#1849).
CRITERION = AcceptanceCriterion(
    name="A design",
    requirement="The item SHALL have a design.",
    scenario="A person reads the item",
    when="a person reads the item",
    then="the design is in the item",
)


CRITERION_JSON = CRITERION.model_dump()


NO_OPEN_TOOL = "No open tool covers the need."


# The open milestones, planning buckets in due-date order: the first, then the second.
FIRST = "2026-10-29"
SECOND = "2026-11-05"
THIRD = "2026-11-12"


# The Priority that makes an issue an Item, as a person sets it.
PLACED = {ItemField.PRIORITY: "P2-Medium"}


def _clean_path_str(target: str) -> str:
    return target.split(":", 1)[1] if ":" in target else target


def _answer_show(repo: Path, target: str) -> ProcessAnswer:
    path_str = _clean_path_str(target)
    p = repo / path_str
    if p.is_file():
        return ProcessAnswer(returncode=0, stdout=p.read_text(encoding="utf-8"))
    return ProcessAnswer(returncode=1, stderr=f"fatal: path '{path_str}' does not exist")


def _answer_ls_tree(repo: Path, target_dir: Path) -> ProcessAnswer:
    if not target_dir.is_dir():
        return ProcessAnswer(returncode=0, stdout="")
    paths = [str(f.relative_to(repo)) for f in sorted(target_dir.rglob("*")) if f.is_file()]
    out = "\0".join(paths) + ("\0" if paths else "")
    return ProcessAnswer(returncode=0, stdout=out)


def _file_grep_matches(f: Path, repo: Path, ident: str) -> list[str]:
    lines = f.read_text(encoding="utf-8").splitlines()
    rel = str(f.relative_to(repo))
    return [f"{rel}:{idx}:{line}" for idx, line in enumerate(lines, 1) if ident in line]


def _answer_grep(repo: Path, ident: str) -> ProcessAnswer:
    matches: list[str] = []
    for f in sorted(repo.rglob("*.py")):
        if f.is_file():
            matches.extend(_file_grep_matches(f, repo, ident))
    if matches:
        return ProcessAnswer(returncode=0, stdout="\n".join(matches) + "\n")
    return ProcessAnswer(returncode=1)


def _answer_grep_files(repo: Path, argv: list[str]) -> ProcessAnswer:
    """`grep -l -z -F -e <needle>... <sha> -- <pathspec>...`: the NUL-ended `<sha>:<path>` of each
    file under a pathspec that holds a needle."""
    needles = [argv[i + 1] for i, arg in enumerate(argv) if arg == "-e"]
    specs = argv[argv.index("--") + 1 :]
    found = []
    for f in sorted(p for p in repo.rglob("*") if p.is_file()):
        rel = f.relative_to(repo).as_posix()
        in_scope = not specs or any(fnmatch.fnmatch(rel, s) or rel.startswith(s) for s in specs)
        if in_scope and any(n in f.read_text(encoding="utf-8") for n in needles):
            found.append(f"{REFINE_HEAD_SHA}:{rel}")
    if not found:
        return ProcessAnswer(returncode=1)
    return ProcessAnswer(stdout="\0".join(found) + "\0")


def _answer_refine_git(repo: Path, argv: list[str]) -> ProcessAnswer:
    if argv[1:] == ["remote", "get-url", "origin"]:
        return ProcessAnswer(stdout=f"https://example.com/{REPO}.git\n")
    if "rev-parse" in argv and "HEAD" in argv:
        return ProcessAnswer(stdout=f"{REFINE_HEAD_SHA}\n")
    if "cat-file" in argv and "-e" in argv:
        p = repo / _clean_path_str(argv[-1])
        return ProcessAnswer(returncode=0 if p.is_file() else 1)
    if "show" in argv:
        return _answer_show(repo, argv[-1])
    if "ls-tree" in argv:
        target_dir = repo / argv[-1] if len(argv) > 6 else repo
        return _answer_ls_tree(repo, target_dir)
    if "grep" in argv and "-l" in argv:
        return _answer_grep_files(repo, argv)
    if "grep" in argv:
        ident_idx = argv.index("-e") + 1
        return _answer_grep(repo, argv[ident_idx])
    return ProcessAnswer()


@pytest.fixture
def git_repo(tmp_path: Path, git_fake: GitFake) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()

    (repo / "CONTEXT.md").write_text("# Project Context\nArchitecture notes.\n", encoding="utf-8")
    (repo / "docs" / "adr").mkdir(parents=True)
    (repo / "docs" / "adr" / "0001-test.md").write_text(
        "# ADR 1\nDecision record.\n", encoding="utf-8"
    )
    (repo / "src").mkdir()
    (repo / "src" / "sample.py").write_text(
        "def hello_world():\n    return 'hello'\n", encoding="utf-8"
    )

    git_fake.answer(
        lambda call: bool(call.argv and call.argv[0] == "git"),
        lambda call: _answer_refine_git(repo, list(call.argv)),
    )
    return repo


class BodyReadCountingStore(InMemoryRoadmapStore):
    """The in-memory roadmap, keeping the number of each issue whose body it is asked to read."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.body_reads: list[int] = []

    def read_issue_body(self, number: int) -> str:
        self.body_reads.append(number)
        return super().read_issue_body(number)


@pytest.fixture
def store() -> BodyReadCountingStore:
    """The roadmap, installed as the store every command opens during the test."""
    s = BodyReadCountingStore(repo=REPO)
    s.seed_milestone(FIRST, due_on=date(2026, 10, 29), state=GitHubState.OPEN)
    s.seed_milestone(SECOND, due_on=date(2026, 11, 5), state=GitHubState.OPEN)
    install_roadmap_store(lambda repo, **_: s)
    return s


class MockLLMClient:
    def __init__(
        self,
        proposal: RefinementProposal | None = None,
        fail_with: AIClientError | None = None,
    ):
        self.fail_with = fail_with
        self.proposal = proposal or RefinementProposal(
            existing_tool=NO_OPEN_TOOL,
            problem_statement="Test problem",
            acceptance_criteria=[CRITERION],
            key_questions=[],
            fits_one_pr=True,
            split_offs=[],
            suspected_block=None,
            dependencies=[],
        )
        self.calls: list[tuple[str, str, Any]] = []

    def chat_structured(self, system: str, prompt: str, schema: type[Any], **_: Any) -> Any:
        self.calls.append((system, prompt, schema))
        if self.fail_with is not None:
            raise self.fail_with
        return self.proposal


def require_item(store: InMemoryRoadmapStore, number: int) -> Item:
    item = store.item(number)
    assert item is not None
    return item


def record_alternatives_check(
    store: InMemoryRoadmapStore, number: int, verdict: str, *, tool: str | None = None
) -> None:
    """What the alternatives job leaves on item `number`: its block in the body and its verdict
    in the job record. `tool` is the URL of the tool of a `covers` or `partly` verdict (#2951)."""
    body = store.read_issue_body(number)
    block = (
        f"{constants.CONST_ROADMAP_ALTERNATIVES_START_MARKER}\n"
        f"Alternatives check of 2026-11-14: {verdict}.\n"
        f"{constants.CONST_ROADMAP_ALTERNATIVES_END_MARKER}"
    )
    store.write_issue_body(number, f"{body}\n\n{block}")
    store.set_marks(
        require_item(store, number),
        {
            AlternativesRecordKey.CHECKED_AT: datetime.now(UTC).isoformat(),
            AlternativesRecordKey.VERDICT: verdict,
            AlternativesRecordKey.TOOL: tool,
        },
    )


def comment_bodies(store: InMemoryRoadmapStore, number: int) -> list[str]:
    """The body of each comment on issue `number`, oldest first."""
    return [comment.body for comment in store.comments_on(number)]


def seed_item(
    store: InMemoryRoadmapStore,
    status: str,
    priority: str,
    *,
    milestone: str | None = None,
    labels: tuple[str, ...] = (),
    refined: bool = False,
    title: str | None = None,
    body: str | None = None,
) -> int:
    """An open item on the board with `status` and `priority`; `refined` gives it the record a
    refine round leaves."""
    number = store.seed_issue(
        title or f"{status} {priority}",
        body=body or f"Body {priority}",
        milestone=milestone,
        labels=labels,
        fields=PLACED,
    )
    store.set_field(require_item(store, number), ItemField.STATUS, status)
    store.set_field(require_item(store, number), ItemField.PRIORITY, priority)
    if refined:
        record = {RefineRecordKey.BODY_HASH: "body", RefineRecordKey.SECTION_HASH: "section"}
        store.set_marks(require_item(store, number), record)
    return number


# ── A failed model call skips only its item (#1363) ────────────────────────────────────────

_GATEWAY_CONFIG = (
    "telemetry:\n  enabled: false\n  endpoint: http://localhost:4318\n"
    "ai:\n  allow_private_network: true\n  provider: gateway\n"
    "  gateway_url: http://example.com:4000/v1\n  model: demo-model\n  rag:\n    enabled: false\n"
    "qdrant:\n  url: http://localhost:6333\n"
)


_READY_PROPOSAL = json.dumps(
    {
        "existing_tool": NO_OPEN_TOOL,
        "problem_statement": "The item needs a design.",
        "acceptance_criteria": [CRITERION_JSON],
    }
)


# Three violations, one of them a key whose name is the model's own text.
SCHEMA_MISS = json.dumps(
    {
        "existing_tool": NO_OPEN_TOOL,
        "problem_statement": "The item needs a design.",
        "acceptance_criteria": ["a plain string"],
        "issue": 1,
        "leaked_model_key": "y",
    }
)


# The retry transport of the model client sends a request that the gateway answers with a 5xx
# five times, so a failing item costs this many requests in a round.
GATEWAY_ATTEMPTS = 5


# What the gateway answers for an issue: the reply's text, or the HTTP response itself.
Answer = str | httpx2.Response


@pytest.fixture
def scripted_gateway(
    isolate_devops_cli_config: Path, web: WebFake, clock: ClockFake
) -> Callable[..., list[httpx2.Request]]:
    """Point refine's `analysis` model at a gateway whose answer to each issue is scripted.

    Every request refine's client sends ends at the `web` fake, which reads the issue's number
    from the JSON document the request's user message carries. Retries wait no time: the `clock`
    fixture answers each wait.
    """
    isolate_devops_cli_config.write_text(_GATEWAY_CONFIG, encoding="utf-8")
    reset_settings_cache()

    def script(
        answers: Mapping[int | None, Answer], default: Answer = _READY_PROPOSAL
    ) -> list[httpx2.Request]:
        def answer(request: httpx2.Request) -> httpx2.Response:
            scripted = answers.get(_issue_number(request), default)
            if isinstance(scripted, httpx2.Response):
                return scripted
            choice = {"message": {"content": scripted}, "finish_reason": "stop"}
            usage = {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}
            return httpx2.Response(200, json={"choices": [choice], "usage": usage})

        return serve_llm(web, answer)

    return script


def seed_new_items(
    store: InMemoryRoadmapStore, priorities: tuple[str, ...] = ("P1-High", "P2-Medium", "P3-Low")
) -> list[int]:
    """A New backlog item of each priority on a private repository, refined in the order
    returned."""
    store.seed_visibility(is_private=True)
    person = store.as_actor("alice")
    numbers: list[int] = []
    for priority in priorities:
        number = person.seed_issue(f"Item {priority}", body=f"Body {priority}", fields=PLACED)
        person.set_field(require_item(person, number), ItemField.STATUS, "New")
        person.set_field(require_item(person, number), ItemField.PRIORITY, priority)
        numbers.append(number)
    return numbers


def _issue_number(request: httpx2.Request) -> int | None:
    """The issue a refine request is about, or None for a request about none."""
    document = json.loads(json.loads(request.content)["messages"][1]["content"])
    number: int | None = document.get("number")
    return number


def requests_per_item(sent: list[httpx2.Request]) -> dict[int | None, int]:
    return dict(Counter(_issue_number(request) for request in sent))


def refine_round(
    store: InMemoryRoadmapStore, source: Path, *, limit: int | None = None
) -> RefinePlan:
    """One round of `devops roadmap refine --confirm`, planned and then applied."""
    plan = (
        plan_refine(store, repo=REPO, source=source)
        if limit is None
        else plan_refine(store, repo=REPO, source=source, limit=limit)
    )
    apply_refine(store, plan)
    return plan


# ── Each item refine cannot set Ready gets a next step (#1758) ────────────────────────────

READY = RefinementProposal(
    existing_tool=NO_OPEN_TOOL,
    problem_statement="The item needs a design.",
    acceptance_criteria=[CRITERION],
)


QUESTION = READY.model_copy(
    update={
        "key_questions": [
            QuestionAnswer(
                question="Which store holds the record?", answer="A person picks it.", kind="person"
            )
        ]
    }
)


SPLIT = READY.model_copy(
    update={"fits_one_pr": False, "split_offs": ["The first change.", "The second change."]}
)


def blocked_by_issue(blocker: int) -> RefinementProposal:
    """A complete proposal that names the item `blocker` as its one dependency and holds no
    suspected block, so the dependency alone decides (#3500)."""
    return READY.model_copy(update={"dependencies": [blocker]})


def replies_sent(model_fake: ModelFake) -> list[str]:
    """The replies the last proposal request carried."""
    replies: list[str] = json.loads(model_fake.calls[-1].prompt)["replies"]
    return replies


# ── A change to the code its block cites ends an item's wait (#2005) ──────────────────────

CITED_PATH = "src/sample.py"


def block_in_code(blocker: int | None) -> RefinementProposal:
    """A proposal whose block the code in `src/sample.py` causes: it waits on the open item
    `blocker`, or, with None, on a suspected block alone, which a person decides."""
    proposal = READY.model_copy(
        update={
            "suspected_block": "`hello_world` in src/sample.py returns a fixed text.",
            "block_paths": [CITED_PATH],
        }
    )
    return proposal if blocker is None else proposal.model_copy(update={"dependencies": [blocker]})


def refine_comment_at(store: InMemoryRoadmapStore, number: int) -> datetime:
    """When refine last commented on issue `number`."""
    marker = constants.CONST_ROADMAP_REFINE_COMMENT_MARKER
    return [c.created_at for c in store.comments_on(number) if marker in c.body][-1]


def seed_item_blocked_in_code(
    store: InMemoryRoadmapStore, model_fake: ModelFake, *, blocked: bool = True
) -> int:
    """On a private repository, a New backlog P1 whose proposal cites `src/sample.py` as the
    cause of its block: it waits on an item In Progress, or on a person when not `blocked`."""
    store.seed_visibility(is_private=True)
    blocker = seed_item(store, "In Progress", "P1-High")
    number = seed_item(store, "New", "P1-High")
    model_fake.answer(block_in_code(blocker if blocked else None))
    return number


# ── Body questions, decisions and the web search state (#2398) ────────────────────────────


def seed_with_body(store: InMemoryRoadmapStore, body: str) -> int:
    """A New P1 backlog item with `body`, on a private repository."""
    store.seed_visibility(is_private=True)
    return store.seed_issue(
        "Item", body=body, fields={ItemField.STATUS: "New", ItemField.PRIORITY: "P1-High"}
    )


# ── A wait ends when its cause ends (#3483) ───────────────────────────────────────────────

STAGE_MARKER = constants.CONST_ROADMAP_STAGE_COMMENT_MARKER


REFINE_MARKER = constants.CONST_ROADMAP_REFINE_COMMENT_MARKER


STAGE_EVIDENCE = "The plan needs `hello_world` to return a name. It returns a fixed text."


def stage_returns(store: InMemoryRoadmapStore, number: int) -> None:
    """The stage job returns the item to New with a comment: the comment first, then the Status."""
    store.comment(
        number,
        f"{STAGE_MARKER}\nThe stage job returned the item to New.\n\nEvidence:\n\n{STAGE_EVIDENCE}",
    )
    store.set_field(require_item(store, number), ItemField.STATUS, "New")


def seed_person_wait(store: InMemoryRoadmapStore, text: str, *, paths: str | None = None) -> int:
    """A New item whose last refine round left it waiting on a person, with `text` in the comment
    of that round, as a round with the same body would leave it."""
    number = seed_item(store, "New", "P1-High")
    record: dict[RefineRecordKey, str | None] = {
        RefineRecordKey.BODY_HASH: hash_text(require_item(store, number).body),
        RefineRecordKey.NEXT_STEP: "person",
        RefineRecordKey.BLOCK_PATHS: paths,
    }
    store.set_marks(require_item(store, number), record)
    store.seed_comment(number, f"{REFINE_MARKER}\nA person answers these questions.\n\n- {text}")
    return number
