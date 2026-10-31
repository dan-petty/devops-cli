"""The shared tracer fixture (#1310)."""

from __future__ import annotations

import os
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest


@pytest.fixture
def tracer(config: Callable[..., Path]) -> Iterator[Any]:
    """An enabled tracer with a clean span buffer and no trace context inherited from the run."""
    from devops_cli.config.constants import (
        CONST_TRACEPARENT_ENV_VAR,
        CONST_TRACEPARENT_HEADER,
    )
    from devops_cli.telemetry.tracer import clear_span_buffer, get_tracer, reset_tracer

    config(telemetry={"enabled": True})
    environment = dict(os.environ)
    environment.pop(CONST_TRACEPARENT_ENV_VAR, None)
    environment.pop(CONST_TRACEPARENT_HEADER, None)
    with patch.dict(os.environ, environment, clear=True):
        reset_tracer()
        clear_span_buffer()
        yield get_tracer()
        clear_span_buffer()
        reset_tracer()
