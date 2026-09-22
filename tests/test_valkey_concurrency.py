"""Test suite for Valkey connection safety under concurrency and large batches."""

from __future__ import annotations

import threading
import time
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from devops_cli.config.defaults import (
    DEFAULT_VALKEY_PIPELINE_CHUNK_BYTES,
    DEFAULT_VALKEY_PIPELINE_CHUNK_COMMANDS,
)
from devops_cli.valkey.client import ValkeyClient, _chunk_commands


@pytest.fixture
def client() -> ValkeyClient:
    """Provide a client with a stubbed socket so nothing touches the network."""
    instance = ValkeyClient(host="127.0.0.1", port=6379)
    instance._sock = MagicMock()
    instance._reader = MagicMock()
    return instance


# =============================================================================
# Batch Chunking
# =============================================================================


def test_a_small_batch_is_sent_as_one_chunk() -> None:
    """Chunking must not add round trips to the common case."""
    commands = [("GET", f"key-{index}") for index in range(10)]
    assert len(_chunk_commands(commands)) == 1


def test_a_batch_is_split_on_the_command_count() -> None:
    """A million tiny commands is one of the two shapes of unbounded memory."""
    commands = [
        ("GET", f"key-{index}") for index in range(DEFAULT_VALKEY_PIPELINE_CHUNK_COMMANDS * 2 + 5)
    ]
    chunks = _chunk_commands(commands)
    assert (len(chunks), sum(len(chunk) for chunk in chunks)) == (3, len(commands))


def test_a_batch_is_split_on_the_byte_budget() -> None:
    """A handful of very large values is the other shape, and the count limit misses it."""
    value = "x" * (DEFAULT_VALKEY_PIPELINE_CHUNK_BYTES // 3)
    commands = [("SET", f"key-{index}", value) for index in range(4)]
    assert len(_chunk_commands(commands)) > 1


def test_every_command_survives_chunking() -> None:
    """Splitting must not drop or duplicate a command; replies are matched by order."""
    commands = [("GET", f"key-{index}") for index in range(2500)]
    flattened = [item for chunk in _chunk_commands(commands) for item in chunk]
    assert flattened == commands


def test_a_single_oversized_command_forms_its_own_chunk() -> None:
    """Splitting one command would corrupt the protocol, so the budget is a target."""
    huge = "x" * (DEFAULT_VALKEY_PIPELINE_CHUNK_BYTES * 2)
    chunks = _chunk_commands([("SET", "key", huge)])
    assert (len(chunks), len(chunks[0])) == (1, 1)


def test_an_empty_batch_produces_no_chunks() -> None:
    """Nothing to send is not a chunk."""
    assert _chunk_commands([]) == []


def test_a_large_pipeline_is_written_in_several_sends(client: ValkeyClient) -> None:
    """The point of chunking is that no single write buffers the whole batch."""
    commands = [
        ("GET", f"key-{index}") for index in range(DEFAULT_VALKEY_PIPELINE_CHUNK_COMMANDS * 2)
    ]
    with patch("devops_cli.valkey.client.parse_resp", return_value="OK"):
        replies = client.pipeline(commands)
    assert (len(replies), client._sock.sendall.call_count) == (len(commands), 2)


def test_a_pipeline_returns_one_reply_per_command(client: ValkeyClient) -> None:
    """Replies are matched to commands by position, so the counts must agree."""
    commands = [("GET", f"key-{index}") for index in range(5)]
    with patch("devops_cli.valkey.client.parse_resp", side_effect=list(range(5))):
        assert client.pipeline(commands) == [0, 1, 2, 3, 4]


def test_an_empty_pipeline_sends_nothing(client: ValkeyClient) -> None:
    """An empty batch must not open a connection or write."""
    assert (client.pipeline([]), client._sock.sendall.call_count) == ([], 0)


# =============================================================================
# Connection Safety
# =============================================================================


def test_concurrent_commands_do_not_interleave_on_the_connection(
    client: ValkeyClient,
) -> None:
    """RESP has no request identifiers: replies are matched to commands purely by order.

    Two threads sharing a connection therefore read each other's replies -- silently, as
    plausible-looking data for the wrong key. This fails if any thread reads while another
    is mid-request, which is exactly the corruption the connection lock prevents.
    """
    in_flight = 0
    overlaps = 0
    guard = threading.Lock()

    def sendall(_: Any) -> None:
        nonlocal in_flight, overlaps
        with guard:
            in_flight += 1
            if in_flight > 1:
                overlaps += 1
        # Yield between the write and the read. A real network round trip takes far
        # longer than a mocked one, so without this the window an unlocked client is
        # vulnerable in is too narrow for the test to ever observe it -- and the test
        # would pass against the very defect it exists to catch.
        time.sleep(0.001)

    def parse(_: Any) -> str:
        nonlocal in_flight, overlaps
        with guard:
            if in_flight > 1:
                overlaps += 1
            in_flight -= 1
        return "OK"

    client._sock.sendall.side_effect = sendall

    # Patched once, outside the threads: mock.patch mutates module globals, so patching
    # inside each worker would have them racing to install and remove the same attribute.
    with patch("devops_cli.valkey.client.parse_resp", side_effect=parse):

        def worker() -> None:
            for _ in range(25):
                client.execute("GET", "key")

        threads = [threading.Thread(target=worker) for _ in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)

    assert overlaps == 0


def test_the_connection_lock_is_reentrant(client: ValkeyClient) -> None:
    """The error paths call close() from inside a held section.

    A non-reentrant lock would deadlock on the first dropped connection rather than
    raising the connection error the caller is waiting for.
    """
    client._sock.sendall.side_effect = BrokenPipeError("connection dropped")
    from devops_cli.exceptions.valkey import ValkeyConnectionError

    with pytest.raises(ValkeyConnectionError):
        client.execute("GET", "key")
    assert client._sock is None


def test_a_timeout_closes_the_connection_rather_than_reusing_it(
    client: ValkeyClient,
) -> None:
    """A half-read reply left on the socket would be returned to the next caller."""
    from devops_cli.exceptions.valkey import ValkeyTimeoutError

    client._sock.sendall.side_effect = TimeoutError("timed out")
    with pytest.raises(ValkeyTimeoutError):
        client.execute("GET", "key")
    assert client._sock is None
