"""Polite HTTP: identifies itself, caches, retries with backoff, never bypasses blocks."""
from __future__ import annotations

import hashlib
import time
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlsplit

import requests

from .. import config


class SourceBlocked(RuntimeError):
    """Raised on 401/403/429: we stop rather than attempt to circumvent."""


# Request counts for the current run (issue #61): network requests vs answers served from the disk
# cache, per host. `python -m sbi daily` resets them at the start and logs them in job `http-requests`.
_STATS: dict[str, dict[str, int]] = {}


def reset_stats() -> None:
    _STATS.clear()


def count(url: str, kind: str) -> None:
    """kind: 'network' (a request was sent), 'cache' (served from disk) or 'stale' (network failed,
    stale cache used). Never records the query string, so keys can never leak into the log."""
    host = urlsplit(url).netloc or "?"
    h = _STATS.setdefault(host, {"network": 0, "cache": 0, "stale": 0})
    h[kind] = h.get(kind, 0) + 1


def stats() -> dict:
    """{"network": n, "cache": n, "stale": n, "by_host": {host: {...}}} for the current run."""
    tot = {k: sum(h.get(k, 0) for h in _STATS.values()) for k in ("network", "cache", "stale")}
    return {**tot, "by_host": {h: dict(v) for h, v in sorted(_STATS.items())}}


def fetch(url: str, max_age_hours: float = 6.0, retries: int = 3, timeout: int = 30) -> tuple[bytes, str | None]:
    """Return (content, last_modified_iso). Cached on disk for `max_age_hours`."""
    config.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha1(url.encode()).hexdigest()
    body_p = config.CACHE_DIR / f"{key}.bin"
    meta_p = config.CACHE_DIR / f"{key}.meta"
    if body_p.exists() and (time.time() - body_p.stat().st_mtime) < max_age_hours * 3600:
        count(url, "cache")
        return body_p.read_bytes(), (meta_p.read_text() or None) if meta_p.exists() else None

    last_exc: Exception | None = None
    for attempt in range(retries):
        try:
            count(url, "network")
            r = requests.get(url, headers={"User-Agent": config.USER_AGENT}, timeout=timeout)
            if r.status_code in (401, 403, 429):
                raise SourceBlocked(f"{url} -> HTTP {r.status_code}; not retrying/circumventing")
            r.raise_for_status()
            lm = r.headers.get("Last-Modified")
            lm_iso = parsedate_to_datetime(lm).isoformat() if lm else None
            body_p.write_bytes(r.content)
            meta_p.write_text(lm_iso or "")
            return r.content, lm_iso
        except SourceBlocked:
            raise
        except Exception as e:  # noqa: BLE001
            last_exc = e
            time.sleep(2 ** attempt)
    # Fall back to stale cache rather than failing the whole run.
    if body_p.exists():
        count(url, "stale")
        return body_p.read_bytes(), (meta_p.read_text() or None) if meta_p.exists() else None
    raise RuntimeError(f"fetch failed for {url}: {last_exc}")
