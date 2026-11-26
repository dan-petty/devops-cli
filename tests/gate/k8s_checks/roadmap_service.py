"""The webhook ingresses of the roadmap service (#2164)."""

from __future__ import annotations

from typing import Any

from tests.gate.k8s_render import applied_documents
from tests.support.paths import REPO_ROOT

DEVOPS_DIR = REPO_ROOT / "k8s" / "devops"


ROADMAP_SERVICE_DIR = DEVOPS_DIR / "roadmap-service"


# The Traefik annotation of an Ingress that names the Middlewares of its routes.
MIDDLEWARES_ANNOTATION = "traefik.ingress.kubernetes.io/router.middlewares"


def _roadmap_ingress(documents: list[dict[str, Any]]) -> dict[str, Any]:
    """The Ingress `devops/roadmap-service` among the objects that one apply sends."""
    (ingress,) = [
        document
        for document in documents
        if document.get("kind") == "Ingress"
        and document["metadata"]["name"] == "roadmap-service"
        and document["metadata"]["namespace"] == "devops"
    ]
    return ingress


def check_each_webhook_ingress_names_the_rate_limit_that_the_devops_stack_renders() -> None:
    """Traefik limits the deliveries of the webhook route (#2476). Argo CD renders the Middleware
    and the Ingress from the product base `k8s/devops`. deploy-stack applies the Ingress from
    `roadmap-service/ingress.yaml`, the one file that holds it (#5292), and each names the
    Middleware, so no apply removes the limit. The limit keeps one bucket for each client, keyed
    on the `Cf-Connecting-Ip` that the Cloudflare edge sets, so another sender cannot use up the
    bucket of GitHub's deliveries (#5035). The request host and the remote address (a cloudflared
    pod) are the same for each sender."""
    rendered = applied_documents(DEVOPS_DIR)
    applies = [
        rendered,
        applied_documents(ROADMAP_SERVICE_DIR / "ingress.yaml"),
    ]
    middlewares = {
        (document["metadata"]["namespace"], document["metadata"]["name"]): (
            document["apiVersion"],
            document["spec"],
        )
        for document in rendered
        if document.get("kind") == "Middleware"
    }
    assert (
        [
            _roadmap_ingress(documents)["metadata"]["annotations"].get(MIDDLEWARES_ANNOTATION)
            for documents in applies
        ],
        middlewares,
    ) == (
        ["devops-roadmap-service-rate-limit@kubernetescrd"] * 2,
        {
            ("devops", "roadmap-service-rate-limit"): (
                "traefik.io/v1alpha1",
                {
                    "rateLimit": {
                        "average": 60,
                        "period": "1m",
                        "burst": 60,
                        "sourceCriterion": {"requestHeaderName": "Cf-Connecting-Ip"},
                    }
                },
            )
        },
    )
