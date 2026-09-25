"""Pricing registry for AI model token costs and open-source industrial rates."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from devops_cli.ai.spend.models import ModelPricing
from devops_cli.ai.spend.pricing_data import DEFAULT_INDUSTRIAL_MODEL_PRICING
from devops_cli.config.defaults import (
    DEFAULT_AI_PRICING_CATALOG_FILENAME,
    DEFAULT_AI_PRICING_OVERRIDES_FILENAME,
    DEFAULT_OPEN_SOURCE_PRICING_URL,
)
from devops_cli.config.settings import load_settings


def _normalize_model_name(model: str) -> str:
    """Normalize model identifier by stripping vendor prefixes and tag suffixes."""
    clean = model.strip().lower()
    if "/" in clean:
        clean = clean.split("/")[-1]
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


def _get_bracket_pricing(param_b: int) -> ModelPricing:
    """Determine industrial average pricing tier based on parameter size bracket."""
    if param_b < 10:
        return ModelPricing(
            prompt_usd_per_million=0.15,
            completion_usd_per_million=0.30,
            source=f"heuristic_{param_b}b",
        )
    if param_b <= 35:
        return ModelPricing(
            prompt_usd_per_million=0.30,
            completion_usd_per_million=0.60,
            source=f"heuristic_{param_b}b",
        )
    if param_b <= 100:
        return ModelPricing(
            prompt_usd_per_million=0.70,
            completion_usd_per_million=1.00,
            source=f"heuristic_{param_b}b",
        )
    return ModelPricing(
        prompt_usd_per_million=1.50,
        completion_usd_per_million=3.00,
        source=f"heuristic_{param_b}b",
    )


class PricingRegistry:
    """Registry maintaining AI model pricing with open-source updates and overrides."""

    def __init__(self, data_dir: Path | None = None) -> None:
        if data_dir is not None:
            self.data_dir = data_dir
        else:
            settings = load_settings()
            self.data_dir = settings.data.dir
        self.ai_dir = self.data_dir / "ai"
        self.catalog_path = self.ai_dir / DEFAULT_AI_PRICING_CATALOG_FILENAME
        self.overrides_path = self.ai_dir / DEFAULT_AI_PRICING_OVERRIDES_FILENAME
        self._catalog: dict[str, ModelPricing] = {}
        self._overrides: dict[str, ModelPricing] = {}
        self._load_local_data()

    def _load_local_data(self) -> None:
        """Load cached catalog and custom overrides from local disk."""
        self._load_catalog()
        self._load_overrides()

    def _load_catalog(self) -> None:
        """Load external catalog JSON if present."""
        if not self.catalog_path.is_file():
            return
        try:
            raw = json.loads(self.catalog_path.read_text(encoding="utf-8"))
            models_dict = raw.get("models", raw)
            if isinstance(models_dict, dict):
                for k, v in models_dict.items():
                    if isinstance(v, dict):
                        self._catalog[k.lower()] = ModelPricing.model_validate(v)
        except Exception:
            # Fall back to defaults on corruption or error
            self._catalog = {}

    def _load_overrides(self) -> None:
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

    def _resolve_key(self, key: str) -> ModelPricing | None:
        """Resolve a specific key against overrides, external catalog, and defaults."""
        return (
            self._overrides.get(key)
            or self._catalog.get(key)
            or DEFAULT_INDUSTRIAL_MODEL_PRICING.get(key)
        )

    def _resolve_normalized(self, model: str) -> ModelPricing | None:
        """Resolve normalized and delimiter-variant forms of model identifier."""
        norm_key = _normalize_model_name(model)
        candidates = (norm_key, norm_key.replace(":", "-"), norm_key.replace("-", ":"))
        for cand in candidates:
            res = self._resolve_key(cand)
            if res is not None:
                return res
        return None

    def get_pricing(self, model: str, server: str | None = None) -> ModelPricing:
        """Resolve token pricing in priority order: server override, model override, catalog, heuristic."""
        if server:
            srv_pricing = self._overrides.get(server.strip().lower())
            if srv_pricing is not None:
                return srv_pricing

        m_key = model.strip().lower()
        direct_match = self._resolve_key(m_key)
        if direct_match is not None:
            return direct_match

        norm_match = self._resolve_normalized(model)
        if norm_match is not None:
            return norm_match

        param_b = _extract_param_size_b(model)
        if param_b is not None:
            return _get_bracket_pricing(param_b)

        return DEFAULT_INDUSTRIAL_MODEL_PRICING.get(
            "default",
            ModelPricing(
                prompt_usd_per_million=0.50,
                completion_usd_per_million=1.00,
                source="default_fallback",
            ),
        )

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
        return pricing

    def remove_custom_pricing(self, target: str) -> bool:
        """Remove a custom pricing override."""
        key = target.strip().lower()
        if key in self._overrides:
            del self._overrides[key]
            self._save_overrides()
            return True
        return False

    def _save_overrides(self) -> None:
        """Persist custom pricing overrides to disk."""
        self.ai_dir.mkdir(parents=True, exist_ok=True)
        data = {k: v.model_dump() for k, v in self._overrides.items()}
        self.overrides_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def list_all_pricing(self) -> dict[str, ModelPricing]:
        """Return merged pricing dictionary: defaults, external catalog, and overrides."""
        merged: dict[str, ModelPricing] = dict(DEFAULT_INDUSTRIAL_MODEL_PRICING)
        merged.update(self._catalog)
        merged.update(self._overrides)
        return merged

    def update_from_remote(self, source_url: str | None = None, timeout: float = 15.0) -> int:
        """Download open-source model pricing catalog and update local cached registry."""
        import httpx2

        url = source_url or DEFAULT_OPEN_SOURCE_PRICING_URL
        with httpx2.Client(timeout=timeout) as client:
            resp = client.get(url)
            resp.raise_for_status()
            raw = resp.json()

        if not isinstance(raw, dict):
            raise ValueError(f"Invalid pricing catalog payload received from {url}")

        parsed: dict[str, Any] = {}
        now_iso = datetime.now(UTC).isoformat()

        for model_name, info in raw.items():
            if not isinstance(info, dict):
                continue
            in_cost = info.get("input_cost_per_token")
            out_cost = info.get("output_cost_per_token")
            if in_cost is not None and out_cost is not None:
                p_usd = round(float(in_cost) * 1_000_000.0, 4)
                c_usd = round(float(out_cost) * 1_000_000.0, 4)
                parsed[model_name.lower()] = {
                    "prompt_usd_per_million": p_usd,
                    "completion_usd_per_million": c_usd,
                    "source": "open_source_catalog",
                    "updated_at": now_iso,
                }

        self.ai_dir.mkdir(parents=True, exist_ok=True)
        catalog_payload = {
            "source": url,
            "synced_at": now_iso,
            "models_count": len(parsed),
            "models": parsed,
        }
        self.catalog_path.write_text(json.dumps(catalog_payload, indent=2), encoding="utf-8")
        self._load_catalog()
        return len(parsed)


_GLOBAL_REGISTRY: PricingRegistry | None = None


def get_pricing_registry(data_dir: Path | None = None) -> PricingRegistry:
    """Return singleton PricingRegistry instance."""
    global _GLOBAL_REGISTRY
    if _GLOBAL_REGISTRY is None or data_dir is not None:
        _GLOBAL_REGISTRY = PricingRegistry(data_dir=data_dir)
    return _GLOBAL_REGISTRY
