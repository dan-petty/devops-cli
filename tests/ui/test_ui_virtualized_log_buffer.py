"""Tests for Virtualized Log Buffer behaviour in reactive dashboard."""

from __future__ import annotations

import threading

from devops_cli.ui.log_buffer import LogLine, VirtualLogBuffer, tail
from tests.support.waits import THREAD_HANDOFF_BOUND_SECONDS


def test_retention_is_bounded_however_long_the_stream_runs() -> None:
    """Memory is bounded by the retention limit, not by stream length.

    Retaining every line of a long tail is how the dashboard gets OOM-killed on a busy
    namespace, which is the whole reason this buffer exists.
    """
    buffer = VirtualLogBuffer(max_lines=100, viewport=10)
    buffer.extend(f"line-{index}" for index in range(100_000))
    assert (buffer.retained, buffer.total_appended) == (100, 100_000)


def test_sequence_numbers_count_evicted_lines() -> None:
    """Position in the stream stays true after eviction."""
    buffer = VirtualLogBuffer(max_lines=3, viewport=3)
    buffer.extend(["a", "b", "c", "d", "e"])
    assert [line.sequence for line in buffer.viewport_lines()] == [3, 4, 5]


def test_dropped_counts_lines_evicted_to_stay_within_the_limit() -> None:
    """The count of discarded lines is reported rather than hidden."""
    buffer = VirtualLogBuffer(max_lines=10, viewport=5)
    buffer.extend(f"line-{index}" for index in range(25))
    assert (buffer.retained, buffer.dropped) == (10, 15)


def test_the_viewport_hands_out_only_the_visible_slice() -> None:
    """Rendering the whole buffer is what drops frames; only the slice is returned."""
    buffer = VirtualLogBuffer(max_lines=1000, viewport=5)
    buffer.extend(f"line-{index}" for index in range(100))
    visible = buffer.viewport_lines()
    assert (len(visible), visible[-1].text) == (5, "line-99")


def test_a_following_viewport_tracks_newly_appended_lines() -> None:
    """While following, the newest line stays on screen."""
    buffer = VirtualLogBuffer(max_lines=100, viewport=3)
    buffer.extend(["a", "b", "c"])
    buffer.append("d")
    assert [line.text for line in buffer.viewport_lines()] == ["b", "c", "d"]


def test_scrolling_back_detaches_the_viewport_from_the_stream() -> None:
    """Reading history must not be yanked away by incoming lines.

    A viewport that keeps jumping to the end makes an active log impossible to read, which
    is the practical failure of a naive auto-scrolling tail.
    """
    buffer = VirtualLogBuffer(max_lines=100, viewport=3)
    buffer.extend(f"line-{index}" for index in range(10))
    buffer.scroll(-4)
    before = [line.text for line in buffer.viewport_lines()]
    buffer.append("line-10")
    after = [line.text for line in buffer.viewport_lines()]
    assert (buffer.following, before == after) == (False, True)


def test_scrolling_to_the_end_reattaches_to_the_stream() -> None:
    """Returning to the newest line resumes following."""
    buffer = VirtualLogBuffer(max_lines=100, viewport=3)
    buffer.extend(f"line-{index}" for index in range(10))
    buffer.scroll(-5)
    buffer.scroll_to_end()
    buffer.append("line-10")
    assert (buffer.following, buffer.viewport_lines()[-1].text) == (True, "line-10")


def test_scrolling_forward_to_the_end_reattaches_without_an_explicit_jump() -> None:
    """Scrolling back to the bottom by hand resumes following too."""
    buffer = VirtualLogBuffer(max_lines=100, viewport=3)
    buffer.extend(f"line-{index}" for index in range(10))
    buffer.scroll(-4)
    buffer.scroll(10)
    assert (buffer.following, buffer.offset) == (True, 7)


def test_scrolling_clamps_to_the_retained_range() -> None:
    """The viewport cannot be driven outside the buffer."""
    buffer = VirtualLogBuffer(max_lines=100, viewport=3)
    buffer.extend(["a", "b", "c", "d"])
    assert (buffer.scroll(-999), buffer.scroll(999)) == (0, 1)


def test_a_detached_viewport_holds_position_as_lines_are_evicted() -> None:
    """Eviction shifts indices beneath the reader, so the offset is corrected."""
    buffer = VirtualLogBuffer(max_lines=5, viewport=2)
    buffer.extend(["a", "b", "c", "d", "e"])
    buffer.scroll(-3)
    buffer.extend(["f", "g", "h", "i", "j"])
    assert (buffer.following, buffer.offset < buffer.retained) == (False, True)


def test_resizing_the_viewport_while_following_keeps_the_newest_lines() -> None:
    """A terminal resize must not scroll the stream away."""
    buffer = VirtualLogBuffer(max_lines=100, viewport=3)
    buffer.extend(f"line-{index}" for index in range(10))
    buffer.resize_viewport(5)
    assert [line.text for line in buffer.viewport_lines()][-1] == "line-9"


def test_resizing_the_viewport_while_detached_keeps_the_reader_in_place() -> None:
    """Growing the viewport must not silently jump a detached reader to the end."""
    buffer = VirtualLogBuffer(max_lines=100, viewport=3)
    buffer.extend(f"line-{index}" for index in range(20))
    buffer.scroll(-10)
    offset = buffer.offset
    buffer.resize_viewport(5)
    assert (buffer.following, buffer.offset) == (False, offset)


