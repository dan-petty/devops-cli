"""Tests for terminal ASCII sparklines, gauges, and LogQL syntax highlighting."""

from __future__ import annotations

from rich.text import Text

from devops_cli.ui.highlighters import LogQLHighlighter
from devops_cli.ui.sparklines import render_gauge, render_sparkline


def test_render_sparkline_empty() -> None:
    """An empty sequence renders a placeholder dash."""
    assert render_sparkline([]) == "—"


def test_render_sparkline_identical_values() -> None:
    """Identical values render uniform baseline bars."""
    res = render_sparkline([5.0, 5.0, 5.0, 5.0])
    assert len(res) == 4
    assert len(set(res)) == 1


def test_render_sparkline_progression() -> None:
    """Ascending series renders ascending Unicode block levels."""
    series = [0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0]
    res = render_sparkline(series)
    assert res == " ▂▃▄▅▆▇█"


def test_render_sparkline_width_truncation() -> None:
    """Sparkline honors requested maximum width by keeping recent samples."""
    series = [float(i) for i in range(20)]
    res = render_sparkline(series, width=8)
    assert len(res) == 8


def test_render_gauge_zero_half_full() -> None:
    """Gauge renders clamped percentages and filled blocks."""
    gauge_zero = render_gauge(0.0, width=10)
    assert "░" * 10 in gauge_zero
    assert "0.0%" in gauge_zero

    gauge_half = render_gauge(0.5, width=10)
    assert "█" * 5 + "░" * 5 in gauge_half
    assert "50.0%" in gauge_half

    gauge_full = render_gauge(1.0, width=10)
    assert "█" * 10 in gauge_full
    assert "100.0%" in gauge_full


def test_render_gauge_clamping() -> None:
    """Ratios below 0 or above 1 are clamped within 0% to 100%."""
    assert "0.0%" in render_gauge(-0.5, width=10)
    assert "100.0%" in render_gauge(1.5, width=10)


def test_logql_highlighter_spans() -> None:
    """LogQL query text is parsed into syntax-highlighted styles."""
    highlighter = LogQLHighlighter()
    text = highlighter('{app="gateway", env="staging"} |= "error" | json')
    assert isinstance(text, Text)

    styles = {span.style for span in text.spans}
    assert "brace" in styles
    assert "str" in styles
    assert "tag" in styles
    assert "call" in styles or "logql.operator" in styles or "operator" in styles
