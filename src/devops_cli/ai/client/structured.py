"""Structured output and JSON schema repair mixin for unified AI client."""

from __future__ import annotations

import json
import logging
import re
import time
from collections.abc import Callable
from typing import Any, TypeVar

import json_repair
from pydantic import BaseModel, TypeAdapter, ValidationError

from devops_cli.ai.client.models import (
    LLMResponse,
    ReplyRejectedError,
    StructuredOutputValidationError,
    genai_provider_name,
)
from devops_cli.ai.client.network import ReplySchema, constrain_reply
from devops_cli.ai.schema_reflection import (
    SchemaReflectionReport,
    extract_schema_reflection,
)
from devops_cli.ai.task_loader import load_task_prompt
from devops_cli.ai.thinking_stream import strip_think_blocks
from devops_cli.config.constants import (
    CONST_MAX_ERROR_DETAIL_LENGTH,
    CONST_METRIC_AI_STRUCTURED_REPAIR_SUCCESS,
    CONST_METRIC_AI_STRUCTURED_RETRY_COUNT,
    CONST_METRIC_AI_STRUCTURED_SUCCESS,
    CONST_METRIC_AI_STRUCTURED_VALIDATION_FAILURE,
)
from devops_cli.config.defaults import (
    DEFAULT_STRUCTURED_OUTPUT_MAX_RETRIES,
    DEFAULT_STRUCTURED_RETRY_BACKOFF_SECONDS,
)
from devops_cli.config.settings import AIConfig
from devops_cli.exceptions.ai import StructuredOutputSchemaError
from devops_cli.models.ai import ChatMessage
from devops_cli.telemetry import record_metric, trace_span

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

# Why a reply failed: the schema's report when it held JSON that broke the schema, else a sentence
# saying why no JSON was read from it.
SchemaFailure = SchemaReflectionReport | str

__all__ = [
    "StructuredOutputMixin",
    "_build_reflection_message",
    "_extract_candidate_json",
    "_parse_json_payload",
    "_prepare_structured_messages",
    "_repair_and_validate_payload",
    "_validate_schema_payload",
]


def _extract_candidate_json(raw_text: str) -> str:
    """Extract candidate JSON substring by removing thinking blocks and markdown fences."""
    cleaned = strip_think_blocks(raw_text).strip()
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", cleaned)
    if match:
        return match.group(1).strip()
    return cleaned


def _parse_json_payload(candidate: str, cleaned: str) -> tuple[Any, bool, str | None]:
    """Parse candidate string to JSON object or array, repairing malformed syntax if needed."""
    try:
        return json.loads(candidate), False, None
    except Exception:
        pass

    try:
        repaired = json_repair.loads(candidate)
        if repaired != "" and repaired is not None and isinstance(repaired, (dict, list)):
            return repaired, True, None
        repaired_full = json_repair.loads(cleaned)
        if (
            repaired_full != ""
            and repaired_full is not None
            and isinstance(repaired_full, (dict, list))
        ):
            return repaired_full, True, None
        return None, False, "Model response does not contain a valid JSON object or array."
    except Exception as exc:
        err = str(exc)
        if len(err) > CONST_MAX_ERROR_DETAIL_LENGTH:
            err = err[: CONST_MAX_ERROR_DETAIL_LENGTH - 3] + "..."
        return None, False, f"JSON repair failed: {err}"


def _validate_schema_payload[T: BaseModel](
    json_data: Any,
    schema: type[T],
) -> tuple[T | None, SchemaFailure | None]:
    """Validate parsed JSON data against Pydantic schema with lossless structured reflection."""
    try:
        if hasattr(schema, "model_validate"):
            return schema.model_validate(json_data), None
        return TypeAdapter(schema).validate_python(json_data), None
    except ValidationError as exc:
        return None, extract_schema_reflection(exc, max_errors=exc.error_count())
    except Exception as exc:
        err_msg = str(exc)
        if len(err_msg) > CONST_MAX_ERROR_DETAIL_LENGTH:
            err_msg = err_msg[: CONST_MAX_ERROR_DETAIL_LENGTH - 3] + "..."
        return None, f"Schema validation error: {err_msg}"


