"""The shortlist of nearest items that intake shows the model, and the embeddings it asks for
(#1335).
"""

from __future__ import annotations

import json

import httpx2
import pytest
from fakeredis import FakeServer

from devops_cli.ai.rag.embeddings import EmbeddingsEngine
from devops_cli.config.settings import AIConfig
from devops_cli.roadmap.intake.intake import (
    Outcome,
    plan_intake,
)
from devops_cli.roadmap.intake.intake_model import (
    GatewayIntakeModel,
    ModelProposal,
)
from tests.support.fakes.http import WebFake
from tests.support.fakes.valkey import valkey_client_on
from tests.support.roadmap_intake import DEFAULT_PROPOSAL, REPO, FakeModel, Roadmap


def test_with_no_candidates_intake_embeds_nothing_and_asks_the_model_nothing(
    roadmap: Roadmap,
) -> None:
    roadmap.finished("done")
    model = FakeModel()
    plan = roadmap.plan(model)
    assert (model.embedded, model.requests, plan.has_writes) == ([], [], False)


def test_the_model_judges_only_the_five_nearest_items(roadmap: Roadmap) -> None:
    for title in ("csv one", "csv two", "csv three", "csv four", "csv five", "other", "else"):
        roadmap.finished(title)
    roadmap.issue("export csv")
    model = FakeModel(topics=("csv",))
    roadmap.plan(model)
    (request,) = model.requests
    assert sorted(n.title for n in request.shortlist) == sorted(
        ("csv one", "csv two", "csv three", "csv four", "csv five")
    )


# ── The embeddings of settled items (#1655) ───────────────────────────────────


class _Proposer:
    """The `analysis` model: the same proposal for each candidate."""

    def chat_structured(
        self, system: str, prompt: str, schema: type[ModelProposal]
    ) -> ModelProposal:
        return schema.model_validate(DEFAULT_PROPOSAL)


def _embeddings_server(request: httpx2.Request) -> httpx2.Response | None:
    """The gateway's OpenAI-compatible `/v1/embeddings`: one vector for each text."""
    if request.url.path != "/v1/embeddings":
        return None
    texts = json.loads(request.content)["input"]
    vectors = [{"index": i, "embedding": [1.0, float(len(t) % 7)]} for i, t in enumerate(texts)]
    return httpx2.Response(200, json={"data": vectors, "usage": {"prompt_tokens": len(texts)}})


@pytest.mark.parametrize(
    ("cached", "embedding_requests"),
    [pytest.param(True, [1, 0], id="valkey-cache"), pytest.param(False, [1, 1], id="no-cache")],
)
def test_a_second_intake_run_over_settled_items_sends_no_embedding_request_with_the_valkey_cache(
    roadmap: Roadmap,
    web: WebFake,
    valkey_server: FakeServer,
    cached: bool,
    embedding_requests: list[int],
) -> None:
    """Each run is a new process with an empty memory cache, as each round of the Service and
    each cluster job is. With the shared Valkey cache, a second run over the same items and the
    same candidate sends no embedding request. With no cache it embeds them all again (#1655)."""
    web.serve(_embeddings_server)
    roadmap.finished("Retry policy for the gateway")
    roadmap.finished("Dashboard for the gateway")
    roadmap.issue("feat: cache the embeddings")
    ai = AIConfig(provider="gateway", gateway_url="https://example.com/v1")
    sent: list[int] = []
    for _run in range(2):
        before = len(web.sent)
        valkey = valkey_client_on(valkey_server) if cached else None
        engine = EmbeddingsEngine(ai, api_key="sk-test", valkey_client=valkey)
        model = GatewayIntakeModel(ai, embedder=engine, client=_Proposer())
        plan = plan_intake(roadmap.store, repo=REPO, model=model)
        sent.append(sum(1 for r in web.sent[before:] if r.url.path == "/v1/embeddings"))

    assert (sent, [d.outcome for d in plan.decisions]) == (embedding_requests, [Outcome.PLACE])


@pytest.mark.usefixtures("keyring_store")
def test_a_second_intake_run_reads_the_embeddings_from_the_data_directory(
    roadmap: Roadmap, web: WebFake
) -> None:
    """Each run builds its own embedder, as each CLI run does. The configured Valkey refuses
    each connection, as on a workstation, so only the disk cache under the data directory holds
    the vectors of the first run (#4447)."""
    web.serve(_embeddings_server)
    roadmap.finished("Retry policy for the gateway")
    roadmap.finished("Dashboard for the gateway")
    roadmap.issue("feat: cache the embeddings")
    ai = AIConfig(provider="gateway", gateway_url="https://example.com/v1")
    sent: list[int] = []
    for _run in range(2):
        before = len(web.sent)
        model = GatewayIntakeModel(ai, api_key="sk-test", client=_Proposer())
        plan = plan_intake(roadmap.store, repo=REPO, model=model)
        sent.append(sum(1 for r in web.sent[before:] if r.url.path == "/v1/embeddings"))

    assert (sent, [d.outcome for d in plan.decisions]) == ([1, 0], [Outcome.PLACE])
