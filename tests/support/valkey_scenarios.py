"""The scenarios of the Valkey fake's contract suite: valkey-py calls, and what each one reads (#4557).

Each scenario sends its commands through a valkey-py client and returns what a caller reads, with
no value that changes with the clock: a TTL is a bounded fact, and an absolute expiry is a fixed
time far in the future. `tests/valkey/test_valkey_contract.py` runs each scenario over the fake
(`FakeValkey` on a fresh `FakeServer`) and over a real valkey-py client that reads the recorded
replies of a real `valkey-server`. `tests/support/valkey_recording.py` records those replies by
running the same scenarios against a real server.

The request bytes do not change between runs: a `Lock` gets an explicit token and timeout, and
`SET EXAT` a fixed time. Each scenario uses its own key prefix and deletes its keys at the end. A
scenario that runs Lua sends `SCRIPT FLUSH` first, so valkey-py meets `NOSCRIPT` and loads the
script on both sides in each order in which the cases run. A binary value is a fixed zlib text,
so its bytes do not change between runs either.
"""

from __future__ import annotations

import zlib
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import valkey
from valkey.client import NEVER_DECODE
from valkey.exceptions import LockNotOwnedError, ResponseError, WatchError

from devops_cli.exceptions.valkey import ValkeyCommandError
from devops_cli.valkey.client import ValkeyClient
from devops_cli.valkey.endpoint import parse_valkey_url

PREFIX = "devops-contract"
# 2100-01-01T00:00:00Z: an absolute expiry that does not pass while the record is in use.
FAR_EXPIRY = 4_102_444_800
# An absolute expiry in the past, which deletes the key at once.
PAST_EXPIRY = 1
TTL_SECONDS = 60
LOCK_TIMEOUT_SECONDS = 10
LOCK_EXTEND_SECONDS = 5
LOCK_TOKEN = f"{PREFIX}-token"
OTHER_TOKEN = f"{PREFIX}-other"
INTRUDER_TOKEN = f"{PREFIX}-intruder"
# How long the project client waits for a reply in the `eval` scenario.
COMMAND_TIMEOUT_SECONDS = 5.0
INCRBY_SCRIPT = "return redis.call('INCRBY', KEYS[1], ARGV[1])"
# A Lua table becomes an array reply: a number is cut to an integer, `false` becomes nil.
TABLE_SCRIPT = "return {1, 'two', 3.7, false, {KEYS[1], ARGV[1]}}"
SET_AND_GET_SCRIPT = "redis.call('SET', KEYS[1], ARGV[1]); return redis.call('GET', KEYS[1])"
STATUS_SCRIPT = "return redis.status_reply('DONE')"
ERROR_SCRIPT = "return redis.error_reply('devops contract refusal')"
# A zlib value, as the shared listing snapshot keeps each record: bytes that are not UTF-8.
BINARY_VALUE = zlib.compress(b'{"number": 1, "title": "devops contract"}' * 4)
# How many fields one `HSCAN` asks for, as the shared listing snapshot reads them.
SCAN_COUNT = 500
# The TTL of the temporary key of a full write of the shared listing snapshot.
TEMPORARY_TTL_SECONDS = 600


def _key(scenario: str, name: str) -> str:
    return f"{PREFIX}:{scenario}:{name}"


def _refusal(call: Callable[[], Any]) -> tuple[str, str]:
    """The error a call raises: its class and its message."""
    try:
        call()
    except (ResponseError, ValkeyCommandError) as exc:
        return type(exc).__name__, str(exc)
    return "none", ""


def set_nx_ex(client: valkey.Valkey) -> tuple[Any, ...]:
    """`SET NX EX` sets a new key with a TTL, and refuses a key that exists."""
    key = _key("set_nx_ex", "key")
    first = client.set(key, "first", nx=True, ex=TTL_SECONDS)
    second = client.set(key, "second", nx=True, ex=TTL_SECONDS)
    ttl = client.ttl(key)
    return first, second, client.get(key), 0 < ttl <= TTL_SECONDS, client.delete(key)


def set_exat(client: valkey.Valkey) -> tuple[Any, ...]:
    """`SET EXAT` sets an absolute expiry, `KEEPTTL` keeps it, and a past time deletes the key."""
    key, gone = _key("set_exat", "key"), _key("set_exat", "gone")
    stored = client.set(key, "first", exat=FAR_EXPIRY)
    expiry = client.expiretime(key)
    kept = client.set(key, "second", xx=True, keepttl=True)
    return (
        stored,
        expiry,
        kept,
        client.expiretime(key),
        client.get(key),
        client.set(gone, "past", exat=PAST_EXPIRY),
        client.get(gone),
        client.delete(key, gone),
    )


