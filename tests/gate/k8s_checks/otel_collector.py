"""The trace pipeline of the OpenTelemetry Collector deletes gateway key data (#4518)."""

from __future__ import annotations

import copy
import hashlib
import re
from typing import Any

import yaml

from tests.gate.k8s_render import applied_documents
from tests.support.paths import REPO_ROOT

K8S_DIR = REPO_ROOT / "k8s"


COLLECTOR_VALUES = K8S_DIR / "otel" / "values.yaml"


# A SHA-256 hash, the form in which LiteLLM writes an API key on a span. No gateway has this key.
KEY_HASH = hashlib.sha256(b"sk-example").hexdigest()


# The attributes that the LiteLLM `otel` callback of v1.103.10 writes with key data. `set_attributes`
# in litellm/integrations/opentelemetry.py writes each key of `StandardLoggingMetadata`
# (litellm/types/utils.py) as `metadata.<key>`, also with message logging off. A refused key puts
# its hash in the error text (litellm/proxy/auth/user_api_key_auth.py), which goes to the
# `exception` attribute and to the exception event. The header names are the OpenTelemetry form
# of a request header, which an HTTP server instrumentation writes when it captures headers.
GATEWAY_KEY_ATTRIBUTES: dict[str, Any] = {
    "metadata.user_api_key_hash": KEY_HASH,
    "metadata.user_api_key_alias": "devops-cli",
    "metadata.user_api_key_user_id": "default_user_id",
    "metadata.user_api_key_user_email": "user@example.com",
    "metadata.user_api_key_team_id": "team-1",
    "metadata.user_api_key_org_id": "org-1",
    "metadata.user_api_key_end_user_id": "roadmap-service",
    "metadata.user_api_key_request_route": "/chat/completions",
    "metadata.user_api_key_spend": 1.5,
    "metadata.user_api_key_auth_metadata": '{"source": "example"}',
    "metadata.requester_custom_headers": '{"x-litellm-end-user-id": "roadmap-service"}',
    "http.request.header.authorization": "Bearer sk-example",
    "http.request.header.x-api-key": "sk-example",
}


# The attributes of a gateway span that a trace needs: the model, the route, the tokens and the
# error class. The error text stays, without the key hash.
GATEWAY_KEPT_ATTRIBUTES: dict[str, Any] = {
    "gen_ai.request.model": "deepseek-v4.1-flash-1017",
    "gen_ai.usage.input_tokens": 3045,
    "http.route": "/chat/completions",
    "litellm.model_group": "devops-chat",
    "metadata.user_agent": "OpenAI/Python 2.8.1",
    "metadata.team_id": "team-1",
    "error.type": "AuthenticationError",
    "exception": f"Authentication Error, Invalid proxy server token passed. Received API Key = "
    f"sk-...mple, Key Hash (Token) ={KEY_HASH}. Unable to find token in cache",
}


# Attributes of devops-cli spans. A 64-digit hex value there is a content digest, not a key.
OTHER_SERVICE_ATTRIBUTES: dict[str, Any] = {
    "vcs.commit": "0123456789abcdef0123456789abcdef01234567",
    "review.digest": KEY_HASH,
    "gen_ai.provider.name": "gateway",
}


# One OTTL statement: a function on the attributes of a context, then an optional condition.
_STATEMENT = re.compile(
    r"(?P<function>\w+)\((?P<target>(?P<context>span|spanevent)\.attributes), (?P<args>.*)\)"
    r"(?: where (?P<where>.+))?"
)


_STRING = re.compile(r'"((?:[^"\\]|\\.)*)"')


_SERVICE_CONDITION = re.compile(r'resource\.attributes\["service\.name"\] == "(?P<name>[^"]+)"')


def _literals(args: str) -> list[str]:
    """The OTTL string literals of an argument list, with their escapes undone."""
    return [re.sub(r"\\(.)", r"\1", literal) for literal in _STRING.findall(args)]


def _applies(where: str | None, service: str, statement: str) -> bool:
    """Whether a statement's condition holds for a span of this service."""
    if where is None:
        return True
    condition = _SERVICE_CONDITION.fullmatch(where)
    assert condition is not None, f"the check does not read the condition of: {statement}"
    return condition["name"] == service


