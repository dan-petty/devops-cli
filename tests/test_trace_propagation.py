"""Test suite for W3C trace context propagation across headers, processes, and threads."""

from __future__ import annotations

import os
import subprocess
import threading
from typing import Any
from unittest.mock import patch

import pytest

from devops_cli.config.constants import (
    CONST_TRACE_FLAG_NOT_SAMPLED,
    CONST_TRACE_FLAG_SAMPLED,
    CONST_TRACEPARENT_ENV_VAR,
    CONST_TRACEPARENT_HEADER,
    CONST_TRACESTATE_ENV_VAR,
)
from devops_cli.telemetry.context import (
    TraceValidationError,
    extract_traceparent,
    extract_traceparent_from_headers,
    generate_traceparent,
    inject_traceparent_headers,
)
from devops_cli.telemetry.propagation import (
    TraceContext,
    extract_env,
    extract_headers,
    generate_span_id,
    generate_trace_id,
    inject_env,
    inject_headers,
    new_trace_context,
    parse_traceparent,
    sanitize_tracestate,
)
from devops_cli.telemetry.tracer import (
    ContextPropagatingThread,
    bind_context,
    clear_span_buffer,
    get_recent_spans,
    get_tracer,
    record_completed_span,
    reset_tracer,
)

VALID_TRACE_ID = "4bf92f3577b34da6a3ce929d0e0e4736"
VALID_SPAN_ID = "00f067aa0ba902b7"
VALID_TRACEPARENT = f"00-{VALID_TRACE_ID}-{VALID_SPAN_ID}-01"


@pytest.fixture
def tracer() -> Any:
    """Provide an enabled tracer with a clean span buffer."""
    environment = dict(os.environ)
    environment.pop(CONST_TRACEPARENT_ENV_VAR, None)
    environment.pop(CONST_TRACEPARENT_HEADER, None)
    with patch.dict(os.environ, environment, clear=True):
        reset_tracer()
        clear_span_buffer()
        yield get_tracer()
        clear_span_buffer()
        reset_tracer()


# =============================================================================
# Parsing
# =============================================================================


def test_a_valid_traceparent_parses_into_its_components() -> None:
    """The specification's own example parses into the fields it defines."""
    context = parse_traceparent(VALID_TRACEPARENT)
    assert context is not None
    assert (context.trace_id, context.span_id, context.trace_flags, context.sampled) == (
        VALID_TRACE_ID,
        VALID_SPAN_ID,
        "01",
        True,
    )


@pytest.mark.parametrize(
    ("description", "value"),
    [
        ("empty", ""),
        ("none-like whitespace", "   "),
        ("too few fields", f"00-{VALID_TRACE_ID}-{VALID_SPAN_ID}"),
        ("version ff is reserved", f"ff-{VALID_TRACE_ID}-{VALID_SPAN_ID}-01"),
        ("non-hex version", f"0g-{VALID_TRACE_ID}-{VALID_SPAN_ID}-01"),
        ("short trace id", f"00-{'a' * 31}-{VALID_SPAN_ID}-01"),
        ("long trace id", f"00-{'a' * 33}-{VALID_SPAN_ID}-01"),
        ("non-hex trace id", f"00-{'z' * 32}-{VALID_SPAN_ID}-01"),
        ("uppercase trace id", f"00-{VALID_TRACE_ID.upper()}-{VALID_SPAN_ID}-01"),
        ("all-zero trace id", f"00-{'0' * 32}-{VALID_SPAN_ID}-01"),
        ("short span id", f"00-{VALID_TRACE_ID}-{'a' * 15}-01"),
        ("non-hex span id", f"00-{VALID_TRACE_ID}-{'z' * 16}-01"),
        ("all-zero span id", f"00-{VALID_TRACE_ID}-{'0' * 16}-01"),
        ("non-hex flags", f"00-{VALID_TRACE_ID}-{VALID_SPAN_ID}-zz"),
        ("short flags", f"00-{VALID_TRACE_ID}-{VALID_SPAN_ID}-1"),
        ("version 00 with extra field", f"00-{VALID_TRACE_ID}-{VALID_SPAN_ID}-01-extra"),
        ("injected newline", f"00-{VALID_TRACE_ID}-{VALID_SPAN_ID}-01\nX-Evil: 1"),
    ],
)
def test_malformed_traceparents_are_rejected(description: str, value: str) -> None:
    """Invalid input yields no context rather than a half-parsed one.

    The value arrives from a caller's headers or from the ambient environment, so a lenient
    parser carries whatever it was handed into trace ids and out to the exporter.
    """
    assert parse_traceparent(value) is None, description