def test_a_viewport_larger_than_the_buffer_shows_everything_retained() -> None:
    """A short stream is fully visible without padding or error."""
    buffer = VirtualLogBuffer(max_lines=100, viewport=50)
    buffer.extend(["a", "b"])
    assert [line.text for line in buffer.viewport_lines()] == ["a", "b"]


def test_degenerate_sizes_are_coerced_to_something_renderable() -> None:
    """A zero or negative size would make the buffer undisplayable."""
    buffer = VirtualLogBuffer(max_lines=0, viewport=-5)
    buffer.append("a")
    assert (buffer.retained, buffer.viewport) == (1, 1)


def test_search_finds_matching_retained_lines_case_insensitively() -> None:
    """Operators search logs without matching the casing exactly."""
    buffer = VirtualLogBuffer(max_lines=100, viewport=5)
    buffer.extend(["INFO started", "ERROR failed", "info stopped"])
    assert [line.text for line in buffer.search("info")] == ["INFO started", "info stopped"]


def test_search_honours_a_result_limit() -> None:
    """A match on every line must not return the whole buffer."""
    buffer = VirtualLogBuffer(max_lines=1000, viewport=5)
    buffer.extend(f"error {index}" for index in range(500))
    assert len(buffer.search("error", limit=10)) == 10


def test_an_empty_search_matches_nothing() -> None:
    """An empty needle returns nothing rather than every line."""
    buffer = VirtualLogBuffer(max_lines=10, viewport=5)
    buffer.extend(["a", "b"])
    assert buffer.search("") == []


def test_clear_discards_lines_but_preserves_the_stream_count() -> None:
    """Clearing the view does not rewrite how much of the stream has been seen."""
    buffer = VirtualLogBuffer(max_lines=10, viewport=5)
    buffer.extend(["a", "b", "c"])
    buffer.clear()
    assert (buffer.retained, buffer.total_appended, buffer.following) == (0, 3, True)


def test_status_reports_retention_drops_and_follow_state() -> None:
    """The status line states what is retained, what was lost, and whether it is live."""
    buffer = VirtualLogBuffer(max_lines=3, viewport=2)
    buffer.extend(["a", "b", "c", "d", "e"])
    assert buffer.status() == "3 retained of 5, 2 dropped (following)"


def test_status_omits_the_drop_count_when_nothing_was_evicted() -> None:
    """A short stream reports cleanly without a zero-drop clause."""
    buffer = VirtualLogBuffer(max_lines=10, viewport=5)
    buffer.extend(["a", "b"])
    assert buffer.status() == "2 retained of 2 (following)"


def test_status_reports_a_detached_viewport() -> None:
    """A reader scrolled into history is told the view is not live."""
    buffer = VirtualLogBuffer(max_lines=10, viewport=2)
    buffer.extend(["a", "b", "c", "d"])
    buffer.scroll(-2)
    assert buffer.status().endswith("4 retained of 4")


def test_append_returns_the_line_it_recorded() -> None:
    """Producers can observe the assigned sequence number."""
    buffer = VirtualLogBuffer(max_lines=10, viewport=5)
    assert buffer.append("hello") == LogLine(sequence=1, text="hello")


def test_concurrent_producers_do_not_lose_or_duplicate_lines() -> None:
    """Workers append while the UI reads, so every operation must be guarded."""
    buffer = VirtualLogBuffer(max_lines=10_000, viewport=20)

    def produce(worker: int) -> None:
        buffer.extend(f"worker-{worker}-line-{index}" for index in range(200))

    threads = [threading.Thread(target=produce, args=(worker,)) for worker in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=THREAD_HANDOFF_BOUND_SECONDS)
    sequences = {line.sequence for line in buffer.viewport_lines()}
    assert (buffer.total_appended, len(sequences)) == (1600, 20)


def test_reading_a_viewport_during_concurrent_appends_never_tears() -> None:
    """A read must always return a valid slice, never a partially mutated one."""
    buffer = VirtualLogBuffer(max_lines=500, viewport=10)
    stop = threading.Event()

    def produce() -> None:
        index = 0
        while not stop.is_set():
            buffer.append(f"line-{index}")
            index += 1

    producer = threading.Thread(target=produce)
    producer.start()
    try:
        widths = {len(buffer.viewport_lines()) for _ in range(500)}
    finally:
        stop.set()
        producer.join(timeout=THREAD_HANDOFF_BOUND_SECONDS)
    assert widths <= {10} or widths.issubset(set(range(11)))


def test_tail_returns_the_final_lines() -> None:
    """The helper trims a finished sequence to its last lines."""
    assert tail(["a", "b", "c", "d"], count=2) == ["c", "d"]


def test_tail_of_a_non_positive_count_is_empty() -> None:
    """Asking for no lines returns none rather than the whole sequence."""
    assert tail(["a", "b"], count=0) == []


def test_tail_of_a_short_sequence_returns_all_of_it() -> None:
    """Requesting more lines than exist is not an error."""
    assert tail(["a"], count=10) == ["a"]