def _run(statement: str, context: str, service: str, attributes: dict[str, Any]) -> None:
    """Apply one OTTL statement to the attributes of a span or an event, as the Collector does.

    The check reads the two functions of the key rule only, and fails on any other statement, so
    a statement that it cannot read never passes as a statement that deletes nothing.
    """
    parsed = _STATEMENT.fullmatch(statement)
    assert parsed is not None, f"the check does not read: {statement}"
    if parsed["context"] != context or not _applies(parsed["where"], service, statement):
        return
    literals = _literals(parsed["args"])
    if parsed["function"] == "delete_matching_keys":
        (pattern,) = literals
        for key in [key for key in attributes if re.search(pattern, key)]:
            del attributes[key]
    elif parsed["function"] == "replace_all_patterns" and literals[0] == "value":
        _, pattern, replacement = literals
        for key, value in attributes.items():
            if isinstance(value, str):
                attributes[key] = re.sub(pattern, replacement, value)
    else:
        raise AssertionError(f"the check does not read: {statement}")


def _trace_pipeline(values: dict[str, Any]) -> tuple[list[str], list[dict[str, Any]]]:
    """The processors of the traces pipeline, and the trace statement groups of its `transform`
    processors in pipeline order."""
    config = values["config"]
    processors = config["service"]["pipelines"]["traces"]["processors"]
    groups = [
        group
        for name in processors
        if name.split("/")[0] == "transform"
        for group in config["processors"][name].get("trace_statements", [])
    ]
    return processors, groups


def _export(
    groups: list[dict[str, Any]], service: str, span: dict[str, Any], event: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    """The attributes of a span and of its one event after the transform processors."""
    span, event = copy.deepcopy(span), copy.deepcopy(event)
    for group in groups:
        context = group["context"]
        for statement in group["statements"]:
            _run(statement, context, service, span if context == "span" else event)
    return span, event


def _gateway_service_name() -> str:
    """`OTEL_SERVICE_NAME` of the gateway Deployment, the `service.name` of its spans."""
    (deployment,) = [
        document
        for document in applied_documents(K8S_DIR / "llm" / "gateway")
        if document["kind"] == "Deployment" and document["metadata"]["name"] == "llm-gateway"
    ]
    env = {
        variable["name"]: variable.get("value")
        for container in deployment["spec"]["template"]["spec"]["containers"]
        for variable in container.get("env", [])
    }
    return env.get("OTEL_SERVICE_NAME", "litellm")


def check_the_trace_pipeline_deletes_gateway_key_data_before_tempo() -> None:
    """The LiteLLM `otel` callback writes the key hash, the key alias, the user and the custom
    request headers on each span, also with message logging off. A `transform` processor of the
    traces pipeline deletes them, and the key hash in the error text of a span and its event,
    before the Tempo exporter (#4518). It runs after `memory_limiter` and before `batch`, and it
    keeps the other attributes of gateway spans and the attributes of devops-cli spans."""
    values = yaml.safe_load(COLLECTOR_VALUES.read_text(encoding="utf-8"))
    processors, groups = _trace_pipeline(values)
    transforms = [name for name in processors if name.split("/")[0] == "transform"]
    gateway = _gateway_service_name()
    gateway_span = {**GATEWAY_KEY_ATTRIBUTES, **GATEWAY_KEPT_ATTRIBUTES}
    gateway_event = {
        "exception.type": "ProxyException",
        "exception.message": GATEWAY_KEPT_ATTRIBUTES["exception"],
        "http.request.header.authorization": "Bearer sk-example",
    }
    span, event = _export(groups, gateway, gateway_span, gateway_event)
    other_span, other_event = _export(
        groups, "devops-cli", OTHER_SERVICE_ATTRIBUTES, {"exception.message": KEY_HASH}
    )

    assert (
        bool(transforms),
        all(
            processors.index("memory_limiter") < processors.index(name) < processors.index("batch")
            for name in transforms
        ),
        sorted(span),
        sorted(event),
        KEY_HASH in str(span) or KEY_HASH in str(event),
        (other_span, other_event),
    ) == (
        True,
        True,
        sorted(GATEWAY_KEPT_ATTRIBUTES),
        ["exception.message", "exception.type"],
        False,
        (OTHER_SERVICE_ATTRIBUTES, {"exception.message": KEY_HASH}),
    )
