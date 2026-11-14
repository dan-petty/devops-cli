"""The roadmap Service uses its own gateway key, not the master key (#3685).

The Deployment reads `DEVOPS_CLI_AI_API_KEY` from Secret `roadmap-service-llm-key`, and every
other variable of the shared Secret has an explicit `secretKeyRef`, so the Service holds no
reference to the gateway master key.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from devops_cli.k8s.cluster_secrets import CLUSTER_SECRETS

DEPLOYMENT = Path("k8s/devops/roadmap-service/deployment.yaml")

REQUIRED = (
    "DEVOPS_CLI_SERVICE_GITHUB_APP_PRIVATE_KEY",
    "DEVOPS_CLI_SERVICE_WEBHOOK_SECRETS",
)
OPTIONAL = (
    "DEVOPS_CLI_FIRECRAWL_API_KEY",
    "DEVOPS_CLI_VALKEY_PASSWORD",
    "DEVOPS_CLI_MATTERMOST_COMMAND_TOKEN",
    "DEVOPS_CLI_CRAWL4AI_API_TOKEN",
)


def _pod_template() -> dict[str, Any]:
    manifest = yaml.safe_load(DEPLOYMENT.read_text(encoding="utf-8"))
    return manifest["spec"]["template"]["spec"]


def _environment() -> dict[str, dict[str, Any]]:
    (container,) = _pod_template()["containers"]
    return {entry["name"]: entry for entry in container["env"]}


def test_the_service_reads_its_own_virtual_key() -> None:
    reference = _environment()["DEVOPS_CLI_AI_API_KEY"]["valueFrom"]["secretKeyRef"]

    assert (reference["name"], reference["key"]) == ("roadmap-service-llm-key", "api-key")


def test_the_pod_template_loads_no_shared_secret() -> None:
    assert "envFrom" not in _pod_template()


def test_each_other_variable_names_its_key_of_the_shared_secret() -> None:
    environment = _environment()

    references = {
        name: environment[name]["valueFrom"]["secretKeyRef"] for name in (*REQUIRED, *OPTIONAL)
    }

    assert {name: reference["name"] for name, reference in references.items()} == {
        name: "devops-cli" for name in (*REQUIRED, *OPTIONAL)
    }
    assert {references[name].get("optional", False) for name in OPTIONAL} == {True}
    assert {references[name].get("optional", False) for name in REQUIRED} == {False}


def test_the_key_has_an_optional_cluster_secret_row() -> None:
    row = next(
        secret for secret in CLUSTER_SECRETS if secret.ref == "devops/roadmap-service-llm-key"
    )
    (entry,) = row.entries

    assert (entry.key, entry.required) == ("api-key", False)