def test_a_future_version_is_accepted_with_its_extra_fields_ignored() -> None:
    """The specification requires forward compatibility with later versions."""
    context = parse_traceparent(f"01-{VALID_TRACE_ID}-{VALID_SPAN_ID}-01-future")
    assert context is not None
    assert (context.trace_id, context.span_id) == (VALID_TRACE_ID, VALID_SPAN_ID)


def test_an_unsampled_context_reports_its_flag() -> None:
    """The sampled bit is read from the flags rather than assumed."""
    context = parse_traceparent(f"00-{VALID_TRACE_ID}-{VALID_SPAN_ID}-00")
    assert context is not None
    assert (context.sampled, context.trace_flags) == (False, "00")


def test_generated_ids_are_valid_by_the_parser_that_will_read_them() -> None:
    """What the generator produces must be what the parser accepts."""
    context = TraceContext(trace_id=generate_trace_id(), span_id=generate_span_id())
    assert parse_traceparent(context.to_traceparent()) == context


def test_a_new_context_round_trips_through_its_own_rendering() -> None:
    """Formatting and parsing are inverse operations."""
    context = new_trace_context()
    assert parse_traceparent(context.to_traceparent()) == context


def test_an_unsampled_new_context_carries_the_unsampled_flag() -> None:
    """Sampling is expressible at construction."""
    assert new_trace_context(sampled=False).trace_flags == CONST_TRACE_FLAG_NOT_SAMPLED


def test_a_child_context_keeps_the_trace_and_takes_a_new_span() -> None:
    """A child span belongs to the same trace under a different span id."""
    parent = new_trace_context()
    child = parent.child()
    assert (child.trace_id, child.span_id != parent.span_id, child.trace_flags) == (
        parent.trace_id,
        True,
        parent.trace_flags,
    )


# =============================================================================
# Tracestate
# =============================================================================


def test_tracestate_is_truncated_to_the_permitted_member_count() -> None:
    """Forwarding an oversized tracestate breaks the next hop instead of this one."""
    oversized = ",".join(f"vendor{index}=value" for index in range(50))
    sanitized = sanitize_tracestate(oversized)
    assert sanitized is not None
    assert len(sanitized.split(",")) == 32


def test_an_empty_tracestate_is_dropped_rather_than_forwarded() -> None:
    """A header with no members carries no information and is omitted."""
    assert (sanitize_tracestate(""), sanitize_tracestate(" , , ")) == (None, None)


def test_tracestate_members_are_trimmed() -> None:
    """Whitespace around list members is not significant."""
    assert sanitize_tracestate(" a=1 , b=2 ") == "a=1,b=2"


# =============================================================================
# HTTP header carrier
# =============================================================================


def test_headers_carry_the_context_under_the_lowercase_name() -> None:
    """HTTP propagation uses the lowercase header the specification defines."""
    context = parse_traceparent(VALID_TRACEPARENT)
    assert context is not None
    assert inject_headers(context)[CONST_TRACEPARENT_HEADER] == VALID_TRACEPARENT


def test_injecting_headers_leaves_the_caller_mapping_untouched() -> None:
    """The header carrier returns a copy, so a shared mapping is not mutated."""
    original = {"authorization": "token"}
    injected = inject_headers(new_trace_context(), original)
    assert (CONST_TRACEPARENT_HEADER in original, CONST_TRACEPARENT_HEADER in injected) == (
        False,
        True,
    )


def test_headers_are_extracted_case_insensitively() -> None:
    """Servers and proxies vary the casing of header names."""
    context = extract_headers({"TraceParent": VALID_TRACEPARENT})
    assert context is not None
    assert context.trace_id == VALID_TRACE_ID


def test_extracting_from_headers_without_a_traceparent_yields_nothing() -> None:
    """Absence of the header is not an error."""
    assert extract_headers({"authorization": "token"}) is None


