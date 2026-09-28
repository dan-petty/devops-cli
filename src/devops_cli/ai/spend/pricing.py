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
from devops_cli.core.repo import resolve_data_path


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


def is_local(server: str | None = None, provider: str | None = None) -> bool:
    """Return True if the backend server or provider indicates local execution."""
    return _is_local_provider(provider) or _is_local_server(server)


_is_local = is_local


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
            self.data_dir = resolve_data_path(Path(settings.data.dir))
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
        try:
            from genai_prices.data_snapshot import DataSnapshot, set_custom_snapshot
            from genai_prices.types import _providers_from_raw

            raw_snap = json.loads(self.snapshot_path.read_text(encoding="utf-8"))
            if isinstance(raw_snap, list):
                set_custom_snapshot(
                    DataSnapshot(_providers_from_raw(raw_snap), from_auto_update=True)
                )
        except Exception:
            pass

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
    ) -> ModelPricing:
        """Resolve token pricing in priority order: overrides, local zero-cost, genai-prices lookup."""
        override = self._get_override_pricing(model, server)
        if override is not None:
            return override

        if _is_local(server=server, provider=provider):
            return ModelPricing(
                prompt_usd_per_million=0.0,
                completion_usd_per_million=0.0,
                source="local",
            )

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
    ) -> float:
        """Calculate exact cost for a request using real token usage and request timestamp."""
        if prompt_tokens <= 0 and completion_tokens <= 0:
            return 0.0

        override_cost = self._check_override_cost(model, server, prompt_tokens, completion_tokens)
        if override_cost is not None:
            return override_cost

        if _is_local(server=server, provider=provider):
            return 0.0

        exact_cost = self._calc_exact_genai_cost(
            model, prompt_tokens, completion_tokens, provider, request_timestamp
        )
        if exact_cost is not None:
            return exact_cost

        pricing = self.get_pricing(
            model, server=server, provider=provider, request_timestamp=request_timestamp
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
                return json.loads(p.read_text(encoding="utf-8"))
            r = httpx2.get(source_url, timeout=timeout)
            r.raise_for_status()
            return json.loads(r.content)

        import genai_prices

        updater = genai_prices.UpdatePrices(request_timeout=httpx2.Timeout(timeout))
        url = getattr(updater, "url", None)
        if url:
            r = httpx2.get(url, timeout=timeout)
            r.raise_for_status()
            return json.loads(r.content)
        return updater.fetch()

    def update_from_remote(self, source_url: str | None = None, timeout: float = 15.0) -> int:
        """Synchronize model pricing catalog from remote genai-prices registry or file."""
        from genai_prices.data_snapshot import DataSnapshot, set_custom_snapshot
        from genai_prices.types import _providers_from_raw

        fetched = self._fetch_raw_pricing_payload(source_url, timeout)
        if isinstance(fetched, DataSnapshot):
            snapshot = fetched
            set_custom_snapshot(snapshot)
            self._pricing_cache.clear()
            self._catalog.clear()
            return sum(len(p.models) for p in snapshot.providers)

        if not isinstance(fetched, list):
            raise ValueError("Expected fetched prices payload to be a provider array")

        providers = _providers_from_raw(fetched)
        snapshot = DataSnapshot(providers, from_auto_update=True)
        set_custom_snapshot(snapshot)

        self.ai_dir.mkdir(parents=True, exist_ok=True)
        self.snapshot_path.write_text(json.dumps(fetched), encoding="utf-8")

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