def hincrby(client: valkey.Valkey) -> tuple[Any, ...]:
    """`HINCRBY` adds to a hash field, and refuses a field that holds no integer."""
    key = _key("hincrby", "hash")
    added = client.hincrby(key, "count", 5)
    taken = client.hincrby(key, "count", -2)
    client.hset(key, "text", "x")
    return (
        added,
        taken,
        _refusal(lambda: client.hincrby(key, "text", 1)),
        client.hgetall(key),
        client.delete(key),
    )


def zadd_and_trim(client: valkey.Valkey) -> tuple[Any, ...]:
    """`ZADD` adds members, and `ZREMRANGEBYSCORE` and `ZREMRANGEBYRANK` trim a window."""
    key = _key("zadd_and_trim", "window")
    added = client.zadd(key, {"a": 1, "b": 2, "c": 3, "d": 4})
    by_score = client.zremrangebyscore(key, "-inf", 2)
    after_score = client.zrange(key, 0, -1, withscores=True)
    client.zadd(key, {"e": 5})
    by_rank = client.zremrangebyrank(key, 0, -3)
    return (
        added,
        by_score,
        after_score,
        by_rank,
        client.zcard(key),
        client.zrange(key, 0, -1),
        client.delete(key),
    )


def lock_lifecycle(client: valkey.Valkey) -> tuple[Any, ...]:
    """A valkey-py `Lock` is acquired, refused to a second holder, extended, owned and released."""
    name = _key("lock_lifecycle", "lock")
    client.script_flush()
    lock = client.lock(name, timeout=LOCK_TIMEOUT_SECONDS, blocking=False)
    other = client.lock(name, timeout=LOCK_TIMEOUT_SECONDS, blocking=False)
    acquired = lock.acquire(token=LOCK_TOKEN)
    refused = other.acquire(token=OTHER_TOKEN)
    extended = lock.extend(LOCK_EXTEND_SECONDS)
    left = client.ttl(name)
    owned = lock.owned()
    lock.release()
    return (
        acquired,
        refused,
        extended,
        LOCK_TIMEOUT_SECONDS < left <= LOCK_TIMEOUT_SECONDS + LOCK_EXTEND_SECONDS,
        owned,
        lock.owned(),
        client.exists(name),
    )


def _lock_refusal(call: Callable[[], Any]) -> str:
    """The class of the lock error a call raises."""
    try:
        call()
    except LockNotOwnedError as exc:
        return type(exc).__name__
    return "none"


def lock_lost(client: valkey.Valkey) -> tuple[Any, ...]:
    """A `Lock` whose key another holder took is not owned, and cannot be extended or released."""
    name = _key("lock_lost", "lock")
    client.script_flush()
    lock = client.lock(name, timeout=LOCK_TIMEOUT_SECONDS, blocking=False)
    acquired = lock.acquire(token=LOCK_TOKEN)
    client.set(name, INTRUDER_TOKEN)
    return (
        acquired,
        lock.owned(),
        _lock_refusal(lambda: lock.extend(LOCK_EXTEND_SECONDS)),
        _lock_refusal(lock.release),
        client.get(name),
        client.delete(name),
    )


def registered_script(client: valkey.Valkey) -> tuple[Any, ...]:
    """A script from `register_script` runs by `EVALSHA`, and loads itself after `NOSCRIPT`."""
    key = _key("registered_script", "count")
    client.script_flush()
    script = client.register_script(INCRBY_SCRIPT)
    first = script(keys=[key], args=[3])
    second = script(keys=[key], args=[4])
    return first, second, client.script_exists(script.sha), client.get(key), client.delete(key)


def eval_through_the_project_client(client: valkey.Valkey) -> tuple[Any, ...]:
    """`EVAL` through the project's `ValkeyClient` turns Lua values into replies and errors."""
    key = _key("eval", "key")
    project = ValkeyClient(
        parse_valkey_url("valkey://127.0.0.1", setting="valkey.url"),
        timeout=COMMAND_TIMEOUT_SECONDS,
        connection_pool=client.connection_pool,
    )
    return (
        project.eval(TABLE_SCRIPT, 1, key, "x"),
        project.eval(SET_AND_GET_SCRIPT, 1, key, "stored"),
        project.eval(STATUS_SCRIPT, 0),
        _refusal(lambda: project.eval(ERROR_SCRIPT, 0)),
        project.delete(key),
    )