def test_a_context_round_trips_through_headers() -> None:
    """What is injected is what is extracted."""
    context = new_trace_context()
    assert extract_headers(inject_headers(context)) == context


def test_tracestate_round_trips_through_headers() -> None:
    """Vendor state survives the header carrier."""
    context = TraceContext(
        trace_id=VALID_TRACE_ID, span_id=VALID_SPAN_ID, trace_state="vendor=value"
    )
    assert extract_headers(inject_headers(context)) == context


# =============================================================================
# Process environment carrier
# =============================================================================


def test_the_environment_carrier_mutates_the_environment_it_is_given() -> None:
    """The caller already holds the environment it will hand to the child.

    Returning a copy is exactly how the context came to be silently dropped: both
    subprocess call sites discarded the returned value.
    """
    env: dict[str, str] = {"PATH": "/usr/bin"}
    context = new_trace_context()
    returned = inject_env(context, env)
    assert (env[CONST_TRACEPARENT_ENV_VAR], returned is env) == (
        context.to_traceparent(),
        True,
    )


def test_the_environment_carrier_uses_the_uppercase_variable_name() -> None:
    """Process environments use TRACEPARENT; only HTTP headers are lowercase."""
    env: dict[str, str] = {}
    inject_env(new_trace_context(), env)
    assert (CONST_TRACEPARENT_ENV_VAR in env, CONST_TRACEPARENT_HEADER in env) == (True, False)


def test_an_inherited_lowercase_spelling_cannot_shadow_the_injected_context() -> None:
    """A stale value under the other spelling must not survive injection.

    Extraction accepts both spellings, so leaving an inherited lowercase value in place
    would let a grandparent's context win over the one being injected here.
    """
    env = {CONST_TRACEPARENT_HEADER: f"00-{'a' * 32}-{'b' * 16}-01"}
    context = new_trace_context()
    inject_env(context, env)
    extracted = extract_env(env)
    assert extracted is not None
    assert (extracted.trace_id, CONST_TRACEPARENT_HEADER in env) == (context.trace_id, False)


def test_injecting_replaces_a_stale_inherited_context() -> None:
    """Each hop must overwrite the context it inherited, not append to it."""
    env = {CONST_TRACEPARENT_ENV_VAR: f"00-{'a' * 32}-{'b' * 16}-01"}
    context = new_trace_context()
    inject_env(context, env)
    assert env[CONST_TRACEPARENT_ENV_VAR] == context.to_traceparent()


def test_a_context_without_tracestate_clears_an_inherited_one() -> None:
    """Forwarding vendor state from an unrelated trace would misattribute it."""
    env = {CONST_TRACESTATE_ENV_VAR: "oldvendor=stale"}
    inject_env(new_trace_context(), env)
    assert CONST_TRACESTATE_ENV_VAR not in env


def test_a_context_round_trips_through_the_environment() -> None:
    """What the parent injects is what the child extracts."""
    env: dict[str, str] = {}
    context = TraceContext(
        trace_id=VALID_TRACE_ID, span_id=VALID_SPAN_ID, trace_state="vendor=value"
    )
    inject_env(context, env)
    assert extract_env(env) == context


def test_a_malformed_inherited_context_is_not_adopted() -> None:
    """A child must start a fresh trace rather than adopt an unparseable one."""
    assert extract_env({CONST_TRACEPARENT_ENV_VAR: "garbage"}) is None


def test_extracting_from_the_ambient_environment_reads_the_process_variables() -> None:
    """With no explicit mapping the real process environment is consulted."""
    with patch.dict(os.environ, {CONST_TRACEPARENT_ENV_VAR: VALID_TRACEPARENT}, clear=False):
        context = extract_env()
    assert context is not None
    assert context.trace_id == VALID_TRACE_ID


# =============================================================================
# Subprocess Propagation
# =============================================================================


