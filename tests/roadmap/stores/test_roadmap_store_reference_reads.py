"""Contract cases of the roadmap store for the reads of the reference step (#4672), over the
in-memory adapter: the code search, the repository search, the reference facts of a repository and
the file of another repository. `test_roadmap_github_store_reference_search.py` pins the requests
of the GitHub adapter for the same reads.
"""

from __future__ import annotations

import pytest

from devops_cli.exceptions.git import GitHubFileNotFoundError, GitHubOperationError
from devops_cli.roadmap.stores.store import CodeSearchHit, ReferenceFacts
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore

HEAD = "a" * 40
HIT = CodeSearchHit(repository="example/agent", path="src/agent.py")
OTHER = CodeSearchHit(repository="example/app", path="app/run.py")
FACTS = ReferenceFacts(
    full_name="example/agent",
    url="https://github.com/example/agent",
    private=False,
    license="MIT",
    stars=7,
    head_sha=HEAD,
    has_tests=True,
)


@pytest.fixture
def store() -> InMemoryRoadmapStore:
    return InMemoryRoadmapStore(repo="example/roadmap")


def test_a_code_search_gives_the_hits_of_its_query_up_to_the_limit(
    store: InMemoryRoadmapStore,
) -> None:
    store.seed_code_search("pydantic_ai", HIT, OTHER)

    found = (
        store.search_code("pydantic_ai", limit=5),
        store.search_code("pydantic_ai", limit=1),
        store.search_code("another query", limit=5),
    )

    assert (found, store.code_searches) == (
        ([HIT, OTHER], [HIT], []),
        ["pydantic_ai", "pydantic_ai", "another query"],
    )


def test_a_repository_search_gives_the_repositories_of_its_query(
    store: InMemoryRoadmapStore,
) -> None:
    store.seed_repository_search("pydantic-ai", FACTS)

    found = (
        store.search_repositories("pydantic-ai", limit=5),
        store.search_repositories("another query", limit=5),
    )

    assert (found, store.repository_searches) == (([FACTS], []), ["pydantic-ai", "another query"])


def test_reference_facts_are_those_seeded_for_the_repository(store: InMemoryRoadmapStore) -> None:
    store.seed_reference_facts(FACTS)

    found = (store.reference_facts("example/agent"), store.reference_facts("example/none"))

    assert (found, store.reference_reads) == ((FACTS, None), ["example/agent", "example/none"])


def test_a_file_of_another_repository_is_read_at_its_commit_and_a_missing_one_raises(
    store: InMemoryRoadmapStore,
) -> None:
    store.seed_file("src/agent.py", "the file of this repository\n")
    store.seed_other_file("example/agent", "src/agent.py", "import pydantic_ai\n", ref=HEAD)

    text = store.repository_file("src/agent.py", ref=HEAD, repository="example/agent")
    with pytest.raises(GitHubFileNotFoundError, match=r"example/agent has no gone\.py"):
        store.repository_file("gone.py", ref=HEAD, repository="example/agent")

    assert (text, store.repository_file("src/agent.py"), store.other_file_reads) == (
        "import pydantic_ai\n",
        "the file of this repository\n",
        [("example/agent", "src/agent.py", HEAD), ("example/agent", "gone.py", HEAD)],
    )


@pytest.mark.parametrize("read", ["search_code", "search_repositories", "reference_facts"])
def test_a_reference_read_that_github_fails_raises_its_error(
    store: InMemoryRoadmapStore, read: str
) -> None:
    store.fail_read(read, GitHubOperationError("HTTP 502", operation="roadmap.read"))
    calls = {
        "search_code": lambda: store.search_code("x", limit=1),
        "search_repositories": lambda: store.search_repositories("x", limit=1),
        "reference_facts": lambda: store.reference_facts("example/agent"),
    }

    with pytest.raises(GitHubOperationError, match="HTTP 502"):
        calls[read]()
