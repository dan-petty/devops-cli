"""Pricing registry for AI model token costs and open-source industrial rates."""

from __future__ import annotations

import ipaddress
import json
import logging
import re
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, NamedTuple
from urllib.parse import urlsplit

from devops_cli.ai.spend.models import ModelPricing
from devops_cli.config.constants import (
    CONST_LOCAL_PROVIDER_NAMES,
    CONST_LOCAL_TRANSPORT_LABELS,
)
from devops_cli.config.defaults import (
    DEFAULT_AI_PRICING_OVERRIDES_FILENAME,
)
from devops_cli.config.settings import load_settings
from devops_cli.core.repo import resolve_review_data_path

logger = logging.getLogger(__name__)


class UpdatePricingResult(NamedTuple):
    """Result summary of a pricing snapshot update."""

    source_model_count: int
    merged_model_count: int


def _get_installed_genai_prices_version() -> str:
    """Return the installed package version of genai-prices."""
    import importlib.metadata

    try:
        return importlib.metadata.version("genai-prices")
    except importlib.metadata.PackageNotFoundError:
        return ""


def _preprocess_raw_providers(
    raw_providers: list[Any], bundled_providers: Sequence[Any]
) -> list[Any]:
    """Ensure raw provider dicts have name and api_pattern if overriding a bundled provider."""
    bundled_by_id = {p.id: p for p in bundled_providers}
    preprocessed: list[Any] = []
    for item in raw_providers:
        if isinstance(item, dict) and "id" in item and item["id"] in bundled_by_id:
            bp = bundled_by_id[item["id"]]
            entry = dict(item)
            if not entry.get("name"):
                entry["name"] = bp.name
            if not entry.get("api_pattern"):
                entry["api_pattern"] = bp.api_pattern
            preprocessed.append(entry)
        else:
            preprocessed.append(item)
    return preprocessed


def _merge_single_provider(file_p: Any, bundled_p: Any) -> Any:
    """Merge a file-supplied Provider with a bundled Provider field by field."""
    from genai_prices.types import Provider

    file_model_ids = {m.id for m in file_p.models}
    merged_models = list(file_p.models) + [
        m for m in bundled_p.models if m.id not in file_model_ids
    ]
    kwargs: dict[str, Any] = {"id": file_p.id, "models": merged_models}
    fields = (
        "name",
        "api_pattern",
        "pricing_urls",
        "description",
        "price_comments",
        "model_match",
        "provider_match",
        "extractors",
        "fallback_model_providers",
    )
    for field_name in fields:
        val = getattr(file_p, field_name, None)
        kwargs[field_name] = val if val is not None else getattr(bundled_p, field_name, None)
    return Provider(**kwargs)


def _merge_providers(file_providers: Sequence[Any], bundled_providers: Sequence[Any]) -> list[Any]:
    """Merge file providers onto bundled providers following priority rules."""
    file_by_id = {p.id: p for p in file_providers}
    merged: list[Any] = []
    seen_ids: set[str] = set()

    for bundled_p in bundled_providers:
        seen_ids.add(bundled_p.id)
        if bundled_p.id in file_by_id:
            merged.append(_merge_single_provider(file_by_id[bundled_p.id], bundled_p))
        else:
            merged.append(bundled_p)

    for file_p in file_providers:
        if file_p.id not in seen_ids:
            merged.append(file_p)

    return merged


def _parse_snapshot_fetch_time(raw_snap: dict[str, Any]) -> datetime:
    """Parse recorded fetch timestamp from snapshot payload, defaulting to UTC now."""
    val = raw_snap.get("fetched_at") or raw_snap.get("fetch_time") or raw_snap.get("timestamp")
    if val:
        try:
            if isinstance(val, (int, float)):
                return datetime.fromtimestamp(val, tz=UTC)
            return datetime.fromisoformat(str(val))
        except ValueError, TypeError:
            pass
    return datetime.now(tz=UTC)


