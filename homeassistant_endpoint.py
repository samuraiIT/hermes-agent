"""Shared Home Assistant endpoint resolution for Hermes.

Hermes should treat the Home Assistant base URL as agent-owned runtime state,
not as a mandatory shell environment variable.  The canonical source order is:

1. Explicit per-call override from platform/tool config.
2. ``~/.hermes/config.yaml`` → ``platforms.homeassistant.extra.url``.
3. Legacy ``HASS_URL`` env var for backward compatibility.
4. Built-in default ``http://homeassistant.local:8123``.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import yaml

from hermes_constants import get_config_path

logger = logging.getLogger(__name__)

DEFAULT_HOMEASSISTANT_URL = "http://homeassistant.local:8123"


def normalize_homeassistant_url(url: Any) -> str:
    """Normalize user-provided HA URLs into a stable base URL."""
    if not isinstance(url, str):
        return ""
    normalized = url.strip()
    if not normalized:
        return ""
    if "://" not in normalized:
        normalized = f"http://{normalized}"
    return normalized.rstrip("/")


def _load_hermes_config() -> dict[str, Any]:
    """Best-effort read of ``config.yaml`` without raising on parse issues."""
    config_path = get_config_path()
    try:
        if not config_path.exists():
            return {}
        loaded = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        return loaded if isinstance(loaded, dict) else {}
    except Exception as exc:
        logger.debug("Failed to load Hermes config for Home Assistant URL: %s", exc)
        return {}


def get_configured_homeassistant_url() -> str:
    """Return the HA URL stored in Hermes config, if present."""
    config = _load_hermes_config()
    platforms = config.get("platforms")
    if not isinstance(platforms, dict):
        return ""
    homeassistant = platforms.get("homeassistant")
    if not isinstance(homeassistant, dict):
        return ""

    extra = homeassistant.get("extra")
    if isinstance(extra, dict):
        configured = normalize_homeassistant_url(extra.get("url"))
        if configured:
            return configured

    return normalize_homeassistant_url(homeassistant.get("url"))


def resolve_homeassistant_url(override: str = "") -> str:
    """Resolve the effective Home Assistant URL for Hermes runtime use."""
    for candidate in (
        override,
        get_configured_homeassistant_url(),
        os.getenv("HASS_URL", ""),
        DEFAULT_HOMEASSISTANT_URL,
    ):
        normalized = normalize_homeassistant_url(candidate)
        if normalized:
            return normalized
    return DEFAULT_HOMEASSISTANT_URL
