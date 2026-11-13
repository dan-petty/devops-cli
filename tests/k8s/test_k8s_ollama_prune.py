"""The prune of the Ollama models that no tier of a node serves (#3654).

The plan is pure: it reads the gateway routes, the tier Services, the Ollama pods of each node and
the `ollama list` of each node as text, so these tests run offline with no cluster.

The planner is imported inside each test, so this module still collects on the base commit, where
`devops_cli.k8s.ollama_prune` does not exist, and each test fails in its call phase there.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tests.support.k8s_tree import TREE

if TYPE_CHECKING:
    from devops_cli.k8s.ollama_prune import OllamaPod

_GATEWAY = """\
model_list:
  - model_name: devops-chat
    litellm_params:
      model: ollama_chat/qwen3.8:27b
      api_base: http://ollama-48gib-fast.llm.svc.cluster.local:11434
    model_info:
      max_input_tokens: 262144
  - model_name: devops-background
    litellm_params:
      model: ollama_chat/qwen3.8:27b
      api_base: http://ollama-64gib-standard.llm.svc.cluster.local:11434
    model_info:
      max_input_tokens: 262144
  - model_name: qwen3-embedding:0.6b
    litellm_params:
      model: ollama/qwen3-embedding:0.6b
      api_base: http://ollama-24gib-embed-gpu0.llm.svc.cluster.local:11434
    model_info:
      mode: embedding
  - model_name: gemini-3.8-flash
    litellm_params:
      model: gemini/gemini-3.8-flash
      api_key: os.environ/GEMINI_API_KEY
    model_info:
      max_input_tokens: 1048576
"""

_SERVICES = """\
apiVersion: v1
kind: Service
metadata:
  name: ollama-48gib-fast
  namespace: llm
spec:
  selector:
    llm.devops.io/provider: ollama
    llm.devops.io/vram-gib: 48gib
    llm.devops.io/speed-tier: fast
---
apiVersion: v1
kind: Service
metadata:
  name: ollama-64gib-standard
  namespace: llm
spec:
  selector:
    llm.devops.io/provider: ollama
    llm.devops.io/vram-gib: 64gib
    llm.devops.io/speed-tier: standard
---
apiVersion: v1
kind: Service
metadata:
  name: ollama-24gib-embed-gpu0
  namespace: llm
spec:
  selector:
    llm.devops.io/provider: ollama
    llm.devops.io/vram-gib: 24gib
    llm.devops.io/speed-tier: embed
    llm.devops.io/gpu-instance: "0"
---
apiVersion: v1
kind: Service
metadata:
  name: ollama-fast
  namespace: llm
spec:
  selector:
    llm.devops.io/provider: ollama
    llm.devops.io/speed-tier: fast