def _normalize_model_name(model: str) -> str:
    """Normalize model identifier by stripping vendor prefixes and tag suffixes."""
    clean = model.strip().lower()
    if "/" in clean:
        clean = clean.split("/")[-1]
    if clean.endswith(":latest"):
        clean = clean.removesuffix(":latest")
    return clean


def _extract_param_size_b(model: str) -> int | None:
    """Extract parameter count in billions from model name, e.g. '70b' -> 70, '1.5b' -> 1."""
    match = re.search(r"(?:^|[-_:a-z])(\d+(?:\.\d+)?)b(?:\b|[-_:])", model.lower())
    if match:
        try:
            return int(float(match.group(1)))
        except ValueError:
            return None
    return None


def _is_local_provider(provider: str | None) -> bool:
    return bool(provider and provider.strip().lower() in CONST_LOCAL_PROVIDER_NAMES)


def _is_configured_cluster_host(host: str) -> bool:
    """Check if host matches configured Kubernetes or Cloudflare cluster domain."""
    import dns.exception

    from devops_cli.core.dns_names import is_at_or_under

    try:
        settings = load_settings()
    except Exception:
        return False
    for domain in (settings.k8s.domain, settings.cloudflare.domain):
        if not domain:
            continue
        try:
            if is_at_or_under(host, domain):
                return True
        except dns.exception.DNSException:
            continue
    return False


def _is_configured_ai_server_host(host: str) -> bool:
    """Check if host matches any configured AI endpoints in settings."""
    try:
        settings = load_settings()
    except Exception:
        return False
    candidates = (
        settings.ai.gateway_url,
        settings.ai.api_base_url,
        settings.ai.portkey_url,
        *settings.ai.ollama_urls,
    )
    from devops_cli.http.urls import extract_domain_target

    for cand in candidates:
        if not cand:
            continue
        cand_host = extract_domain_target(cand.strip().lower())
        if cand_host and cand_host == host:
            return True
    return False


def _is_local_host(host: str) -> bool:
    from devops_cli.core.dns_names import is_public_dns_name

    clean = urlsplit(f"//{host}").hostname or host
    try:
        ip = ipaddress.ip_address(clean)
        if ip.is_loopback or ip.is_private:
            return True
    except ValueError:
        if not is_public_dns_name(host):
            return True
    return _is_configured_cluster_host(host) or _is_configured_ai_server_host(host)


def _is_single_server_local(server: str) -> bool:
    clean = server.strip().lower()
    if not clean:
        return False
    if clean in CONST_LOCAL_TRANSPORT_LABELS or urlsplit(clean).scheme == "http+unix":
        return True
    from devops_cli.http.urls import extract_domain_target

    host = extract_domain_target(clean)
    if host and _is_local_host(host):
        return True
    return False


def _is_local_server(server: str | None) -> bool:
    if not server:
        return False
    clean = server.strip().lower()
    if "," in clean:
        parts = [p.strip() for p in clean.split(",") if p.strip()]
        return bool(parts) and all(_is_single_server_local(p) for p in parts)
    return _is_single_server_local(clean)


def _is_local_gateway_configured() -> bool:
    """Check if configured AI gateway endpoint resolves to local/cluster infrastructure."""
    try:
        settings = load_settings()
        gw_url = settings.ai.gateway_url or settings.ai.api_base_url
        if gw_url and _is_local_server(gw_url):
            return True
    except Exception:
        pass
    return False


def is_local(
    server: str | None = None, provider: str | None = None, served_by: str | None = None
) -> bool:
    """Return True if the call ran on local hardware.

    `served_by` is the backend that served the call, as the LLM gateway names it in its reply
    (`ai/client/network.py` reads the header). When the reply names it, it decides: a hosted route
    behind a local gateway is hosted, and a local backend behind a gateway on a public host is
    local (#1631). LiteLLM names the API base of a route only when it knows it, so a gateway
    route sets `api_base`. When the reply names no backend, the provider and the server the call
    was sent to decide.
    """
    if served_by and served_by.strip():
        return _is_local_server(served_by)
    if _is_local_provider(provider):
        return True
    if _is_local_server(server):
        return True
    if provider and provider.strip().lower() == "gateway" and not server:
        return _is_local_gateway_configured()
    return False


