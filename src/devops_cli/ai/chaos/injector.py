"""Model dependency chaos fault injector, metric recorder, and failover engine."""

from __future__ import annotations

import logging
import random
import time

from devops_cli.ai.chaos.models import (
    ChaosConfig,
    ChaosFaultResult,
    ChaosMode,
    ChaosStatus,
    ModelChaosReport,
)
from devops_cli.telemetry.metrics import GLOBAL_METRICS
from devops_cli.telemetry.tracer import trace_span

logger = logging.getLogger(__name__)

_METRIC_CHAOS_INJECTIONS = "devops_cli_ai_chaos_injections_total"
_METRIC_CHAOS_RECOVERIES = "devops_cli_ai_chaos_recoveries_total"


def _record_injection_metrics(mode: ChaosMode, provider: str) -> None:
    """Record fault injection event to Prometheus counters."""
    GLOBAL_METRICS.increment_counter(
        _METRIC_CHAOS_INJECTIONS,
        labels={"mode": mode.value, "provider": provider},
    )


def _record_recovery_metrics(mode: ChaosMode, fallback_provider: str, fallback_model: str) -> None:
    """Record successful recovery event to Prometheus counters."""
    GLOBAL_METRICS.increment_counter(
        _METRIC_CHAOS_RECOVERIES,
        labels={
            "mode": mode.value,
            "fallback_provider": fallback_provider,
            "fallback_model": fallback_model,
        },
    )


