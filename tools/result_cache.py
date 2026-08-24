"""Server-side result cache for progressive disclosure.

Caches full query results keyed by query_id so the model can:
  1. Get a summary from execute_query (cheap)
  2. Drill into details via get_details (only when needed)

Results are evicted after TTL expires. Cache is in-memory (single-process).
"""
from __future__ import annotations

import hashlib
import time
import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class CachedResult:
    """A cached query result with metadata."""
    query_id: str
    rows: list[dict]
    row_count: int
    analysis_type: str
    classified: dict | None  # Full classified output (if analyzer ran)
    sid: str
    kql: str
    created_at: float = field(default_factory=time.time)
    ttl_seconds: int = 300  # 5 minutes default

    @property
    def is_expired(self) -> bool:
        return (time.time() - self.created_at) > self.ttl_seconds


# Module-level cache store
_cache: dict[str, CachedResult] = {}

# Max cache entries to prevent memory leak
_MAX_ENTRIES = 50


def _evict_expired() -> None:
    """Remove expired entries."""
    expired = [k for k, v in _cache.items() if v.is_expired]
    for k in expired:
        del _cache[k]


def _evict_oldest() -> None:
    """Remove oldest entry if cache is full."""
    if len(_cache) >= _MAX_ENTRIES:
        oldest_key = min(_cache, key=lambda k: _cache[k].created_at)
        del _cache[oldest_key]


def generate_query_id(kql: str, sid: str) -> str:
    """Generate a short, unique query ID."""
    # Combine a hash prefix (for dedup) with a uuid suffix (for uniqueness)
    hash_prefix = hashlib.sha256(f"{kql}:{sid}:{time.time()}".encode()).hexdigest()[:8]
    return f"q_{hash_prefix}"


def store(
    query_id: str,
    rows: list[dict],
    analysis_type: str,
    classified: dict | None,
    sid: str,
    kql: str,
    ttl_seconds: int = 300,
) -> CachedResult:
    """Store query results in the cache."""
    _evict_expired()
    _evict_oldest()

    entry = CachedResult(
        query_id=query_id,
        rows=rows,
        row_count=len(rows),
        analysis_type=analysis_type,
        classified=classified,
        sid=sid,
        kql=kql,
        ttl_seconds=ttl_seconds,
    )
    _cache[query_id] = entry
    return entry


def get(query_id: str) -> CachedResult | None:
    """Retrieve a cached result. Returns None if not found or expired."""
    _evict_expired()
    entry = _cache.get(query_id)
    if entry is None or entry.is_expired:
        return None
    return entry


def get_detail_slice(
    query_id: str,
    category: str = "",
    offset: int = 0,
    limit: int = 5,
) -> dict:
    """Get a detail slice from cached results.

    If category is provided and a classified result exists, returns the
    investigation detail for that specific category/error type.
    Otherwise returns paginated raw rows.
    """
    entry = get(query_id)
    if entry is None:
        return {
            "status": "error",
            "error": f"query_id '{query_id}' not found or expired. Re-run the query.",
        }

    # If we have classified results and a category filter, slice by category
    if category and entry.classified:
        return _slice_classified(entry.classified, category, offset, limit)

    # Otherwise return paginated raw rows
    rows = entry.rows[offset:offset + limit]
    return {
        "status": "success",
        "query_id": query_id,
        "slice": "raw_rows",
        "offset": offset,
        "limit": limit,
        "total_rows": entry.row_count,
        "rows": rows,
        "has_more": (offset + limit) < entry.row_count,
    }


def _slice_classified(classified: dict, category: str, offset: int, limit: int) -> dict:
    """Extract detail for a specific category from classified results."""
    analysis_type = classified.get("analysis_type", "")

    # For short_dumps / batch_jobs: filter error_investigation by category
    if "error_investigation" in classified:
        matching = [
            e for e in classified["error_investigation"]
            if e.get("category", "").lower() == category.lower()
            or e.get("runtime_error", "").lower() == category.lower()
        ]
        if matching:
            sliced = matching[offset:offset + limit]
            return {
                "status": "success",
                "query_id": classified.get("_query_id", ""),
                "slice": "error_investigation",
                "filter": category,
                "items": sliced,
                "total_matching": len(matching),
                "has_more": (offset + limit) < len(matching),
            }

    # For system_logs: filter next_investigation_steps by category
    if "next_investigation_steps" in classified:
        matching = [
            s for s in classified["next_investigation_steps"]
            if s.get("category", "").lower() == category.lower()
            or s.get("message_group", "").lower() == category.lower()
        ]
        if matching:
            sliced = matching[offset:offset + limit]
            return {
                "status": "success",
                "query_id": classified.get("_query_id", ""),
                "slice": "investigation_steps",
                "filter": category,
                "items": sliced,
                "total_matching": len(matching),
                "has_more": (offset + limit) < len(matching),
            }

    # For ha_cluster / availability: filter findings by category or severity
    for findings_key in ("critical_findings", "warnings", "informational"):
        if findings_key in classified:
            matching = [
                f for f in classified[findings_key]
                if category.lower() in (
                    f.get("category", "").lower(),
                    f.get("metric", "").lower(),
                    f.get("instance_type", "").lower(),
                    findings_key.replace("_findings", "").lower(),
                )
            ]
            if matching:
                sliced = matching[offset:offset + limit]
                return {
                    "status": "success",
                    "query_id": classified.get("_query_id", ""),
                    "slice": findings_key,
                    "filter": category,
                    "items": sliced,
                    "total_matching": len(matching),
                    "has_more": (offset + limit) < len(matching),
                }

    # Fallback: category not found
    return {
        "status": "no_match",
        "query_id": classified.get("_query_id", ""),
        "error": f"No findings matching category '{category}' in cached results.",
        "available_categories": _extract_categories(classified),
    }


def _extract_categories(classified: dict) -> list[str]:
    """Extract available category names from classified results for guidance."""
    cats: set[str] = set()

    if "error_investigation" in classified:
        for e in classified["error_investigation"]:
            if e.get("category"):
                cats.add(e["category"])
            if e.get("runtime_error"):
                cats.add(e["runtime_error"])

    if "next_investigation_steps" in classified:
        for s in classified["next_investigation_steps"]:
            if s.get("category"):
                cats.add(s["category"])

    if "category_breakdown" in classified:
        for cb in classified["category_breakdown"]:
            if cb.get("category"):
                cats.add(cb["category"])

    for key in ("critical_findings", "warnings"):
        for f in classified.get(key, []):
            if f.get("category"):
                cats.add(f["category"])

    return sorted(cats)