def test_a_subprocess_receives_the_active_span_as_its_parent(tracer: Any) -> None:
    """The child process must be parented to the span that spawned it.

    Both subprocess call sites previously discarded the injected copy, so no child process
    ever received a parent span and every subprocess started a fresh root trace. The
    docstring claimed propagation; nothing asserted it.
    """
    from devops_cli.core.process import run_subprocess

    captured: dict[str, dict[str, str]] = {}

    def fake_run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        captured["env"] = dict(kwargs["env"])
        return subprocess.CompletedProcess(cmd, returncode=0, stdout="", stderr="")

    with tracer.span("parent-operation"):
        trace_id, outer_span_id = tracer.current_trace_id, tracer.current_span_id
        with patch("subprocess.run", side_effect=fake_run):
            run_subprocess(["echo", "hello"], quiet=True)

    child = extract_env(captured["env"])
    subprocess_spans = [
        span for span in get_recent_spans() if span.get("name") == "subprocess.echo"
    ]
    assert child is not None
    assert len(subprocess_spans) == 1
    # The child belongs to the same trace and is parented to the span that spawned it --
    # the subprocess span itself, not the operation enclosing it.
    assert (child.trace_id, child.span_id, child.span_id == outer_span_id) == (
        trace_id,
        subprocess_spans[0]["spanId"],
        False,
    )


def test_a_subprocess_spawned_outside_a_span_still_carries_a_valid_context(
    tracer: Any,
) -> None:
    """A child must never receive a malformed or absent context."""
    from devops_cli.core.process import run_subprocess

    captured: dict[str, dict[str, str]] = {}

    def fake_run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        captured["env"] = dict(kwargs["env"])
        return subprocess.CompletedProcess(cmd, returncode=0, stdout="", stderr="")

    with patch("subprocess.run", side_effect=fake_run):
        run_subprocess(["echo", "hello"], quiet=True)

    assert extract_env(captured["env"]) is not None


def test_a_disabled_tracer_injects_no_context_into_a_child() -> None:
    """Telemetry that is switched off must not write trace variables into the environment."""
    with patch(
        "devops_cli.telemetry.tracer._resolve_telemetry_settings", return_value=(None, False)
    ):
        reset_tracer()
        client = get_tracer()
        env: dict[str, str] = {}
        client.inject_trace_env(env)
        headers = client.inject_trace_context({"accept": "application/json"})
        reset_tracer()
    assert (env, CONST_TRACEPARENT_HEADER in headers) == ({}, False)


def test_the_header_injector_still_does_not_mutate_its_argument(tracer: Any) -> None:
    """The HTTP carrier keeps its copying contract; only the env carrier mutates."""
    headers: dict[str, str] = {}
    with tracer.span("operation"):
        returned = tracer.inject_trace_context(headers)
    assert (headers, CONST_TRACEPARENT_HEADER in returned) == ({}, True)


def test_a_span_adopts_a_valid_context_inherited_from_a_parent_process() -> None:
    """A nested CLI invocation continues its parent's trace rather than starting one."""
    with patch.dict(
        os.environ,
        {"DEVOPS_OTEL_ENABLED": "1", CONST_TRACEPARENT_ENV_VAR: VALID_TRACEPARENT},
        clear=False,
    ):
        reset_tracer()
        client = get_tracer()
        with client.span("child-operation"):
            adopted = client.current_trace_id
        reset_tracer()
    assert adopted == VALID_TRACE_ID


def test_a_span_ignores_a_malformed_context_inherited_from_a_parent_process() -> None:
    """Ambient input is validated before it becomes a trace id.

    Adopting an unvalidated value would export a trace keyed on whatever the environment
    happened to contain.
    """
    with patch.dict(
        os.environ,
        {"DEVOPS_OTEL_ENABLED": "1", CONST_TRACEPARENT_ENV_VAR: "00-nothex-nothex-01"},
        clear=False,
    ):
        reset_tracer()
        client = get_tracer()
        with client.span("child-operation"):
            adopted = client.current_trace_id
        reset_tracer()
    assert adopted is not None
    assert parse_traceparent(f"00-{adopted}-{VALID_SPAN_ID}-01") is not None


# =============================================================================
# Thread Propagation
# =============================================================================


def test_a_context_propagating_thread_continues_the_spawning_trace(tracer: Any) -> None:
    """Work moved onto a thread must stay inside the trace that scheduled it.

    A bare thread starts with empty context variables, so any span it opens becomes a new
    root and the work disappears from the trace that caused it.
    """
    seen: dict[str, str | None] = {}

    def worker() -> None:
        seen["trace_id"] = tracer.current_trace_id

    with tracer.span("parent-operation"):
        expected = tracer.current_trace_id
        thread = ContextPropagatingThread(target=worker)
        thread.start()
        thread.join(timeout=5)

    assert seen["trace_id"] == expected


