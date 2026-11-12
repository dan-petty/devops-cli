"""The alternatives check reads the facts of the project: the tools in use and the ADRs (#4661).

A `covers` or `partly` verdict whose tool the repository already uses becomes `in-use` by a code
rule. The inventory of the repository holds the package URLs of the SBOM that the dependency graph
exports, the text of the deployed paths of a clone, and the packages that deps.dev links to the
GitHub project of the tool. `rejected` needs an option of the ADR that rejects the tool. A check
records the canonical id of its tool and the hash of the ADRs it read, and an item whose hash
differs from the ADRs at HEAD is checked again.

The roadmap is the in-memory store, deps.dev and PyPI answer at the HTTP edge through `web`, and a
clone is a tree under `tmp_path`. The census replay reads `tests/fixtures/roadmap/
alternatives_census.json`: the 97 `covers` and `partly` checks of the census of 2026-11-11, and the
SBOM, the deployed words, the PyPI projects and the deps.dev answers recorded at the commit it names.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlsplit

import pytest

from devops_cli.config.defaults import DEFAULT_DEPS_DEV_PROJECT_URL, DEFAULT_PYPI_PACKAGE_URL
from devops_cli.roadmap import alternatives
from devops_cli.roadmap.adr import Adr
from devops_cli.roadmap.alternatives import (
    AlternativesPlan,
    AlternativesReply,
    AlternativesTools,
    Check,
    ToolFacts,
    Verdict,
    select_items,
)
from devops_cli.roadmap.inventory import Inventory, canonical_id, project_of, read_inventory
from devops_cli.roadmap.stores.store import AlternativesRecordKey, ItemField
from tests.support.fakes.http import WebFake
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.paths import FIXTURES
from tests.support.roadmap_alternatives import apply_alternatives

pytestmark = pytest.mark.usefixtures("keyring_store")

REPO = "example/roadmap"
NOW = datetime(2026, 11, 12, 12, 0, tzinfo=UTC)
PATHS = ("k8s", "tf", ".devcontainer", "src/devops_cli/tools_lock/tools.lock")
REASON = "The tool reads a directory, and the item needs that."
IN_REPOSITORY = "The repository already uses this tool."
CENSUS = FIXTURES / "roadmap" / "alternatives_census.json"


@pytest.fixture
def store() -> InMemoryRoadmapStore:
    return InMemoryRoadmapStore(repo=REPO, is_private=False)


def _item(store: InMemoryRoadmapStore, title: str = "Scan a directory") -> int:
    return store.seed_issue(
        title,
        body="The job needs to read every file of a directory.",
        fields={ItemField.PRIORITY: "P2-Medium", ItemField.STATUS: "New"},
        author_association="COLLABORATOR",
    )


def _facts(url: str, *, project: str | None = None) -> ToolFacts:
    name = urlsplit(url).path.strip("/").removeprefix("project/")
    return ToolFacts(
        name=name,
        url=url,
        license="MIT",
        last_activity=NOW - timedelta(days=3),
        project=project,
    )


def _check(
    store: InMemoryRoadmapStore,
    number: int,
    facts: ToolFacts,
    *,
    inventory: Inventory | None = None,
    adrs: tuple[Adr, ...] = (),
    **changes: Any,
) -> Check:
    """The check of item `number` from a reply that gives `covers` for the tool of `facts`."""
    item = store.item(number)
    assert item is not None
    tools = AlternativesTools(store=store)
    tools.searches.append(alternatives.Search("scanner", 1))
    tools.facts[facts.url] = facts
    reply = AlternativesReply(reason=REASON, verdict=Verdict.COVERS, tool_url=facts.url)
    reply = reply.model_copy(update=changes)
    check = alternatives.validate_reply(item, reply, tools, NOW, adrs, inventory=inventory)
    assert isinstance(check, Check)
    return check


def _deps_dev(web: WebFake, project: str, *packages: tuple[str, str]) -> None:
    """Make deps.dev link each `(system, name)` of `packages` to `project` as its source."""
    body = {
        "versions": [
            {
                "versionKey": {"system": system, "name": name, "version": "1.0.0"},
                "relationType": "SOURCE_REPO",
                "relationProvenance": "UNVERIFIED_METADATA",
            }
            for system, name in packages
        ]
    }
    url = DEFAULT_DEPS_DEV_PROJECT_URL.format(project=quote(project, safe=""))
    web.content(url, json.dumps(body).encode())


# ── The tools in use ──────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("url", "purl"),
    [
        pytest.param("https://pypi.org/project/MCP", "pkg:pypi/mcp@2.3.0", id="pypi"),
        pytest.param(
            "https://github.com/actions/checkout",
            "pkg:githubactions/actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1",
            id="action",
        ),
        pytest.param(
            "https://github.com/github/codeql-action",
            "pkg:githubactions/github/codeql-action/init@2892aa5e19bbd11bc0cff5427e3b750a04d9e3c2",
            id="action-with-a-path",
        ),
        pytest.param(
            "https://github.com/devcontainers/cli",
            "pkg:npm/%40devcontainers/cli@0.89.0",
            id="npm-scope",
        ),
    ],
)
def test_a_tool_whose_package_the_sbom_holds_is_in_use(
    store: InMemoryRoadmapStore, url: str, purl: str
) -> None:
    store.seed_dependencies("pkg:pypi/httpx@0.28.1", purl)
    number = _item(store)

    check = _check(store, number, _facts(url), inventory=read_inventory(store, None, PATHS))

    assert (
        check.verdict,
        IN_REPOSITORY in check.comment.splitlines(),
        IN_REPOSITORY in check.new_body.splitlines(),
    ) == (Verdict.IN_USE, True, True)


def test_a_tool_that_the_deployed_paths_of_the_clone_name_is_in_use(
    store: InMemoryRoadmapStore, tmp_path: Path
) -> None:
    """A service or a CLI that no manifest names: the deployed paths name it as a whole word, in
    any case. A word in another path, or a longer word, names no tool."""
    (tmp_path / "k8s" / "gateway").mkdir(parents=True)
    (tmp_path / "k8s" / "gateway" / "deployment.yaml").write_text(
        "image: ghcr.io/berriai/LiteLLM:main\n", encoding="utf-8"
    )
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "notes.md").write_text("Velero backs up volumes.\n", encoding="utf-8")
    (tmp_path / "tf").mkdir()
    (tmp_path / "tf" / "main.tf").write_text('source = "trivyscan"\n', encoding="utf-8")
    inventory = read_inventory(store, tmp_path, PATHS)
    number = _item(store)

    verdicts = [
        _check(store, number, _facts(url), inventory=inventory).verdict
        for url in (
            "https://github.com/BerriAI/litellm",
            "https://github.com/velero-io/velero",
            "https://github.com/aquasecurity/trivy",
        )
    ]

    assert verdicts == [Verdict.IN_USE, Verdict.COVERS, Verdict.COVERS]


def test_a_github_tool_whose_package_deps_dev_links_and_the_sbom_holds_is_in_use(
    store: InMemoryRoadmapStore, web: WebFake
) -> None:
    """The repository `modelcontextprotocol/python-sdk` ships the PyPI package `mcp`."""
    project = "github.com/modelcontextprotocol/python-sdk"
    _deps_dev(web, project, ("PYPI", "MCP"), ("GO", "github.com/modelcontextprotocol/python-sdk"))
    store.seed_dependencies("pkg:pypi/mcp@2.3.0")
    number = _item(store)

    check = _check(
        store,
        number,
        _facts("https://github.com/modelcontextprotocol/python-sdk"),
        inventory=read_inventory(store, None, PATHS),
    )

    assert (check.verdict, web.requested) == (
        Verdict.IN_USE,
        [DEFAULT_DEPS_DEV_PROJECT_URL.format(project=quote(project, safe=""))],
    )


def test_a_tool_that_no_source_holds_keeps_its_verdict_and_an_empty_sbom_asks_no_deps_dev(
    store: InMemoryRoadmapStore, web: WebFake
) -> None:
    """deps.dev answers 404 for a project it does not know. With no package in the SBOM, no
    package that deps.dev links can be in it, so the check asks deps.dev nothing."""
    number = _item(store)
    url = "https://github.com/velero-io/velero"
    empty = _check(store, number, _facts(url), inventory=read_inventory(store, None, PATHS))
    store.seed_dependencies("pkg:pypi/httpx@0.28.1")

    unknown = _check(store, number, _facts(url), inventory=read_inventory(store, None, PATHS))

    assert ((empty.verdict, unknown.verdict), len(web.requested)) == (
        (Verdict.COVERS, Verdict.COVERS),
        1,
    )


def test_a_pypi_read_gives_the_project_that_the_package_names_as_its_source(
    store: InMemoryRoadmapStore, web: WebFake
) -> None:
    """The canonical id of a PyPI tool is the GitHub project of its `Source` URL, so the package
    and the repository of one tool get one id."""
    package = {
        "info": {
            "name": "pydantic-ai-slim",
            "version": "1.0.0",
            "license_expression": "MIT",
            "package_url": "https://pypi.org/project/pydantic-ai-slim/",
            "project_urls": {
                "Changelog": "https://github.com/pydantic/pydantic-ai/releases",
                "Documentation": "https://pydantic.dev/docs/ai/",
                "Source": "https://github.com/Pydantic/Pydantic-AI",
            },
        },
        "urls": [{"upload_time_iso_8601": "2026-11-01T10:00:00Z"}],
    }
    web.content(
        DEFAULT_PYPI_PACKAGE_URL.format(name="pydantic-ai-slim"), json.dumps(package).encode()
    )
    tools = AlternativesTools(store=store)

    tools.pypi_package("pydantic-ai-slim")

    (facts,) = tools.facts.values()
    assert facts.project == "github.com/pydantic/pydantic-ai"


@pytest.mark.parametrize(
    ("url", "project", "expected"),
    [
        pytest.param(
            "https://github.com/Fission-AI/OpenSpec",
            None,
            "github.com/fission-ai/openspec",
            id="repository",
        ),
        pytest.param(
            "https://pypi.org/project/gidgethub",
            "github.com/gidgethub/gidgethub",
            "github.com/gidgethub/gidgethub",
            id="package-with-a-source",
        ),
        pytest.param(
            "https://pypi.org/project/Markdown_It.py", None, "pkg:pypi/markdown-it-py", id="package"
        ),
        pytest.param("https://example.com/tool", None, "https://example.com/tool", id="other"),
    ],
)
def test_the_canonical_id_of_a_tool_is_its_github_project_else_its_package_url(
    url: str, project: str | None, expected: str
) -> None:
    assert canonical_id(url, project) == expected


def test_a_check_records_the_canonical_id_of_its_tool_and_the_hash_of_its_adrs(
    store: InMemoryRoadmapStore,
) -> None:
    number = _item(store)
    adr = Adr(8, "Argo Workflows runs the jobs", "## Considered Options\n\n- **DBOS**: rejected.")
    check = _check(
        store,
        number,
        _facts("https://pypi.org/project/gidgethub", project="github.com/gidgethub/gidgethub"),
        adrs=(adr,),
    )

    apply_alternatives(store, AlternativesPlan(repo=REPO, checks=[check]))

    item = store.item(number)
    assert item is not None
    assert (
        item.job_record.get(AlternativesRecordKey.TOOL_ID),
        item.job_record.get(AlternativesRecordKey.ADR_HASH),
    ) == ("github.com/gidgethub/gidgethub", alternatives.adr_hash_of((adr,)))


# ── The ADRs ──────────────────────────────────────────────────────────────────

# ADR 0010 adopts OpenSpec, and two of its rejected options name OpenSpec too (#3258).
ADR_0010 = Adr(
    10,
    "OpenSpec is the spec and change proposal layer",
    "## Considered Options\n\n"
    "- **Adopt OpenSpec and delete the task files** (chosen): one planning format.\n"
    "- **Adopt OpenSpec beside the task files**: rejected. Two sources of truth.\n"
    "- **Keep the task files**: rejected. Planning stays a format every agent must learn.",
)


def test_an_adr_that_chose_the_tool_gives_no_rejected_verdict(
    store: InMemoryRoadmapStore,
) -> None:
    number = _item(store, "Plan each change as a spec delta")

    check = _check(
        store,
        number,
        _facts("https://github.com/Fission-AI/OpenSpec"),
        adrs=(ADR_0010,),
        adr=10,
        tool_name="OpenSpec",
    )

    assert (check.verdict, check.adr) == (Verdict.COVERS, None)


def _checked(
    store: InMemoryRoadmapStore, title: str, *, adr_hash: str | None, days: int = 2
) -> int:
    """An item that a check `days` ago recorded with `adr_hash`, its body unchanged since."""
    number = _item(store, title)
    item = store.item(number)
    assert item is not None
    store.set_marks(
        item,
        {
            AlternativesRecordKey.CHECKED_AT: (NOW - timedelta(days=days)).isoformat(),
            AlternativesRecordKey.BODY_HASH: alternatives.body_hash_of(item.body),
            AlternativesRecordKey.VERDICT: "partly",
            AlternativesRecordKey.ADR_HASH: adr_hash,
        },
    )
    return number


def test_an_item_whose_adr_hash_differs_from_the_adrs_at_head_is_checked_again(
    store: InMemoryRoadmapStore,
) -> None:
    """A check of an item of no skip class read the ADRs: when they changed since, or when the
    check recorded no hash, the item is due. A skip-class item reads no ADR, so a change of them
    leaves it alone."""
    current = _checked(store, "Scan a directory", adr_hash="new")
    changed = _checked(store, "Run durable jobs", adr_hash="old")
    unrecorded = _checked(store, "Watch the webhooks", adr_hash=None)
    skip_class = _checked(store, "docs(roadmap): explain the check", adr_hash=None)

    selection = select_items(
        store,
        item_number=None,
        limit=5,
        recheck_days=30,
        retry_days=3,
        now=NOW,
        adr_hash="new",
    )

    assert (
        [item.number for item in selection.selected],
        [item.number for item in selection.current],
    ) == ([changed, unrecorded], [current, skip_class])


# ── The census replay ─────────────────────────────────────────────────────────


def _census() -> dict[str, Any]:
    census: dict[str, Any] = json.loads(CENSUS.read_text(encoding="utf-8"))
    return census


def _project(url: str, census: dict[str, Any]) -> str | None:
    """The GitHub project of the tool at `url`: its own for a repository, else the one that the
    PyPI record of the package names, as the census recorded it."""
    return project_of(url) or census["pypi_projects"].get(url.rsplit("/", 1)[-1])


def test_the_tool_strings_of_the_census_map_to_at_most_81_canonical_ids() -> None:
    census = _census()

    ids = {canonical_id(tool["url"], _project(tool["url"], census)) for tool in census["tools"]}

    assert (len(census["tools"]), len(ids)) == (88, 81)


def test_the_census_tools_in_use_give_in_use_with_no_model_call(
    store: InMemoryRoadmapStore, web: WebFake, tmp_path: Path
) -> None:
    """At least 55 of the 58 tools in use give `in-use`. The two misses are a Go library inside
    Argo CD. The one tool that the census counted as new is in the SBOM at the recorded commit."""
    census = _census()
    store.seed_dependencies(*census["purls"])
    (tmp_path / "k8s").mkdir()
    (tmp_path / "k8s" / "words.txt").write_text(
        "\n".join(census["deployed_words"]), encoding="utf-8"
    )
    for project, packages in census["deps_dev"].items():
        _deps_dev(web, project, *map(tuple, packages))
    inventory = read_inventory(store, tmp_path, census["paths"])

    found = {
        item["number"]: inventory.uses(item["url"], _project(item["url"], census))
        for item in census["items"]
    }

    used = [item["number"] for item in census["items"] if item["used"]]
    new = [item["number"] for item in census["items"] if not item["used"]]
    assert (
        len(used),
        sum(found[number] for number in used) >= 55,
        [number for number in used if not found[number]],
        [number for number in new if found[number]],
    ) == (58, True, [1387, 2003], [3612])