def _repair_and_validate_payload[T: BaseModel](
    raw_text: str,
    schema: type[T],
) -> tuple[T | None, bool, SchemaFailure | None]:
    """Extract, repair, and validate raw model text against target schema."""
    cleaned = strip_think_blocks(raw_text).strip()
    candidate = _extract_candidate_json(raw_text)
    json_data, was_repaired, parse_err = _parse_json_payload(candidate, cleaned)
    if parse_err is not None or json_data is None:
        return None, was_repaired, parse_err

    model_inst, schema_err = _validate_schema_payload(json_data, schema)
    if schema_err is not None:
        return None, was_repaired, schema_err

    return model_inst, was_repaired, None


def _failure_summary(failure: SchemaFailure) -> str:
    """What the last reply's failure was, holding none of the reply: its violation count and their
    pydantic error types, never a field path, since a path can be a key the model invented."""
    if isinstance(failure, SchemaReflectionReport):
        types = ", ".join(sorted({violation.error_type for violation in failure.violations}))
        return f"{failure.total_errors} schema violation(s) ({types})"
    return "no JSON object the schema could validate"


def _validation_failure(
    model_name: str, attempts: int, failure: SchemaFailure
) -> StructuredOutputValidationError:
    """The error for a call whose every reply failed, counting the last one's violations.

    Its message reaches spans, logs and intake's skip reason, so it carries no model text; the
    full report went to the model in the reflection prompt.
    """
    violations = failure.total_errors if isinstance(failure, SchemaReflectionReport) else 0
    return StructuredOutputValidationError(
        f"Response validation failed for model '{model_name}' after {attempts} attempts: "
        f"the last reply had {_failure_summary(failure)}.",
        violations=violations,
    )


def _with_reply_schema(system: str, json_schema: dict[str, Any]) -> str:
    """The caller's system prompt, then the instruction to answer with one JSON object that
    validates against `json_schema`, then that schema."""
    instruction = load_task_prompt("structured_output_schema.md")
    parts = (system, instruction, json.dumps(json_schema, ensure_ascii=False))
    return "\n\n".join(part for part in parts if part)


def _build_reflection_message(error_details: str | SchemaReflectionReport) -> ChatMessage:
    """Construct dynamic error reflection prompt to guide model self-repair."""
    if isinstance(error_details, SchemaReflectionReport):
        content = error_details.format_reflection_prompt()
    else:
        content = (
            "Your previous response could not be parsed or validated against the required schema.\n"
            f"Validation Error: {error_details}\n"
            "Please fix the error and respond with ONLY the valid JSON object matching the schema, "
            "with no markdown explanations or extraneous commentary."
        )
    return ChatMessage(role="user", content=content)


def _prepare_structured_messages(
    prompt: str | list[ChatMessage] | None,
    user: str | None,
) -> list[ChatMessage]:
    """Normalize user prompt input into a list of ChatMessage instances."""
    if prompt is None and user is not None:
        return [ChatMessage(role="user", content=user)]
    if isinstance(prompt, str):
        return [ChatMessage(role="user", content=prompt)]
    if isinstance(prompt, list):
        return list(prompt)
    if user is not None:
        return [ChatMessage(role="user", content=user)]
    raise StructuredOutputSchemaError("Either prompt or user text must be provided.")


