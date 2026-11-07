"""The keep set that the GPU Placement table of `k8s/README.md` writes for each gateway target (#3654).

The gateway config is the record of which model each Ollama tier is sent, so the table of the
document and the `api_base` targets of the config must name the same models.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

import yaml

from tests.support.markdown_examples import tables
from tests.support.paths import REPO_ROOT

K8S_README = REPO_ROOT / "k8s" / "README.md"
GATEWAY_CONFIG = REPO_ROOT / "k8s" / "llm" / "gateway" / "config.yaml"
# The subsection of k8s/README.md that describes the tiers and the models they keep.
GPU_PLACEMENT = "### GPU Placement: Ollama tiers"
TARGET_COLUMN = "Gateway target"
MODELS_COLUMN = "Models it keeps"


def _keep_set_rows() -> list[list[str]]:
    """The rows of the keep-set table, the header first."""
    found = [rows for rows in tables(K8S_README) if rows[0][:1] == [TARGET_COLUMN]]
    assert len(found) == 1, (
        f"k8s/README.md must hold one {TARGET_COLUMN!r} table, found {len(found)}"
    )
    return found[0]


def _written_keep_set() -> dict[str, set[str]]:
    """The models that the table writes for each gateway target."""
    header, *rows = _keep_set_rows()
    target = header.index(TARGET_COLUMN)
    models = header.index(MODELS_COLUMN)
    return {
        row[target].strip("`"): {name.strip().strip("`") for name in row[models].split(",")}
        for row in rows
    }


def _gateway_keep_set() -> dict[str, set[str]]:
    """The models that the gateway config sends to each target, by Service name."""
    config: dict[str, Any] = yaml.safe_load(GATEWAY_CONFIG.read_text(encoding="utf-8"))
    keep: dict[str, set[str]] = {}
    for deployment in config["model_list"]:
        params = deployment["litellm_params"]
        if not (api_base := params.get("api_base")):
            continue
        target = (urlsplit(api_base).hostname or "").split(".")[0]
        keep.setdefault(target, set()).add(params["model"].partition("/")[2])
    return keep


def test_the_table_writes_the_keep_set_of_each_gateway_target() -> None:
    """Each model that the gateway config sends to a target is in the table, and the table names
    no other model, so a changed route fails here with the target and the model."""
    written = _written_keep_set()
    config = _gateway_keep_set()
    differences = [
        f"{target}: {model}"
        for target in sorted(written.keys() | config.keys())
        for model in sorted(written.get(target, set()) ^ config.get(target, set()))
    ]

    assert differences == []


def test_the_table_names_each_gateway_target_once() -> None:
    """One row for each target, so a second row cannot keep a model that the gateway drops."""
    _, *rows = _keep_set_rows()
    targets = [row[0].strip("`") for row in rows]

    assert len(targets) == len(set(targets))


def test_the_keep_set_table_sits_under_gpu_placement() -> None:
    """A person reads the keep set where the tiers that it describes are placed."""
    readme = K8S_README.read_text(encoding="utf-8")
    section = readme.split(GPU_PLACEMENT, 1)[1].split("\n## ", 1)[0]

    assert f"| {TARGET_COLUMN} |" in section
