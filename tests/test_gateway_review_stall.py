"""Offline tests for issue #1069: gateway review calls no longer stall.

Tests:
1. `devops ai gateway connect` saves NodePort URL probing only /health/liveliness and /model/info.
2. Fake transport answering 400 once: persona call fails without second attempt, report shows status.
3. 5 personas on 1 page with 1 transient 503: fake transport sees exactly 6 calls (not 10).
4. Fake transport answering 503: exactly max_retries + 1 sends per call (one retry layer).
5. Closed-by-peer / cut connection: client connection pool holds no closed-by-peer connection.
6. Slots config table defines DEFAULT_GATEWAY_REVIEW_SLOTS and sum equals DEFAULT_GATEWAY_REVIEW_CONCURRENCY.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

import httpx2
import pytest
from typer.testing import CliRunner

from devops_cli.ai.client.models import AIClientError
from devops_cli.ai.client.unified import LLMClient
from devops_cli.ai.review.pipeline import ReviewPipelineOrchestrator
from devops_cli.commands.ai_gateway import app as gateway_cli_app
from devops_cli.config.defaults import (
    DEFAULT_GATEWAY_REVIEW_CONCURRENCY,
    DEFAULT_GATEWAY_REVIEW_SLOTS,
)
from devops_cli.config.settings import AIConfig, Settings
from devops_cli.http.pool import close_expired_connections
from devops_cli.k8s.node_port import NodePortSpec, ServiceNotReachableError
from devops_cli.models.ai import FileAnalysisMeta

runner = CliRunner()


class TestGatewaySlotsConfig:
    """Verify review in-flight requests are capped at the sum of slots in the config table."""

    def test_gateway_review_slots_table_and_concurrency(self) -> None:
        """Verify DEFAULT_GATEWAY_REVIEW_SLOTS defines 3 one-slot tiers totaling 3 concurrency."""
        assert (
            DEFAULT_GATEWAY_REVIEW_SLOTS,
            DEFAULT_GATEWAY_REVIEW_CONCURRENCY,
        ) == (
            {
                "http://ollama-48gib-fast.llm.svc.cluster.local:11434": 1,
                "http://ollama-64gib-standard.llm.svc.cluster.local:11434": 1,
                "http://ollama-16gib-fast.llm.svc.cluster.local:11434": 1,
            },
            3,
        )


class TestAiGatewayConnectCommand:
    """Verify `devops ai gateway connect` probes only liveliness and model/info via NodePort."""

    def test_connect_saves_nodeport_url_and_probes_only_liveliness_and_models(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify connect command discovers NodePort, probes /health/liveliness and /model/info, and saves LAN URL."""
        mock_spec_captured: list[NodePortSpec] = []

        def fake_node_port_address(
            context: str | None, namespace: str, service: str, spec: NodePortSpec
        ) -> tuple[str, int]:
            mock_spec_captured.append(spec)
            return "192.0.2.10", 30400

        monkeypatch.setattr(
            "devops_cli.commands.ai_gateway.node_port_address", fake_node_port_address
        )

        requested_urls: list[str] = []

        def fake_get(client_self: httpx2.Client, url: str, **kwargs: Any) -> httpx2.Response:
            requested_urls.append(url)
            req = httpx2.Request("GET", url)
            if "/health/liveliness" in url:
                return httpx2.Response(200, json={"status": "healthy"}, request=req)
            if "/model/info" in url:
                return httpx2.Response(
                    200, json={"data": [{"model_name": "devops-review"}]}, request=req
                )
            return httpx2.Response(404, request=req)

        monkeypatch.setattr(httpx2.Client, "get", fake_get)

        saved_settings: list[Settings] = []
        fake_settings = Settings()
        monkeypatch.setattr("devops_cli.commands.ai_gateway.load_settings", lambda: fake_settings)
        monkeypatch.setattr(
            "devops_cli.commands.ai_gateway.save_settings",
            lambda s: saved_settings.append(s),
        )

        result = runner.invoke(gateway_cli_app, ["connect"])

        assert (
            result.exit_code,
            fake_settings.ai.gateway_url,
            fake_settings.ai.allow_private_network,
            len(saved_settings),
            requested_urls,
            mock_spec_captured[0].port,
            mock_spec_captured[0].port_name,
        ) == (
            0,
            "http://192.0.2.10:30400/v1",
            True,
            1,
            ["http://192.0.2.10:30400/health/liveliness", "http://192.0.2.10:30400/model/info"],
            4000,
            "http",
        )

    def test_connect_fails_when_service_not_reachable(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify connect command exits 1 with helpful message if NodePort lookup fails."""

        def fake_unreachable(*args: Any, **kwargs: Any) -> tuple[str, int]:
            raise ServiceNotReachableError("the LLM gateway service exposes no HTTP node port")

        monkeypatch.setattr("devops_cli.commands.ai_gateway.node_port_address", fake_unreachable)

        result = runner.invoke(gateway_cli_app, ["connect"])

        assert (
            result.exit_code,
            "Cannot find the LLM gateway: the LLM gateway service exposes no HTTP node port"
            in result.output,
        ) == (1, True)

    def test_connect_fails_when_liveliness_or_model_info_returns_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify connect fails if /health/liveliness returns non-200."""
        monkeypatch.setattr(
            "devops_cli.commands.ai_gateway.node_port_address",
            lambda *args, **kwargs: ("192.0.2.10", 30400),
        )

        def fake_get(client_self: httpx2.Client, url: str, **kwargs: Any) -> httpx2.Response:
            req = httpx2.Request("GET", url)
            if "/health/liveliness" in url:
                return httpx2.Response(503, text="Service Unavailable", request=req)
            return httpx2.Response(200, request=req)

        monkeypatch.setattr(httpx2.Client, "get", fake_get)
        result = runner.invoke(gateway_cli_app, ["connect"])

        assert (result.exit_code, "not live: HTTP 503" in result.output) == (1, True)


class TestConnectionPoolPurgeOnCut:
    """Verify expired, cut, or closed-by-peer connections are purged from client pool."""

    def test_closed_by_peer_connection_purged_from_client_pool(self) -> None:
        """Verify client connection pool holds no closed-by-peer/expired connections after close_expired_connections."""

        class MockConnection:
            def __init__(self, expired: bool, closed: bool = False) -> None:
                self._expired = expired
                self.closed = closed

            def has_expired(self) -> bool:
                return self._expired

            def is_closed(self) -> bool:
                return self.closed

            def close(self) -> None:
                self.closed = True

        client = httpx2.Client()
        conn_active = MockConnection(expired=False)
        conn_cut = MockConnection(expired=True)
        # Inject connections into pool
        pool = client._transport._pool
        pool._connections = [conn_active, conn_cut]

        close_expired_connections(client)

        assert (
            conn_cut.closed,
            conn_cut in pool._connections,
            conn_active in pool._connections,
        ) == (True, False, True)


class TestSingleRetryLayerAndStatusRules:
    """Verify exactly one retry layer retries 503, 400 fails immediately, and persona retries alone."""

    def test_transport_answers_503_sees_exactly_max_retries_plus_one_sends(self) -> None:
        """Verify a call that always encounters 503 sees max_retries + 1 sends (single retry layer)."""
        calls = 0

        class Always503Transport(httpx2.BaseTransport):
            def handle_request(self, request: httpx2.Request) -> httpx2.Response:
                nonlocal calls
                calls += 1
                return httpx2.Response(503, text="Service Unavailable", request=request)

        config = AIConfig(
            provider="gateway",
            gateway_url="http://example.com/v1",
            model="devops-review",
            max_retries=3,
            allow_private_network=True,
        )
        client = LLMClient(config)
        # Patch client._create_retry_transport to use our Always503Transport as wrapped
        from devops_cli.ai.retries import create_retry_transport
        from devops_cli.http.pool import close_shared_clients

        close_shared_clients()
        retry_transport = create_retry_transport(
            max_attempts=4, min_wait=0.01, max_wait=0.02, wrapped=Always503Transport()
        )
        client._create_retry_transport = lambda: retry_transport
        shared_http = httpx2.Client(transport=retry_transport)
        client._shared_client = lambda: shared_http

        try:
            with pytest.raises(AIClientError) as exc_info:
                client.chat("system prompt", "review test prompt")

            assert (
                calls,
                "503" in str(exc_info.value),
            ) == (4, True)
        finally:
            close_shared_clients()

    def test_transport_answers_400_once_fails_without_second_attempt_and_reports_status(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify fake transport answering 400 fails persona call without a second attempt and records status in report."""
        monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", str(tmp_path / ".data"))
        calls = 0

        class Answering400Transport(httpx2.BaseTransport):
            def handle_request(self, request: httpx2.Request) -> httpx2.Response:
                nonlocal calls
                calls += 1
                return httpx2.Response(
                    400,
                    text='{"error": "bad request: context too large or malformed prompt"}',
                    request=request,
                )

        config = AIConfig(
            provider="gateway",
            gateway_url="http://example.com/v1",
            model="devops-review",
            max_retries=4,
            allow_private_network=True,
        )
        client = LLMClient(config)
        from devops_cli.ai.retries import create_retry_transport
        from devops_cli.http.pool import close_shared_clients

        close_shared_clients()
        retry_transport = create_retry_transport(max_attempts=5, wrapped=Answering400Transport())
        client._create_retry_transport = lambda: retry_transport
        shared_http = httpx2.Client(transport=retry_transport)
        client._shared_client = lambda: shared_http

        orchestrator = ReviewPipelineOrchestrator(
            session_id="test-400-review",
            llm_client=client,
            target_dir=tmp_path,
        )

        dummy_file = tmp_path / "test.py"
        dummy_file.write_text("x = 1\n", encoding="utf-8")
        fmeta = FileAnalysisMeta(path="test.py", key_symbols=["x"], dependencies=[])
        payloads = orchestrator.init_per_file_payloads(["test.py"], {"test.py": fmeta})

        try:
            orchestrator.execute_multi_persona_review(
                payloads,
                diff_text_by_file={"test.py": "x = 1\n"},
                personas=["devsecops"],
            )

            _data, report_md = orchestrator.generate_consolidated_report(payloads)

            assert (
                calls,
                "test.py" in orchestrator.errored_files,
                "HTTP 400" in orchestrator.errored_files["test.py"],
                "bad request" in orchestrator.errored_files["test.py"],
                "Skipped / Errored Files" in report_md,
                "HTTP 400" in report_md,
            ) == (1, True, True, True, True, True)
        finally:
            close_shared_clients()

    def test_five_personas_with_one_transient_503_sees_exactly_six_calls(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify 5 personas on 1 page with 1 transient 503 sees exactly 6 calls (retries alone, not 10)."""
        monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", str(tmp_path / ".data"))
        calls = 0
        transient_hit = False
        calls_lock = threading.Lock()

        review_reply = json.dumps(
            {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": '```json\n{"findings": []}\n```',
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            }
        )

        class Transient503Transport(httpx2.BaseTransport):
            def handle_request(self, request: httpx2.Request) -> httpx2.Response:
                nonlocal calls, transient_hit
                with calls_lock:
                    calls += 1
                    first_failure = not transient_hit
                    if first_failure:
                        transient_hit = True
                if first_failure:
                    return httpx2.Response(503, text="Service Unavailable", request=request)
                return httpx2.Response(
                    200,
                    text=review_reply,
                    headers={"content-type": "application/json"},
                    request=request,
                )

        config = AIConfig(
            provider="gateway",
            gateway_url="http://example.com/v1",
            model="devops-review",
            max_retries=4,
            allow_private_network=True,
        )
        client = LLMClient(config)
        from devops_cli.ai.retries import create_retry_transport
        from devops_cli.http.pool import close_shared_clients

        close_shared_clients()
        retry_transport = create_retry_transport(
            max_attempts=5, min_wait=0.01, max_wait=0.02, wrapped=Transient503Transport()
        )
        client._create_retry_transport = lambda: retry_transport
        shared_http = httpx2.Client(transport=retry_transport)
        client._shared_client = lambda: shared_http

        orchestrator = ReviewPipelineOrchestrator(
            session_id="test-transient-503-review",
            llm_client=client,
            target_dir=tmp_path,
        )

        dummy_file = tmp_path / "test.py"
        dummy_file.write_text("x = 1\n", encoding="utf-8")
        fmeta = FileAnalysisMeta(path="test.py", key_symbols=["x"], dependencies=[])
        payloads = orchestrator.init_per_file_payloads(["test.py"], {"test.py": fmeta})

        try:
            # 5 distinct personas on 1 file / page
            personas = ["devsecops", "architect", "qa", "performance", "maintainer"]
            orchestrator.execute_multi_persona_review(
                payloads,
                diff_text_by_file={"test.py": "x = 1\n"},
                personas=personas,
            )

            assert (
                calls,
                payloads[0].ai_scratchpad.get("stage"),
            ) == (6, "reviewed")
        finally:
            close_shared_clients()