class StructuredOutputMixin:
    """Mixin adding structured JSON generation, repair, and error reflection retry to LLMClient."""

    _config: AIConfig

    def chat_messages(
        self,
        system: str,
        messages: list[ChatMessage],
        *,
        enable_thinking: bool = True,
        validator: Callable[[str], bool] | None = None,
        max_retries: int | None = None,
        use_cache: bool = True,
        starting_point: str | None = None,
        context_tag: str | None = None,
        append_cache: bool | None = None,
    ) -> LLMResponse:
        raise NotImplementedError

    def _execute_structured_step[T: BaseModel](
        self,
        system: str,
        messages: list[ChatMessage],
        schema: type[T],
        *,
        enable_thinking: bool,
        use_cache: bool,
        context_tag: str | None,
    ) -> tuple[T | None, bool, SchemaFailure | None, str]:
        """Dispatch a single chat request and evaluate parsed schema outcome.

        The schema check is the request's validator, so a reply that fails it is neither served
        from the response cache nor written to it, and comes back on `ReplyRejectedError` for
        the reflection.
        """
        try:
            res = self.chat_messages(
                system,
                messages,
                enable_thinking=enable_thinking,
                use_cache=use_cache,
                context_tag=context_tag,
                max_retries=0,
                validator=lambda text: _repair_and_validate_payload(text, schema)[0] is not None,
            )
        except ReplyRejectedError as rejected:
            res = LLMResponse(rejected.reply)
        raw_text = res.text if hasattr(res, "text") else str(res)
        model_inst, was_repaired, failure = _repair_and_validate_payload(raw_text, schema)
        return model_inst, was_repaired, failure, raw_text

    def _handle_structured_retry(
        self,
        messages: list[ChatMessage],
        raw_text: str,
        failure: SchemaFailure,
        attempt: int,
        backoff_seconds: float,
        model_name: str,
    ) -> None:
        """Record retry telemetry, backoff, and append reflection messages."""
        record_metric(
            CONST_METRIC_AI_STRUCTURED_RETRY_COUNT,
            1.0,
            attributes={"model": model_name},
        )
        time.sleep(backoff_seconds * (2 ** (attempt - 1)))
        messages.append(ChatMessage(role="assistant", content=raw_text))
        messages.append(_build_reflection_message(failure))

    def chat_structured[T: BaseModel](
        self,
        system: str,
        prompt: str | list[ChatMessage] | None = None,
        schema: type[T] | None = None,
        *,
        user: str | None = None,
        max_retries: int = DEFAULT_STRUCTURED_OUTPUT_MAX_RETRIES,
        backoff_seconds: float = DEFAULT_STRUCTURED_RETRY_BACKOFF_SECONDS,
        enable_thinking: bool = False,
        use_cache: bool = True,
        context_tag: str | None = None,
    ) -> T:
        """Send chat request and guarantee validated structured Pydantic output with repair and retry.

        The system message ends with the schema's JSON Schema, introduced by
        `structured_output_schema.md`, for every provider; the gateway and ollama providers also
        get it as their request's constraint (`constrain_reply`). Only the first attempt reads
        and writes the response cache, and only a reply that validates is written or served.
        """
        if schema is None:
            raise StructuredOutputSchemaError("A schema model class must be provided.")

        messages = _prepare_structured_messages(prompt, user)
        model_name = str(getattr(self._config, "model", "default"))
        provider_name = str(getattr(self._config, "provider", "unknown"))
        schema_name = getattr(schema, "__name__", str(schema))
        json_schema = schema.model_json_schema()
        structured_system = _with_reply_schema(system, json_schema)
        max_attempts = max(1, max_retries + 1)
        last_error: SchemaFailure = "Unknown schema error"

        with (
            trace_span(
                "ai.client.chat_structured",
                attributes={
                    "gen_ai.provider.name": genai_provider_name(provider_name),
                    "gen_ai.request.model": model_name,
                    "schema.name": schema_name,
                    "max_retries": max_retries,
                },
            ) as span_h,
            constrain_reply(ReplySchema(schema_name, json_schema)),
        ):
            for attempt in range(1, max_attempts + 1):
                attempt_cache = use_cache if attempt == 1 else False
                model_inst, was_repaired, failure, raw_text = self._execute_structured_step(
                    structured_system,
                    messages,
                    schema,
                    enable_thinking=enable_thinking,
                    use_cache=attempt_cache,
                    context_tag=context_tag,
                )
                if model_inst is not None:
                    record_metric(
                        CONST_METRIC_AI_STRUCTURED_SUCCESS,
                        1.0,
                        attributes={"model": model_name},
                    )
                    if was_repaired:
                        record_metric(
                            CONST_METRIC_AI_STRUCTURED_REPAIR_SUCCESS,
                            1.0,
                            attributes={"model": model_name},
                        )
                    span_h.set_attribute("structured.attempts", attempt)
                    span_h.set_attribute("structured.was_repaired", was_repaired)
                    return model_inst

                last_error = failure or "Failed to validate schema."
                record_metric(
                    CONST_METRIC_AI_STRUCTURED_VALIDATION_FAILURE,
                    1.0,
                    attributes={"model": model_name, "attempt": str(attempt)},
                )
                if attempt < max_attempts:
                    self._handle_structured_retry(
                        messages, raw_text, last_error, attempt, backoff_seconds, model_name
                    )

            exc = _validation_failure(model_name, max_attempts, last_error)
            span_h.record_exception(exc)
            raise exc