def _candidate_models(model: str) -> tuple[str, ...]:
    clean = model.strip().lower()
    norm = _normalize_model_name(model)
    candidates = [clean]
    if norm != clean:
        candidates.append(norm)
    colon_to_dash = norm.replace(":", "-")
    if colon_to_dash not in candidates:
        candidates.append(colon_to_dash)
    return tuple(candidates)


def _query_genai_prices(
    model: str,
    provider: str | None = None,
    request_timestamp: datetime | None = None,
) -> ModelPricing | None:
    import genai_prices

    usage = genai_prices.Usage(input_tokens=1_000, output_tokens=1_000)
    candidates = _candidate_models(model)
    prov_id = provider.strip().lower() if provider else None
    for cand in candidates:
        try:
            p = genai_prices.calc_price(
                usage,
                cand,
                provider_id=prov_id,
                genai_request_timestamp=request_timestamp,
            )
            return ModelPricing(
                prompt_usd_per_million=round(float(p.input_price) * 1_000.0, 6),
                completion_usd_per_million=round(float(p.output_price) * 1_000.0, 6),
                source=f"genai_prices:{p.provider.id}",
            )
        except Exception:
            continue
    if prov_id is not None:
        for cand in candidates:
            try:
                p = genai_prices.calc_price(
                    usage,
                    cand,
                    genai_request_timestamp=request_timestamp,
                )
                return ModelPricing(
                    prompt_usd_per_million=round(float(p.input_price) * 1_000.0, 6),
                    completion_usd_per_million=round(float(p.output_price) * 1_000.0, 6),
                    source=f"genai_prices:{p.provider.id}",
                )
            except Exception:
                continue
    return None