def test_a_bare_thread_loses_the_trace_which_is_why_the_helper_exists(tracer: Any) -> None:
    """The failure the propagating thread prevents is asserted, not assumed."""
    seen: dict[str, str | None] = {}

    def worker() -> None:
        seen["trace_id"] = tracer.current_trace_id

    with tracer.span("parent-operation"):
        thread = threading.Thread(target=worker)
        thread.start()
        thread.join(timeout=5)

    assert seen["trace_id"] is None


def test_bind_context_carries_the_trace_into_a_foreign_executor(tracer: Any) -> None:
    """Work handed to a pool this module does not own keeps its context."""
    from concurrent.futures import ThreadPoolExecutor

    with tracer.span("parent-operation"):
        expected = tracer.current_trace_id
        bound = bind_context(lambda: tracer.current_trace_id)
        with ThreadPoolExecutor(max_workers=1) as pool:
            observed = pool.submit(bound).result(timeout=5)

    assert observed == expected


def test_binding_inside_the_worker_would_capture_nothing(tracer: Any) -> None:
    """The snapshot must be taken on the calling thread, not the worker.

    Copying the context inside the worker captures the worker's own empty context, so the
    helper has to be called before the work is submitted.
    """
    from concurrent.futures import ThreadPoolExecutor

    with tracer.span("parent-operation"):
        with ThreadPoolExecutor(max_workers=1) as pool:
            late = pool.submit(lambda: bind_context(lambda: tracer.current_trace_id)()).result(
                timeout=5
            )

    assert late is None


# =============================================================================
# Span Buffer
# =============================================================================


def test_the_span_buffer_retains_a_bounded_window() -> None:
    """A long-running command must not grow the buffer without limit."""
    clear_span_buffer()
    for index in range(2500):
        record_completed_span({"traceId": "t", "spanId": f"s{index}"})
    retained = get_recent_spans()
    clear_span_buffer()
    assert (len(retained), retained[-1]["spanId"]) == (1000, "s2499")


def test_the_span_buffer_evicts_the_oldest_spans_first() -> None:
    """Eviction is first-in-first-out, so the most recent spans are the ones kept."""
    clear_span_buffer()
    for index in range(1100):
        record_completed_span({"traceId": "t", "spanId": f"s{index}"})
    ids = {span["spanId"] for span in get_recent_spans()}
    clear_span_buffer()
    assert ("s0" in ids, "s99" in ids, "s100" in ids) == (False, False, True)


def test_recorded_spans_are_copied_so_later_mutation_cannot_alter_them() -> None:
    """A caller reusing its span dict must not retroactively rewrite the buffer."""
    clear_span_buffer()
    span = {"traceId": "t", "spanId": "s0"}
    record_completed_span(span)
    span["spanId"] = "mutated"
    retained = get_recent_spans()
    clear_span_buffer()
    assert retained[0]["spanId"] == "s0"


# =============================================================================
# Legacy Context Helpers
# =============================================================================


def test_generate_traceparent_produces_a_value_the_parser_accepts() -> None:
    """The public generator and the parser agree on what is valid."""
    assert parse_traceparent(generate_traceparent()) is not None


def test_generate_traceparent_rejects_flags_outside_the_supported_set() -> None:
    """A caller constructing a context with bad flags has made a programming error."""
    with pytest.raises(TraceValidationError):
        generate_traceparent(trace_flags="zz")


def test_generate_traceparent_rejects_a_malformed_trace_id() -> None:
    """Components are validated rather than concatenated blindly."""
    with pytest.raises(TraceValidationError):
        generate_traceparent(trace_id="short")


def test_generate_traceparent_accepts_the_unsampled_flag() -> None:
    """Both specification-defined flag values are constructible."""
    value = generate_traceparent(trace_flags=CONST_TRACE_FLAG_NOT_SAMPLED)
    context = parse_traceparent(value)
    assert context is not None
    assert context.sampled is False


def test_extract_traceparent_returns_the_documented_component_names() -> None:
    """Existing callers depend on these keys."""
    assert extract_traceparent(VALID_TRACEPARENT) == {
        "trace_id": VALID_TRACE_ID,
        "parent_span_id": VALID_SPAN_ID,
        "trace_flags": CONST_TRACE_FLAG_SAMPLED,
    }


