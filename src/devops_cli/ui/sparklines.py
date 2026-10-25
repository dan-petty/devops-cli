"""Terminal ASCII sparklines and progress gauges for performance metrics."""

from __future__ import annotations

from collections.abc import Sequence

_SPARK_TICKS = (" ", "▂", "▃", "▄", "▅", "▆", "▇", "█")


def render_sparkline(values: Sequence[float], width: int | None = None) -> str:
    """Render a sequence of numerical values as an ASCII sparkline."""
    if not values:
        return "—"

    samples = list(values)
    if width is not None and width > 0 and len(samples) > width:
        samples = samples[-width:]

    min_val = min(samples)
    max_val = max(samples)

    if max_val == min_val:
        return _SPARK_TICKS[0] * len(samples)

    span = max_val - min_val
    chars: list[str] = []
    num_ticks = len(_SPARK_TICKS)
    for v in samples:
        idx = int((v - min_val) / span * (num_ticks - 1))
        clamped_idx = max(0, min(num_ticks - 1, idx))
        chars.append(_SPARK_TICKS[clamped_idx])

    return "".join(chars)


def render_gauge(ratio: float, width: int = 10) -> str:
    """Render a ratio as an ASCII progress gauge with a percentage label."""
    clamped = max(0.0, min(1.0, ratio))
    filled = round(clamped * width)
    empty = max(0, width - filled)
    pct = clamped * 100.0
    return f"[{'█' * filled}{'░' * empty}] {pct:5.1f}%"


__all__ = ["render_gauge", "render_sparkline"]
