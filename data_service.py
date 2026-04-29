from __future__ import annotations

import time
from threading import Lock

import build_json
import settings

_cache_lock = Lock()
_cached_dataset: dict | None = None
_cached_at = 0.0


def _is_cache_valid(now: float) -> bool:
    return (
        _cached_dataset is not None
        and (now - _cached_at) < settings.CACHE_TTL_SECONDS
    )


def get_dataset(force_refresh: bool = False) -> dict:
    global _cached_at, _cached_dataset

    now = time.time()
    with _cache_lock:
        if not force_refresh and _is_cache_valid(now):
            return _cached_dataset

        _cached_dataset = build_json.generate_dataset()
        _cached_at = now
        return _cached_dataset


def get_cache_status() -> dict:
    now = time.time()
    with _cache_lock:
        return {
            "cache_ttl_seconds": settings.CACHE_TTL_SECONDS,
            "cached": _cached_dataset is not None,
            "age_seconds": int(now - _cached_at) if _cached_dataset is not None else None,
        }
