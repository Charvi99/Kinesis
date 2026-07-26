"""
Shared Massive/Polygon REST client for the alternative-data backfills.

One place for: API key, host, paginated GET, 429/5xx backoff. All
fetch_<source>.py scripts import `polygon_get` / `polygon_paginate` from here.

Host: api.polygon.io  (Polygon rebranded the *docs* to massive.com; the REST
host is unchanged — verified against the live news backfill
`fetch_historical_news.py`, which hits the same host).
Auth: ?apiKey=<POLYGON_API_KEY> query param (same as fetch_historical_news.py).

Pagination: Polygon returns {results:[...], next_url:<url?>}. `polygon_paginate`
follows next_url (re-adding apiKey, which next_url omits) until exhausted.

NOTE on the vX SEC-filing endpoints (form-4, 8-K, 13-F): they IGNORE the
ticker/cusip filter params and page GLOBALLY by date — see probe notes in the
individual fetch_*.py scripts. The ticker-filterable endpoints (short-interest,
short-volume, risk-factors, float) paginate per-stock.
"""
from __future__ import annotations

import logging
import os
import time
from typing import Dict, Iterator, Optional
from urllib.parse import parse_qsl, urlencode, urlsplit

import requests

log = logging.getLogger(__name__)

BASE_URL = "https://api.polygon.io"
API_KEY = os.getenv("POLYGON_API_KEY")

# Paid tier is generous, but backfills run sequenced — keep a small floor to
# stay well under rate ceilings across many requests.
RATE_LIMIT_DELAY = float(os.getenv("POLYGON_DELAY", "0.15"))
MAX_RETRIES = 6

_session = requests.Session()


class NotAuthorized(Exception):
    """Raised on HTTP 403 — the current plan is not entitled to the endpoint."""


def _with_api_key(url: str) -> str:
    """Ensure a URL (incl. Polygon next_url) carries the apiKey query param."""
    parts = urlsplit(url)
    qs = dict(parse_qsl(parts.query))
    qs.setdefault("apiKey", API_KEY or "")
    return parts._replace(query=urlencode(qs)).geturl()


def _request(url: str, params: Optional[Dict], timeout: int = 30) -> requests.Response:
    """GET with exponential backoff on 429/5xx/network errors."""
    backoff = 1.0
    for attempt in range(MAX_RETRIES):
        try:
            r = _session.get(url, params=params, timeout=timeout)
            if r.status_code == 429 or r.status_code >= 500:
                log.warning("polygon %s -> %s; retry %.1fs", url, r.status_code, backoff)
                time.sleep(backoff)
                backoff *= 2
                continue
            return r
        except requests.RequestException as e:
            log.warning("polygon %s network error %s; retry %.1fs", url, e, backoff)
            time.sleep(backoff)
            backoff *= 2
    raise RuntimeError(f"polygon request failed after {MAX_RETRIES} retries: {url}")


def polygon_get(path: str, params: Optional[Dict] = None) -> Dict:
    """Single GET -> parsed JSON. Raises NotAuthorized on 403."""
    if not API_KEY or API_KEY == "demo":
        raise RuntimeError("POLYGON_API_KEY not set (or 'demo') — cannot backfill.")
    url = _with_api_key(BASE_URL + path)
    r = _request(url, params)
    if r.status_code == 403:
        raise NotAuthorized(f"{path}: {r.text[:200]}")
    r.raise_for_status()
    time.sleep(RATE_LIMIT_DELAY)
    return r.json()


def polygon_paginate(
    path: str,
    params: Optional[Dict] = None,
    max_pages: int = 5000,
) -> Iterator[Dict]:
    """Yield result records, following next_url until exhausted or max_pages.

    `path` is the endpoint path on the first call (BASE_URL prepended, apiKey
    added); subsequent calls follow the returned next_url verbatim (+ apiKey).
    """
    if not API_KEY or API_KEY == "demo":
        raise RuntimeError("POLYGON_API_KEY not set (or 'demo') — cannot backfill.")
    url = _with_api_key(BASE_URL + path)
    use_params = params
    for page in range(max_pages):
        r = _request(url, use_params)
        if r.status_code == 403:
            raise NotAuthorized(f"{path}: {r.text[:200]}")
        r.raise_for_status()
        j = r.json()
        for rec in (j.get("results") or []):
            yield rec
        nxt = j.get("next_url")
        time.sleep(RATE_LIMIT_DELAY)
        if not nxt:
            return
        url = _with_api_key(nxt)
        use_params = None  # next_url carries cursor + all params
    log.warning("polygon_paginate %s hit max_pages=%d (truncated)", path, max_pages)