def _watch_refusal(call: Callable[[], Any]) -> str:
    """The class of the error that a transaction raises when a watched key changed."""
    try:
        call()
    except WatchError as exc:
        return type(exc).__name__
    return "none"


def watch_lost(client: valkey.Valkey) -> tuple[Any, ...]:
    """A transaction whose watched hash another client changed writes nothing (#4668)."""
    key = _key("watch_lost", "hash")
    client.hset(key, "meta", "first")
    with client.pipeline(transaction=True) as pipe:
        pipe.watch(key)
        seen = pipe.hget(key, "meta")
        # The client sends this on a second connection, as another writer does.
        client.hset(key, "meta", "other")
        pipe.multi()
        pipe.hset(key, "meta", "mine")
        lost = _watch_refusal(pipe.execute)
    return seen, lost, client.hget(key, "meta"), client.delete(key)


def hscan_bytes(client: valkey.Valkey) -> tuple[Any, ...]:
    """`HSCAN` with `NEVER_DECODE` gives the bytes of a binary value to a decoding client (#4668)."""
    key = _key("hscan_bytes", "hash")
    written = client.hset(key, mapping={"1": BINARY_VALUE, "2": BINARY_VALUE})
    cursor, fields = client.execute_command(
        "HSCAN", key, 0, "COUNT", SCAN_COUNT, **{NEVER_DECODE: True}
    )
    field = client.execute_command("HGET", key, "1", **{NEVER_DECODE: True})
    return written, cursor, sorted(fields.items()), field, client.delete(key)


def rename_hash_ttl(client: valkey.Valkey) -> tuple[Any, ...]:
    """`RENAME` of a temporary hash with a TTL replaces a hash that exists and keeps a TTL (#4668)."""
    key, temporary = _key("rename_hash_ttl", "hash"), _key("rename_hash_ttl", "next")
    client.hset(key, mapping={"1": "old", "2": "old"})
    client.hset(temporary, mapping={"1": "new"})
    client.expire(temporary, TEMPORARY_TTL_SECONDS)
    renamed = client.rename(temporary, key)
    ttl = client.ttl(key)
    return (
        renamed,
        0 < ttl <= TEMPORARY_TTL_SECONDS,
        client.hgetall(key),
        client.exists(temporary),
        client.delete(key),
    )


def expire_hdel_unlink(client: valkey.Valkey) -> tuple[Any, ...]:
    """`EXPIRE` sets a TTL, `HDEL` removes the fields that exist, `UNLINK` counts its keys (#4668)."""
    key, other = _key("expire_hdel_unlink", "hash"), _key("expire_hdel_unlink", "other")
    client.hset(key, mapping={"meta": "m", "1": "a", "2": "b"})
    client.set(other, "x")
    expired = client.expire(key, TTL_SECONDS)
    ttl = client.ttl(key)
    removed = client.hdel(key, "2", "3")
    fields = sorted(client.hkeys(key))
    unlinked = client.unlink(key, other, _key("expire_hdel_unlink", "missing"))
    return expired, 0 < ttl <= TTL_SECONDS, removed, fields, unlinked, client.exists(key)


@dataclass(frozen=True)
class ValkeyScenario:
    """A scenario: its name and its calls."""

    name: str
    run: Callable[[valkey.Valkey], tuple[Any, ...]]


SCENARIOS: tuple[ValkeyScenario, ...] = (
    ValkeyScenario("set_nx_ex", set_nx_ex),
    ValkeyScenario("set_exat", set_exat),
    ValkeyScenario("hincrby", hincrby),
    ValkeyScenario("zadd_and_trim", zadd_and_trim),
    ValkeyScenario("lock_lifecycle", lock_lifecycle),
    ValkeyScenario("lock_lost", lock_lost),
    ValkeyScenario("registered_script", registered_script),
    ValkeyScenario("eval", eval_through_the_project_client),
    ValkeyScenario("watch_lost", watch_lost),
    ValkeyScenario("hscan_bytes", hscan_bytes),
    ValkeyScenario("rename_hash_ttl", rename_hash_ttl),
    ValkeyScenario("expire_hdel_unlink", expire_hdel_unlink),
)