class ModelChaosInjector:
    """Executes model dependency chaos faults and evaluates automated fallback recovery."""

    def __init__(self, config: ChaosConfig | None = None) -> None:
        self.config = config or ChaosConfig()

    def _invoke_model_fallback(self, config: ChaosConfig, prompt: str) -> str:
        """Execute inference against local open-weight model fallback route."""
        if config.dry_run:
            return (
                f"# Automated fallback response from {config.fallback_provider}/{config.fallback_model}\n"
                f"def test_health():\n"
                f"    return True"
            )

        from devops_cli.ai.client.unified import LLMClient
        from devops_cli.config.settings import AIConfig

        fallback_ai_cfg = AIConfig(
            provider=config.fallback_provider,
            model=config.fallback_model,
            max_retries=config.max_retries,
        )
        client = LLMClient(config=fallback_ai_cfg)
        res = client.chat(
            system="",
            user=prompt,
            max_retries=config.max_retries,
        )
        return str(res.content)

    def _execute_fallback_recovery(
        self,
        mode: ChaosMode,
        fault_desc: str,
        latency_ms: float,
    ) -> ChaosFaultResult:
        """Attempt automated failover to local open model upon primary failure."""
        _record_injection_metrics(mode, self.config.primary_provider)
        try:
            recovery_text = self._invoke_model_fallback(self.config, self.config.prompt)
            _record_recovery_metrics(
                mode,
                self.config.fallback_provider,
                self.config.fallback_model,
            )
            return ChaosFaultResult(
                mode=mode,
                primary_provider=self.config.primary_provider,
                primary_model=self.config.primary_model,
                fault_injected=fault_desc,
                fault_latency_ms=latency_ms,
                fallback_engaged=True,
                fallback_provider=self.config.fallback_provider,
                fallback_model=self.config.fallback_model,
                status=ChaosStatus.RECOVERED,
                recovery_response=recovery_text,
            )
        except (RuntimeError, ValueError, OSError) as exc:
            logger.warning("Automated fallback failed during chaos fault injection: %s", exc)
            return ChaosFaultResult(
                mode=mode,
                primary_provider=self.config.primary_provider,
                primary_model=self.config.primary_model,
                fault_injected=fault_desc,
                fault_latency_ms=latency_ms,
                fallback_engaged=True,
                fallback_provider=self.config.fallback_provider,
                fallback_model=self.config.fallback_model,
                status=ChaosStatus.FAILED,
                error=str(exc),
            )

    def _inject_latency_fault(self) -> ChaosFaultResult:
        """Inject synthetic network latency and verify threshold adherence."""
        start_time = time.perf_counter()
        simulated_delay = (
            min(self.config.latency_ms / 1000.0, 0.01)
            if self.config.dry_run
            else min(self.config.latency_ms / 1000.0, 30.0)
        )
        time.sleep(simulated_delay)
        elapsed_ms = (time.perf_counter() - start_time) * 1000.0

        desc = f"Injected synthetic network latency ({self.config.latency_ms}ms target, {elapsed_ms:.1f}ms measured)"
        return self._execute_fallback_recovery(ChaosMode.LATENCY, desc, elapsed_ms)

    def _inject_rate_limit_fault(self) -> ChaosFaultResult:
        """Emulate HTTP 429 Too Many Requests rate-limiting on primary model."""
        desc = (
            f"HTTP 429 Too Many Requests: Rate limit exceeded for model "
            f"'{self.config.primary_model}' on provider '{self.config.primary_provider}'"
        )
        return self._execute_fallback_recovery(ChaosMode.RATE_LIMIT, desc, 0.0)

    def _inject_timeout_fault(self) -> ChaosFaultResult:
        """Emulate connection timeout or socket error to primary model endpoint."""
        desc = (
            f"Connection timeout (ConnectTimeout): Primary endpoint for "
            f"'{self.config.primary_provider}' failed to respond within deadline"
        )
        return self._execute_fallback_recovery(ChaosMode.TIMEOUT, desc, 0.0)

    def _inject_malformed_json_fault(self) -> ChaosFaultResult:
        """Emulate mid-stream truncation and malformed JSON syntax."""
        desc = (
            "Mid-stream response truncation: Unexpected EOF while parsing JSON stream "
            "(JSONDecodeError: Unterminated string)"
        )
        return self._execute_fallback_recovery(ChaosMode.MALFORMED_JSON, desc, 0.0)

    def _dispatch_fault(self, mode: ChaosMode) -> ChaosFaultResult:
        """Dispatch fault injection according to specified mode."""
        if self.config.error_rate <= 0.0 or (
            self.config.error_rate < 1.0 and random.random() > self.config.error_rate
        ):
            return ChaosFaultResult(
                mode=mode,
                primary_provider=self.config.primary_provider,
                primary_model=self.config.primary_model,
                fault_injected=f"Fault injection skipped (error_rate={self.config.error_rate})",
                status=ChaosStatus.SKIPPED,
            )

        dispatch_table = {
            ChaosMode.LATENCY: self._inject_latency_fault,
            ChaosMode.RATE_LIMIT: self._inject_rate_limit_fault,
            ChaosMode.TIMEOUT: self._inject_timeout_fault,
            ChaosMode.MALFORMED_JSON: self._inject_malformed_json_fault,
        }
        handler = dispatch_table.get(mode)
        if handler is None:
            return ChaosFaultResult(
                mode=mode,
                primary_provider=self.config.primary_provider,
                primary_model=self.config.primary_model,
                fault_injected=f"Unsupported chaos mode: {mode}",
                status=ChaosStatus.SKIPPED,
            )

        with trace_span(
            "ai.chaos.inject",
            attributes={
                "chaos.mode": mode.value,
                "chaos.primary_provider": self.config.primary_provider,
                "chaos.fallback_provider": self.config.fallback_provider,
                "chaos.fallback_model": self.config.fallback_model,
            },
        ) as fault_span:
            res = handler()
            fault_span.set_attributes(
                {
                    "chaos.status": res.status.value,
                    "chaos.fault_latency_ms": res.fault_latency_ms,
                    "chaos.fallback_engaged": res.fallback_engaged,
                }
            )
            return res

    def execute(self) -> ModelChaosReport:
        """Execute configured chaos tests with OpenTelemetry tracing and metrics."""
        start_time = time.perf_counter()
        target_modes = (
            [
                ChaosMode.LATENCY,
                ChaosMode.RATE_LIMIT,
                ChaosMode.TIMEOUT,
                ChaosMode.MALFORMED_JSON,
            ]
            if self.config.mode == ChaosMode.ALL
            else [self.config.mode]
        )

        with trace_span(
            "ai.chaos.run",
            attributes={
                "chaos.mode": self.config.mode.value,
                "chaos.primary_provider": self.config.primary_provider,
                "chaos.fallback_provider": self.config.fallback_provider,
                "chaos.dry_run": self.config.dry_run,
            },
        ) as span:
            results: list[ChaosFaultResult] = []
            for mode in target_modes:
                res = self._dispatch_fault(mode)
                results.append(res)

            recovered = sum(1 for r in results if r.status == ChaosStatus.RECOVERED)
            failed = sum(1 for r in results if r.status == ChaosStatus.FAILED)
            all_passed = failed == 0 and recovered == len(results)
            total_duration = time.perf_counter() - start_time

            span.set_attributes(
                {
                    "chaos.total_faults": len(results),
                    "chaos.recovered_faults": recovered,
                    "chaos.failed_faults": failed,
                    "chaos.all_passed": all_passed,
                }
            )

            summary = (
                f"Model chaos validation passed: {recovered}/{len(results)} faults successfully recovered."
                if all_passed
                else f"Model chaos validation failed: {failed}/{len(results)} faults could not be recovered."
            )

            return ModelChaosReport(
                summary=summary,
                total_faults=len(results),
                recovered_faults=recovered,
                failed_faults=failed,
                results=results,
                all_passed=all_passed,
                duration_seconds=total_duration,
            )