"""

_FAST_LABELS = {
    "llm.devops.io/provider": "ollama",
    "llm.devops.io/vram-gib": "48gib",
    "llm.devops.io/speed-tier": "fast",
}
_STANDARD_LABELS = {
    "llm.devops.io/provider": "ollama",
    "llm.devops.io/vram-gib": "64gib",
    "llm.devops.io/speed-tier": "standard",
}
_EMBED_LABELS = {
    "llm.devops.io/provider": "ollama",
    "llm.devops.io/vram-gib": "24gib",
    "llm.devops.io/speed-tier": "embed",
    "llm.devops.io/gpu-instance": "0",
}

_HEADER = "NAME                       ID              SIZE      MODIFIED\n"
_SHARED_LIST = _HEADER + (
    "qwen3.8:27b                7d5f8b3c4e2a    17 GB     2 days ago\n"
    "llama3.1:70b               b1c2d3e4f5a6    39 GB     6 days ago\n"
)
_EMBED_LIST = _HEADER + (
    "qwen3-embedding:0.6b       a1b2c3d4e5f6    639 MB    3 days ago\n"
    "qwen3.8:27b                7d5f8b3c4e2a    17 GB     2 days ago\n"
    "nomic-embed-text:latest    c1d2e3f4a5b6    274 MB    8 days ago\n"
)


def _pod(name: str, node: str, labels: dict[str, str]) -> OllamaPod:
    """One Ollama pod of the stack, built from the planner that this module tests."""
    from devops_cli.k8s.ollama_prune import OllamaPod

    return OllamaPod(name=name, node=node, labels=labels)


def test_a_node_keeps_the_models_of_its_tiers() -> None:
    """A node keeps one copy of each model that the gateway sends to a tier that runs on it, and
    the prune removes the other models of its list."""
    from devops_cli.k8s.ollama_prune import NodePrune, plan_ollama_prune

    plan = plan_ollama_prune(
        _GATEWAY,
        _SERVICES,
        [
            _pod("ollama-48gib-fast-abcde", "node-shared", _FAST_LABELS),
            _pod("ollama-64gib-standard-fghij", "node-shared", _STANDARD_LABELS),
            _pod("ollama-24gib-embed-gpu0-klmno", "node-embed", _EMBED_LABELS),
            _pod("ollama-48gib-fast-pqrst", "node-failed", _FAST_LABELS),
        ],
        {"node-shared": _SHARED_LIST, "node-embed": _EMBED_LIST, "node-failed": None},
    )

    assert plan == (
        NodePrune(
            node="node-embed",
            keep=("qwen3-embedding:0.6b",),
            remove=("nomic-embed-text:latest", "qwen3.8:27b"),
            list_failed=False,
        ),
        NodePrune(
            node="node-failed",
            keep=("qwen3.8:27b",),
            remove=(),
            list_failed=True,
        ),
        NodePrune(
            node="node-shared",
            keep=("qwen3.8:27b",),
            remove=("llama3.1:70b",),
            list_failed=False,
        ),
    )


def test_a_missing_ollama_list_keeps_every_model_and_names_the_node() -> None:
    """A node whose list was not read removes nothing, so an unreadable list never empties a store."""
    from devops_cli.k8s.ollama_prune import NodePrune, plan_ollama_prune

    (entry,) = plan_ollama_prune(
        _GATEWAY,
        _SERVICES,
        [_pod("ollama-48gib-fast-pqrst", "node-failed", _FAST_LABELS)],
        {},
    )

    assert entry == NodePrune(
        node="node-failed",
        keep=("qwen3.8:27b",),
        remove=(),
        list_failed=True,
    )


def test_the_gateway_targets_name_the_models_of_each_api_base() -> None:
    """The target is the Service of the `api_base` host, the model is the Ollama model behind the
    LiteLLM provider prefix, and a hosted deployment names no target."""
    from devops_cli.k8s.ollama_prune import gateway_targets

    assert gateway_targets(_GATEWAY) == {
        "ollama-48gib-fast": frozenset({"qwen3.8:27b"}),
        "ollama-64gib-standard": frozenset({"qwen3.8:27b"}),
        "ollama-24gib-embed-gpu0": frozenset({"qwen3-embedding:0.6b"}),
    }


def test_the_service_selectors_name_the_selector_of_each_service() -> None:
    """A pod matches a Service when its labels hold every pair of the selector, so the plan reads
    the selector of each Service of the stack, aliases included."""
    from devops_cli.k8s.ollama_prune import service_selectors

    assert service_selectors(_SERVICES) == {
        "ollama-48gib-fast": {
            "llm.devops.io/provider": "ollama",
            "llm.devops.io/vram-gib": "48gib",
            "llm.devops.io/speed-tier": "fast",
        },
        "ollama-64gib-standard": {
            "llm.devops.io/provider": "ollama",
            "llm.devops.io/vram-gib": "64gib",
            "llm.devops.io/speed-tier": "standard",
        },
        "ollama-24gib-embed-gpu0": {
            "llm.devops.io/provider": "ollama",
            "llm.devops.io/vram-gib": "24gib",
            "llm.devops.io/speed-tier": "embed",
            "llm.devops.io/gpu-instance": "0",
        },
        "ollama-fast": {
            "llm.devops.io/provider": "ollama",
            "llm.devops.io/speed-tier": "fast",
        },
    }


def test_an_ollama_list_names_each_model_once() -> None:
    """The first column of each row is the model, and the header names the columns."""
    from devops_cli.k8s.ollama_prune import parse_ollama_list

    assert (
        parse_ollama_list(_SHARED_LIST),
        parse_ollama_list(_HEADER),
    ) == (
        frozenset({"qwen3.8:27b", "llama3.1:70b"}),
        frozenset(),
    )


def test_the_tracked_gateway_routes_name_a_service_of_the_stack() -> None:
    """Each target of the tracked gateway config is a Service of the tracked stack, and the keep
    set of each is the model that its tiers load."""
    from devops_cli.k8s.ollama_prune import gateway_targets, service_selectors

    gateway = TREE.gateway_config.read_text(encoding="utf-8")
    services = TREE.llm_services.read_text(encoding="utf-8")

    assert gateway_targets(gateway) == {
        "ollama-24gib-embed-gpu0": frozenset({"qwen3-embedding:0.6b"}),
        "ollama-24gib-embed-gpu1": frozenset({"qwen3-embedding:0.6b"}),
        "ollama-48gib-fast": frozenset({"qwen3.8:27b"}),
        "ollama-64gib-standard": frozenset({"qwen3.8:27b"}),
    }
    assert set(gateway_targets(gateway)) <= set(service_selectors(services))