class PricingRegistry:
    """Registry maintaining AI model pricing with genai-prices and custom overrides."""

    def __init__(self, data_dir: Path | None = None) -> None:
        if data_dir is not None:
            self.data_dir = Path(data_dir)
        else:
            settings = load_settings()
            # Beside the spend ledger, which a review records into too (#972).
            self.data_dir = resolve_review_data_path(Path(settings.data.dir))
        self.ai_dir = self.data_dir / "ai"
        self.overrides_path = self.ai_dir / DEFAULT_AI_PRICING_OVERRIDES_FILENAME
        self.snapshot_path = self.ai_dir / "pricing_snapshot.json"
        self._catalog: dict[str, ModelPricing] = {}
        self._overrides: dict[str, ModelPricing] = {}
        self._pricing_cache: dict[str, ModelPricing] = {}
        self._load_local_data()

    def _load_local_data(self) -> None:
        """Load user-defined pricing overrides and cached remote snapshot if present."""
        self._load_persisted_snapshot()
        self._load_persisted_overrides()

    def _load_persisted_snapshot(self) -> None:
        """Load cached snapshot from disk to restore previously updated prices."""
        if not self.snapshot_path.is_file():
            return

        def _warn_ignored(reason: str) -> None:
            logger.warning(
                "Ignoring pricing snapshot %s (%s). To clear it, run 'devops ai cost update-pricing --reset'.",
                self.snapshot_path,
                reason,
            )

        try:
            content = self.snapshot_path.read_text(encoding="utf-8")
            raw_snap = json.loads(content)
        except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            _warn_ignored(f"unreadable: {exc}")
            return

        if not isinstance(raw_snap, dict):
            _warn_ignored("old format (missing metadata wrapper)")
            return

        recorded_version = raw_snap.get("genai_prices_version") or raw_snap.get("version")
        if not recorded_version:
            _warn_ignored("missing genai-prices version")
            return

        installed_version = _get_installed_genai_prices_version()
        if recorded_version != installed_version:
            _warn_ignored(
                f"stale (recorded version {recorded_version} != installed version {installed_version})"
            )
            return

        raw_providers = raw_snap.get("providers")
        if not isinstance(raw_providers, list):
            _warn_ignored("missing or invalid providers list")
            return

        fetch_time = _parse_snapshot_fetch_time(raw_snap)

        try:
            from genai_prices.data_snapshot import (
                DataSnapshot,
                _bundled_snapshot,
                set_custom_snapshot,
            )
            from genai_prices.types import _providers_from_raw

            bundled = _bundled_snapshot()
            preprocessed = _preprocess_raw_providers(raw_providers, bundled.providers)
            file_providers = _providers_from_raw(preprocessed)
            merged = _merge_providers(file_providers, bundled.providers)
            snapshot = DataSnapshot(providers=merged, from_auto_update=True, timestamp=fetch_time)
            set_custom_snapshot(snapshot)
        except (TypeError, ValueError, KeyError, AttributeError) as exc:
            _warn_ignored(f"failed to parse providers: {exc}")

    def _load_persisted_overrides(self) -> None:
        """Load user custom pricing overrides file."""
        if not self.overrides_path.is_file():
            return
        try:
            raw = json.loads(self.overrides_path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                for k, v in raw.items():
                    if isinstance(v, dict):
                        self._overrides[k.lower()] = ModelPricing.model_validate(v)
        except Exception:
            self._overrides = {}

    def _get_override_pricing(self, model: str, server: str | None) -> ModelPricing | None:
        """Resolve custom pricing override if configured for model or server."""
        m_key = model.strip().lower()
        if m_key in self._overrides:
            return self._overrides[m_key]
        norm_key = _normalize_model_name(model)
        if norm_key in self._overrides:
            return self._overrides[norm_key]
        if server:
            srv_pricing = self._overrides.get(server.strip().lower())
            if srv_pricing is not None:
                return srv_pricing
        return None

    def get_pricing(
        self,
        model: str,
        server: str | None = None,
        provider: str | None = None,
        request_timestamp: datetime | None = None,
        served_by: str | None = None,
    ) -> ModelPricing:
        """Resolve token pricing in priority order: local zero-cost, overrides, genai-prices lookup.

        A local call costs nothing, whatever override names its model or server, so its tokens
        count in local savings and never as spend (#1631).
        """
        if is_local(server=server, provider=provider, served_by=served_by):
            return ModelPricing(
                prompt_usd_per_million=0.0,
                completion_usd_per_million=0.0,
                source="local",
            )

        override = self._get_override_pricing(model, server)
        if override is not None:
            return override

        prov_clean = provider.strip().lower() if provider else ""
        cache_key = f"{prov_clean}:{model.strip().lower()}"
        if request_timestamp is None and cache_key in self._pricing_cache:
            return self._pricing_cache[cache_key]

        resolved = _query_genai_prices(
            model, provider=provider, request_timestamp=request_timestamp
        )
        pricing = resolved or ModelPricing(
            prompt_usd_per_million=0.0,
            completion_usd_per_million=0.0,
            source="unknown",
        )
        if request_timestamp is None:
            self._pricing_cache[cache_key] = pricing
        return pricing

    def _check_override_cost(
        self, model: str, server: str | None, prompt_tokens: int, completion_tokens: int
    ) -> float | None:
        """Calculate cost from custom override if registered."""
        m_key = model.strip().lower()
        if m_key in self._overrides:
            return self._overrides[m_key].calculate_cost(prompt_tokens, completion_tokens)
        norm_key = _normalize_model_name(model)
        if norm_key in self._overrides:
            return self._overrides[norm_key].calculate_cost(prompt_tokens, completion_tokens)
        if server:
            srv_pricing = self._overrides.get(server.strip().lower())
            if srv_pricing is not None:
                return srv_pricing.calculate_cost(prompt_tokens, completion_tokens)
        return None

    def _calc_exact_genai_cost(
        self,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        provider: str | None,
        request_timestamp: datetime | None,
    ) -> float | None:
        """Calculate real request cost using genai-prices exact tiered usage."""
        import genai_prices

        usage = genai_prices.Usage(input_tokens=prompt_tokens, output_tokens=completion_tokens)
        candidates = _candidate_models(model)
        prov_id = provider.strip().lower() if provider else None
        req_ts = request_timestamp or datetime.now(UTC)
        for cand in candidates:
            try:
                p = genai_prices.calc_price(
                    usage, cand, provider_id=prov_id, genai_request_timestamp=req_ts
                )
                return round(float(p.total_price), 6)
            except Exception:
                continue
        if prov_id is not None:
            for cand in candidates:
                try:
                    p = genai_prices.calc_price(usage, cand, genai_request_timestamp=req_ts)
                    return round(float(p.total_price), 6)
                except Exception:
                    continue
        return None

    def calculate_request_cost(
        self,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        server: str | None = None,
        provider: str | None = None,
        request_timestamp: datetime | None = None,
        served_by: str | None = None,
    ) -> float:
        """Calculate exact cost for a request using real token usage and request timestamp.

        A local call costs nothing, whatever override names its model or server (#1631).
        """
        if prompt_tokens <= 0 and completion_tokens <= 0:
            return 0.0

        if is_local(server=server, provider=provider, served_by=served_by):
            return 0.0

        override_cost = self._check_override_cost(model, server, prompt_tokens, completion_tokens)
        if override_cost is not None:
            return override_cost

        exact_cost = self._calc_exact_genai_cost(
            model, prompt_tokens, completion_tokens, provider, request_timestamp
        )
        if exact_cost is not None:
            return exact_cost

        pricing = self.get_pricing(
            model,
            server=server,
            provider=provider,
            request_timestamp=request_timestamp,
            served_by=served_by,
        )
        return pricing.calculate_cost(prompt_tokens, completion_tokens)

    def set_custom_pricing(
        self, target: str, prompt_rate: float, completion_rate: float
    ) -> ModelPricing:
        """Store custom pricing override for a model or server endpoint."""
        pricing = ModelPricing(
            prompt_usd_per_million=float(prompt_rate),
            completion_usd_per_million=float(completion_rate),
            source="custom_override",
            updated_at=datetime.now(UTC).isoformat(),
        )
        self._overrides[target.strip().lower()] = pricing
        self._save_overrides()
        self._pricing_cache.clear()
        return pricing

    def remove_custom_pricing(self, target: str) -> bool:
        """Remove a custom pricing override."""
        key = target.strip().lower()
        if key in self._overrides:
            del self._overrides[key]
            self._save_overrides()
            self._pricing_cache.clear()
            return True
        return False

    def _save_overrides(self) -> None:
        """Persist custom pricing overrides to disk."""
        self.ai_dir.mkdir(parents=True, exist_ok=True)
        data = {k: v.model_dump() for k, v in self._overrides.items()}
        self.overrides_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def _build_catalog(self) -> dict[str, ModelPricing]:
        """Extract baseline pricing catalog from genai-prices snapshot."""
        import genai_prices

        catalog: dict[str, ModelPricing] = {}
        usage = genai_prices.Usage(input_tokens=1_000, output_tokens=1_000)
        ds = genai_prices.data_snapshot.get_snapshot()
        for prov in ds.providers:
            for m in prov.models:
                m_key = m.id.lower()
                if m_key in catalog:
                    continue
                try:
                    p = genai_prices.calc_price(usage, m.id, provider_id=prov.id)
                    catalog[m_key] = ModelPricing(
                        prompt_usd_per_million=round(float(p.input_price) * 1_000.0, 6),
                        completion_usd_per_million=round(float(p.output_price) * 1_000.0, 6),
                        source=f"genai_prices:{prov.id}",
                    )
                except Exception:
                    continue
        return catalog

    def list_all_pricing(self) -> dict[str, ModelPricing]:
        """Return merged pricing dictionary: genai-prices models and custom overrides."""
        if not self._catalog:
            self._catalog = self._build_catalog()
        merged = dict(self._catalog)
        merged.update(self._overrides)
        return merged

    @staticmethod
    def _fetch_raw_pricing_payload(source_url: str | None, timeout: float) -> object:
        """Fetch raw JSON pricing payload from local file, custom URL, or default registry."""
        import httpx2

        if source_url:
            p = Path(source_url)
            if p.is_file():
                raw = json.loads(p.read_text(encoding="utf-8"))
                if isinstance(raw, dict) and "providers" in raw:
                    return raw["providers"]
                return raw
            r = httpx2.get(source_url, timeout=timeout)
            r.raise_for_status()
            raw = json.loads(r.content)
            if isinstance(raw, dict) and "providers" in raw:
                return raw["providers"]
            return raw

        import genai_prices

        updater = genai_prices.UpdatePrices(request_timeout=httpx2.Timeout(timeout))
        url = getattr(updater, "url", None)
        if url:
            r = httpx2.get(url, timeout=timeout)
            r.raise_for_status()
            raw = json.loads(r.content)
            if isinstance(raw, dict) and "providers" in raw:
                return raw["providers"]
            return raw
        return updater.fetch()

    def update_from_remote(
        self, source_url: str | None = None, timeout: float = 15.0
    ) -> UpdatePricingResult:
        """Synchronize model pricing catalog from remote genai-prices registry or file."""
        from genai_prices.data_snapshot import (
            DataSnapshot,
            _bundled_snapshot,
            set_custom_snapshot,
        )
        from genai_prices.types import _providers_from_raw

        fetched = self._fetch_raw_pricing_payload(source_url, timeout)
        if not isinstance(fetched, list):
            raise ValueError("Expected fetched prices payload to be a provider array")

        fetched_at = datetime.now(tz=UTC)
        bundled = _bundled_snapshot()
        preprocessed = _preprocess_raw_providers(fetched, bundled.providers)
        source_providers = _providers_from_raw(preprocessed)
        merged_providers = _merge_providers(source_providers, bundled.providers)

        snapshot = DataSnapshot(
            providers=merged_providers, from_auto_update=True, timestamp=fetched_at
        )
        set_custom_snapshot(snapshot)

        self.ai_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "genai_prices_version": _get_installed_genai_prices_version(),
            "fetched_at": fetched_at.isoformat(),
            "providers": fetched,
        }
        self.snapshot_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

        self._pricing_cache.clear()
        self._catalog.clear()

        source_count = sum(len(p.models) for p in source_providers)
        merged_count = sum(len(p.models) for p in merged_providers)
        return UpdatePricingResult(source_model_count=source_count, merged_model_count=merged_count)

    def reset_pricing(self) -> None:
        """Reset custom pricing snapshot, removing persisted file and restoring bundled catalog."""
        from genai_prices.data_snapshot import set_custom_snapshot

        if self.snapshot_path.is_file():
            try:
                self.snapshot_path.unlink()
            except OSError:
                pass
        set_custom_snapshot(None)
        self._pricing_cache.clear()
        self._catalog.clear()


_GLOBAL_REGISTRY: PricingRegistry | None = None


def get_pricing_registry(data_dir: Path | None = None) -> PricingRegistry:
    """Return singleton PricingRegistry instance."""
    global _GLOBAL_REGISTRY
    if _GLOBAL_REGISTRY is None or data_dir is not None:
        _GLOBAL_REGISTRY = PricingRegistry(data_dir=data_dir)
    return _GLOBAL_REGISTRY


def reset_pricing_registry() -> None:
    """Drop the global PricingRegistry singleton."""
    global _GLOBAL_REGISTRY
    _GLOBAL_REGISTRY = None
