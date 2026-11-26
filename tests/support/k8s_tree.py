"""The inputs of `devops ai gateway render` that a test writes into an environment tree (#7290).

devops-cli ships no environment tree, so a test builds the one that its command reads.
`tests.support.k8s_commands.write_environment_tree` writes a whole tree. The render also reads the
GPU architecture thresholds, a tier template and the marker lines of the regions that it writes,
which `write_gateway_render_inputs` adds.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

_REGION: Final[str] = (
    "# BEGIN rendered by devops ai gateway render from gpu-thresholds.yaml\n"
    "# END rendered by devops ai gateway render from gpu-thresholds.yaml\n"
)

_GATEWAY_CONFIG: Final[str] = (
    "model_list:\n"
    "  - model_name: example-chat\n"
    "    litellm_params:\n"
    "      model: ollama_chat/qwen3.8:27b\n"
    "      api_base: http://ollama-48gib-fast.llm.svc.cluster.local:11434\n"
    + "".join(f"  {line}\n" for line in _REGION.splitlines())
    + "router_settings:\n"
    "  routing_strategy: least-busy\n"
)

# Both thresholds are older than the architecture of the one tier template, so the render keeps
# the tier as it is: one DaemonSet and its Service, and no embedding route.
_THRESHOLDS: Final[str] = "embedding_only: kepler\nper_gpu: kepler\n"

_TIER_TEMPLATE: Final[str] = """\
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: ollama-16gib-fast
  namespace: llm
  labels:
    llm.devops.io/provider: ollama
    llm.devops.io/vram-gib: 16gib
    llm.devops.io/speed-tier: fast
spec:
  selector:
    matchLabels:
      app.kubernetes.io/name: ollama-16gib-fast
  template:
    metadata:
      labels:
        llm.devops.io/provider: ollama
        llm.devops.io/vram-gib: 16gib
        llm.devops.io/speed-tier: fast
    spec:
      affinity:
        nodeAffinity:
          requiredDuringSchedulingIgnoredDuringExecution:
            nodeSelectorTerms:
              - matchExpressions:
                  - key: nvidia.com/gpu.architecture
                    operator: In
                    values: ["pascal"]
      containers:
        - name: ollama
          env: []
"""


def write_gateway_render_inputs(tree: Path) -> None:
    """Write into the environment tree `tree` each file that the gateway render reads."""
    files = {
        "llm/gateway/config.yaml": _GATEWAY_CONFIG,
        "llm/profiles/ollama-profiles.yaml": f"---\n{_REGION}",
        "llm/profiles/services.yaml": f"---\n{_REGION}",
        "llm/profiles/gpu-thresholds.yaml": _THRESHOLDS,
        "llm/profiles/tier-templates/ollama-16gib-fast.yaml": _TIER_TEMPLATE,
    }
    for name, text in files.items():
        path = tree / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
