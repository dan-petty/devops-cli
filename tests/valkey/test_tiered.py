"""The tiered mapping of the project brain: an in-process tier over the shared Valkey tier (#4668).

Each test runs the mapping over the in-memory Valkey (`shared_valkey`), whose server fails each
command while `connected` is False, and reads the counters of the mapping and of the cache tier
on the OTLP fake. A read that reached Valkey while the server was down counts a `connection`
error, and a read that the open breaker did not send counts `open`, so the counters show each
command that the mapping sent.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from cachetools import cached
from fakeredis import FakeServer, FakeValkey
from pydantic import BaseModel, TypeAdapter

from devops_cli.config.constants import CONST_VALKEY_BRAIN_PREFIX
from tests.support.fakes.otlp import FakeCollector

if TYPE_CHECKING:
    from devops_cli.valkey.cache import ValkeyCacheTier
    from devops_cli.valkey.tiered import TieredMapping

_PREFIX = f"{CONST_VALKEY_BRAIN_PREFIX}:fact:test"
_TTL = 60


class _Fact(BaseModel):
    name: str
    stars: int


def _facts(adapter: TypeAdapter[Any] | None = None) -> TieredMapping[Any]:
    """A mapping of facts under `_PREFIX`, as a new process builds it.

    The import is local, so the module loads on a base without the mapping.
    """
    from devops_cli.valkey.tiered import TieredMapping

    return TieredMapping(_PREFIX, adapter or TypeAdapter(_Fact), ttl=_TTL)


def _summed(otlp: FakeCollector, name: str, *labels: str) -> dict[tuple[str, ...], float]:
    """The data points of the counter `name`, summed by the values of `labels`."""
    counted: dict[tuple[str, ...], float] = {}
    for attributes, value in otlp.points(name):
        point = tuple(attributes[label] for label in labels)
        counted[point] = counted.get(point, 0) + value
    return counted


def _reads(otlp: FakeCollector) -> dict[tuple[str, ...], float]:
    from devops_cli.telemetry.instruments import BRAIN_READS_TOTAL

    return _summed(otlp, BRAIN_READS_TOTAL.name, "store", "result")


def _writes(otlp: FakeCollector) -> dict[tuple[str, ...], float]:
    from devops_cli.telemetry.instruments import BRAIN_WRITES_TOTAL

    return _summed(otlp, BRAIN_WRITES_TOTAL.name, "store", "result")


def _errors(otlp: FakeCollector) -> dict[tuple[str, ...], float]:
    from devops_cli.telemetry.instruments import VALKEY_CACHE_ERRORS_TOTAL

    return _summed(otlp, VALKEY_CACHE_ERRORS_TOTAL.name, "op", "error")


def _stored(server: FakeServer) -> dict[str, tuple[str, bool]]:
    """Each key on the server, with its value and whether it has a TTL above 0."""
    reader = FakeValkey(server=server, decode_responses=True)
    return {key: (reader.get(key), 0 < reader.ttl(key) <= _TTL) for key in reader.keys("*")}


def test_a_shared_read_fills_the_memory_tier(
    shared_valkey: ValkeyCacheTier, valkey_server: FakeServer, otlp: FakeCollector
) -> None:
    """T1: a second process reads the fact from Valkey once; its next read is from memory.

    The server is down for the second read, so a read that reached Valkey would count an error.
    """
    fact = _Fact(name="tool", stars=3)
    _facts()["tool"] = fact
    otlp.clear()
    reader = _facts()

    first = reader["tool"]
    valkey_server.connected = False
    second = reader["tool"]

    assert (first, second, _reads(otlp), _errors(otlp)) == (
        fact,
        fact,
        {("fact", "shared"): 1.0, ("fact", "memory"): 1.0},
        {},
    )


def test_a_down_shared_tier_gives_the_source_value_and_keeps_the_write_in_memory(
    shared_valkey: ValkeyCacheTier, valkey_server: FakeServer, otlp: FakeCollector
) -> None:
    """T2: with Valkey down, each read goes to the source and each write stays in memory.

    One command reaches Valkey and fails; the open breaker sends no other command in the
    cooldown, and no error reaches the caller.
    """
    sources: list[str] = []

    @cached(_facts(), key=str)
    def read(name: str) -> _Fact:
        sources.append(name)
        return _Fact(name=name, stars=1)

    valkey_server.connected = False
    results = [read("a"), read("b"), read("a")]
    valkey_server.connected = True

    assert (
        [fact.name for fact in results],
        sources,
        _stored(valkey_server),
        _reads(otlp),
        _writes(otlp),
        _errors(otlp),
    ) == (
        ["a", "b", "a"],
        ["a", "b"],
        {},
        {("fact", "fallback"): 2.0, ("fact", "memory"): 1.0},
        {("fact", "skipped"): 2.0},
        {("get", "connection"): 1.0, ("get", "open"): 1.0, ("set", "open"): 2.0},
    )


def test_an_oversize_value_stays_in_memory_and_each_key_has_a_ttl(
    shared_valkey: ValkeyCacheTier, valkey_server: FakeServer, otlp: FakeCollector
) -> None:
    """T5: a value whose encoded form is 1 MiB and one byte is not sent; a value of 1 KiB is,
    with a TTL."""
    from devops_cli.config.defaults import DEFAULT_BRAIN_VALUE_MAX_BYTES

    texts = _facts(TypeAdapter(str))
    # The encoded form is the 16 characters of the schema key, a colon, and the JSON string.
    big = "x" * (DEFAULT_BRAIN_VALUE_MAX_BYTES - len(texts.schema_key) - 1 - 2 + 1)
    small = "y" * 1024
    texts["big"] = big
    texts["small"] = small

    assert (texts["big"] == big, _stored(valkey_server), _writes(otlp)) == (
        True,
        {f"{_PREFIX}:small": (f"{texts.schema_key}:{json.dumps(small)}", True)},
        {("fact", "oversize"): 1.0, ("fact", "shared"): 1.0},
    )


def test_a_value_of_an_old_kind_or_schema_is_read_from_the_source(
    shared_valkey: ValkeyCacheTier, valkey_server: FakeServer, otlp: FakeCollector
) -> None:
    """T6: a fact under an older key version, and a fact under the current key with another
    schema key, are misses; the source value replaces them under the current key."""
    old = _Fact(name="old", stars=0).model_dump_json()
    writer = FakeValkey(server=valkey_server, decode_responses=True)
    writer.set("valkey:brain:v0:fact:test:a", f"0000000000000000:{old}", ex=_TTL)
    writer.set(f"{_PREFIX}:b", f"0123456789abcdef:{old}", ex=_TTL)
    facts = _facts()

    @cached(facts, key=str)
    def read(name: str) -> _Fact:
        return _Fact(name=name, stars=2)

    results = [read("a"), read("b")]
    fresh = {name: _Fact(name=name, stars=2).model_dump_json() for name in ("a", "b")}

    assert (results, _stored(valkey_server), _reads(otlp)) == (
        [_Fact(name="a", stars=2), _Fact(name="b", stars=2)],
        {
            "valkey:brain:v0:fact:test:a": (f"0000000000000000:{old}", True),
            f"{_PREFIX}:a": (f"{facts.schema_key}:{fresh['a']}", True),
            f"{_PREFIX}:b": (f"{facts.schema_key}:{fresh['b']}", True),
        },
        {("fact", "source"): 2.0},
    )


def test_the_brain_counters_send_only_fixed_labels(
    shared_valkey: ValkeyCacheTier, valkey_server: FakeServer, otlp: FakeCollector
) -> None:
    """The counters of a fact read with the shared tier up and one with it down hold only the
    labels `store`, `result`, `op` and `error`, each with a value of a fixed set, and never the
    name of the package."""
    from devops_cli.config.constants import BrainRead, BrainStore, BrainWrite, ValkeyCacheError
    from devops_cli.telemetry.instruments import (
        BRAIN_READS_TOTAL,
        BRAIN_WRITES_TOTAL,
        VALKEY_CACHE_ERRORS_TOTAL,
    )

    @cached(_facts(), key=str)
    def read(name: str) -> _Fact:
        return _Fact(name=name, stars=1)

    read("secret-package-up")
    valkey_server.connected = False
    read("secret-package-down")
    allowed = {
        "store": {str(value) for value in BrainStore},
        "result": {str(value) for value in (*BrainRead, *BrainWrite)},
        "op": {"get", "set"},
        "error": {str(value) for value in ValkeyCacheError},
    }
    points = [
        attributes
        for name in (BRAIN_READS_TOTAL, BRAIN_WRITES_TOTAL, VALKEY_CACHE_ERRORS_TOTAL)
        for attributes, _ in otlp.points(name.name)
    ]
    unbounded = [
        (label, value)
        for attributes in points
        for label, value in attributes.items()
        if value not in allowed.get(label, set())
    ]

    assert (len(points) >= 3, unbounded) == (True, [])