def test_extract_traceparent_rejects_what_the_shared_parser_rejects() -> None:
    """The lenient length-only check this replaced accepted non-hex values."""
    assert extract_traceparent(f"00-{'z' * 32}-{'z' * 16}-01") is None


def test_extract_traceparent_from_headers_matches_names_case_insensitively() -> None:
    """Header casing varies by client."""
    result = extract_traceparent_from_headers({"TRACEPARENT": VALID_TRACEPARENT})
    assert result is not None
    assert result["trace_id"] == VALID_TRACE_ID


def test_extract_traceparent_from_headers_without_one_yields_nothing() -> None:
    """Absence is not an error."""
    assert extract_traceparent_from_headers({"accept": "application/json"}) is None


def test_injecting_traceparent_headers_uses_the_active_span(tracer: Any) -> None:
    """An open span is the context callers expect to propagate."""
    with tracer.span("operation"):
        expected = tracer.current_trace_id
        headers = inject_traceparent_headers()
    context = parse_traceparent(headers[CONST_TRACEPARENT_HEADER])
    assert context is not None
    assert context.trace_id == expected


def test_injecting_traceparent_headers_without_a_span_generates_nothing_by_default() -> None:
    """Inventing a trace id for no recorded span produces a trace no backend can resolve."""
    reset_tracer()
    assert CONST_TRACEPARENT_HEADER not in inject_traceparent_headers()


def test_injecting_traceparent_headers_can_generate_one_on_request() -> None:
    """Callers that need a correlation id can opt in."""
    reset_tracer()
    headers = inject_traceparent_headers(auto_generate=True)
    assert parse_traceparent(headers[CONST_TRACEPARENT_HEADER]) is not None


def test_injecting_traceparent_headers_preserves_an_existing_one() -> None:
    """An upstream context already on the request is not overwritten by a synthetic one."""
    reset_tracer()
    headers = inject_traceparent_headers(
        {CONST_TRACEPARENT_HEADER: VALID_TRACEPARENT}, auto_generate=True
    )
    assert headers[CONST_TRACEPARENT_HEADER] == VALID_TRACEPARENT


def test_injecting_traceparent_headers_carries_sanitized_tracestate() -> None:
    """Vendor state is forwarded, trimmed to the permitted member count."""
    reset_tracer()
    headers = inject_traceparent_headers(
        auto_generate=True, tracestate=",".join(f"v{i}=x" for i in range(40))
    )
    assert len(headers["tracestate"].split(",")) == 32


def test_a_context_with_unparseable_flags_reports_itself_unsampled() -> None:
    """A directly constructed context that bypassed the parser must not raise on read.

    `sampled` is consulted while building export payloads, where an exception would lose
    the span rather than merely mislabel it.
    """
    context = TraceContext(trace_id=VALID_TRACE_ID, span_id=VALID_SPAN_ID, trace_flags="zz")
    assert context.sampled is False


def test_an_explicit_parent_context_outranks_the_open_span(tracer: Any) -> None:
    """A caller supplying a context is continuing someone else's trace."""
    with tracer.span("local-operation"):
        with tracer.span(
            "remote-continuation", parent_context={CONST_TRACEPARENT_HEADER: VALID_TRACEPARENT}
        ):
            observed = tracer.current_trace_id
    assert observed == VALID_TRACE_ID


def test_a_malformed_supplied_parent_context_falls_back_to_the_open_span(tracer: Any) -> None:
    """Bad input from a caller must not orphan the span into a new trace."""
    with tracer.span("local-operation"):
        expected = tracer.current_trace_id
        with tracer.span("child", parent_context={CONST_TRACEPARENT_HEADER: "garbage"}):
            observed = tracer.current_trace_id
    assert observed == expected


def test_an_explicit_parent_trace_id_is_honoured(tracer: Any) -> None:
    """The lowest-level override remains available to callers that reconstruct a trace."""
    with tracer.span("adopted", parent_trace_id=VALID_TRACE_ID, parent_span_id=VALID_SPAN_ID):
        observed = tracer.current_trace_id
    assert observed == VALID_TRACE_ID
