"""Pricing registry for AI model token costs and open-source industrial rates."""

from __future__ import annotations

import ipaddress
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

from devops_cli.ai.spend.models import ModelPricing
from devops_cli.config.constants import (
    CONST_LOCAL_DOMAIN_SUFFIXES,
    CONST_LOCAL_HOSTNAMES,
    CONST_LOCAL_PROVIDER_NAMES,
    CONST_LOCAL_TRANSPORT_LABELS,
)
from devops_cli.config.defaults import (
    DEFAULT_AI_PRICING_OVERRIDES_FILENAME,
)
from devops_cli.config.settings import load_settings


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


def _is_local_host(host: str) -> bool:
    if host in CONST_LOCAL_HOSTNAMES:
        return True
    if any(host.endswith(suffix) for suffix in CONST_LOCAL_DOMAIN_SUFFIXES):
        return True
    try:
        ip = ipaddress.ip_address(host)
        return ip.is_loopback or ip.is_private
    except ValueError:
        return False


def _is_local_server(server: str | None) -> bool:
    if not server:
        return False
    clean = server.strip().lower()
    if clean in CONST_LOCAL_TRANSPORT_LABELS:
        return True
    if clean.startswith("http+unix://"):
        return True
    target = clean if "://" in clean else f"http://{clean}"
    try:
        parsed = urlsplit(target)
        if parsed.hostname and _is_local_host(parsed.hostname):
            return True
    except Exception:
        pass
    return False


def _is_local(server: str | None = None, provider: str | None = None) -> bool:
    return _is_local_provider(provider) or _is_local_server(server)


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


def _query_genai_prices(model: str, provider: str | None = None) -> ModelPricing | None:
    import genai_prices

    usage = genai_prices.Usage(input_tokens=1_000_000, output_tokens=1_000_000)
    candidates = _candidate_models(model)
    prov_id = provider.strip().lower() if provider else None
    for cand in candidates:
        try:
            p = genai_prices.calc_price(usage, cand, provider_id=prov_id)
            return ModelPricing(
                prompt_usd_per_million=float(p.input_price),
                completion_usd_per_million=float(p.output_price),
                source=f"genai_prices:{p.provider.id}",
            )
        except Exception:
            continue
    if prov_id is not None:
        for cand in candidates:
            try:
                p = genai_prices.calc_price(usage, cand)
                return ModelPricing(
                    prompt_usd_per_million=float(p.input_price),
                    completion_usd_per_million=float(p.output_price),
                    source=f"genai_prices:{p.provider.id}",
                )
            except Exception:
                continue
    return None


class PricingRegistry:
    """Registry maintaining AI model pricing with genai-prices and custom overrides."""

    def __init__(self, data_dir: Path | None = None) -> None:
        if data_dir is not None:
            self.data_dir = data_dir
        else:
            settings = load_settings()
            self.data_dir = settings.data.dir
        self.ai_dir = self.data_dir / "ai"
        self.overrides_path = self.ai_dir / DEFAULT_AI_PRICING_OVERRIDES_FILENAME
        self._catalog: dict[str, ModelPricing] = {}
        self._overrides: dict[str, ModelPricing] = {}
        self._pricing_cache: dict[str, ModelPricing] = {}
        self._load_local_data()

    def _load_local_data(self) -> None:
        """Load user-defined pricing overrides if present."""
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

    def get_pricing(
        self,
        model: str,
        server: str | None = None,
        provider: str | None = None,
    ) -> ModelPricing:
        """Resolve token pricing in priority order: overrides, local zero-cost, genai-prices lookup."""
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

        if _is_local(server=server, provider=provider):
            return ModelPricing(
                prompt_usd_per_million=0.0,
                completion_usd_per_million=0.0,
                source="local",
            )

        prov_clean = provider.strip().lower() if provider else ""
        cache_key = f"{prov_clean}:{m_key}"
        cached = self._pricing_cache.get(cache_key)
        if cached is not None:
            return cached

        resolved = _query_genai_prices(model, provider=provider)
        if resolved is not None:
            self._pricing_cache[cache_key] = resolved
            return resolved

        unknown = ModelPricing(
            prompt_usd_per_million=0.0,
            completion_usd_per_million=0.0,
            source="unknown",
        )
        self._pricing_cache[cache_key] = unknown
        return unknown

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
        usage = genai_prices.Usage(input_tokens=1_000_000, output_tokens=1_000_000)
        ds = genai_prices.data_snapshot.get_snapshot()
        for prov in ds.providers:
            for m in prov.models:
                m_key = m.id.lower()
                if m_key in catalog:
                    continue
                try:
                    p = genai_prices.calc_price(usage, m.id, provider_id=prov.id)
                    catalog[m_key] = ModelPricing(
                        prompt_usd_per_million=float(p.input_price),
                        completion_usd_per_million=float(p.output_price),
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

    def update_from_remote(self, source_url: str | None = None, timeout: float = 15.0) -> int:
        """Synchronize model pricing catalog from remote genai-prices registry."""
        import genai_prices
        import httpx2
        from genai_prices.data_snapshot import set_custom_snapshot

        updater = (
            genai_prices.UpdatePrices(url=source_url) if source_url else genai_prices.UpdatePrices()
        )
        updater.request_timeout = httpx2.Timeout(timeout)
        snapshot = updater.fetch()
        if snapshot is None:
            raise RuntimeError("Pricing update returned no snapshot")

        set_custom_snapshot(snapshot)
        self._pricing_cache.clear()
        self._catalog.clear()
        return sum(len(p.models) for p in snapshot.providers)


_GLOBAL_REGISTRY: PricingRegistry | None = None


def get_pricing_registry(data_dir: Path | None = None) -> PricingRegistry:
    """Return singleton PricingRegistry instance."""
    global _GLOBAL_REGISTRY
    if _GLOBAL_REGISTRY is None or data_dir is not None:
        _GLOBAL_REGISTRY = PricingRegistry(data_dir=data_dir)
    return _GLOBAL_REGISTRY
