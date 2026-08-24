"""Generic statistical summarizer for query results without a domain analyzer.

When execute_query has no matching analysis_type, this module produces a compact
statistical summary instead of returning raw rows to the model.

Output includes:
  - Column type detection (numeric, categorical, time, other)
  - Numeric columns: min, max, avg, p95
  - Categorical columns: top-5 value distribution
  - Time columns: range (earliest, latest)
  - 3 sample rows for context
  - Total row count
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import Any


def summarize(result: dict[str, Any], context: str = "") -> dict[str, Any]:
    """Produce a generic statistical summary of query results.

    This is the fallback when no domain-specific analyzer exists.
    The model receives compact statistics instead of 1000 raw rows.
    """
    rows: list[dict] = result.get("rows", [])
    row_count = result.get("row_count", len(rows))

    if not rows:
        return {
            "status": "no_data",
            "summary": "Query returned no rows.",
            "row_count": 0,
            "context": context,
        }

    # Detect column types from first 50 rows (sample for efficiency)
    sample_for_typing = rows[:50]
    columns = _detect_columns(sample_for_typing)

    # Build statistics per column type
    numeric_stats = {}
    categorical_stats = {}
    time_stats = {}

    for col_name, col_type in columns.items():
        if col_type == "numeric":
            numeric_stats[col_name] = _numeric_summary(rows, col_name)
        elif col_type == "categorical":
            categorical_stats[col_name] = _categorical_summary(rows, col_name)
        elif col_type == "time":
            time_stats[col_name] = _time_summary(rows, col_name)

    # Select 3 representative sample rows (first, middle, last)
    sample_rows = _pick_samples(rows, count=3)

    # Build compact output
    output: dict[str, Any] = {
        "status": "success",
        "summary": (
            f"{row_count} row(s) returned. "
            f"Columns: {len(columns)} "
            f"({sum(1 for v in columns.values() if v == 'numeric')} numeric, "
            f"{sum(1 for v in columns.values() if v == 'categorical')} categorical, "
            f"{sum(1 for v in columns.values() if v == 'time')} time). "
            "No domain analyzer matched — showing statistical summary. "
            "Use get_details(query_id) for raw rows if needed."
        ),
        "row_count": row_count,
    }

    if numeric_stats:
        output["numeric_columns"] = numeric_stats
    if categorical_stats:
        output["categorical_columns"] = categorical_stats
    if time_stats:
        output["time_columns"] = time_stats
    if sample_rows:
        output["sample_rows"] = sample_rows

    if context:
        output["context"] = context

    return output


def _detect_columns(rows: list[dict]) -> dict[str, str]:
    """Detect column types from a sample of rows.

    Returns: {column_name: "numeric"|"categorical"|"time"|"other"}
    """
    if not rows:
        return {}

    # Collect all column names
    all_cols: set[str] = set()
    for row in rows:
        all_cols.update(row.keys())

    col_types: dict[str, str] = {}

    for col in sorted(all_cols):
        # Skip internal/metadata columns
        if col.startswith("_") or col in ("TenantId", "Type", "SourceSystem"):
            continue

        values = [row.get(col) for row in rows if row.get(col) is not None and str(row.get(col)).strip()]

        if not values:
            continue

        # Check if it's a time column (by name convention or ISO format)
        if _is_time_column(col, values[:5]):
            col_types[col] = "time"
        elif _is_numeric_column(values[:10]):
            col_types[col] = "numeric"
        else:
            col_types[col] = "categorical"

    return col_types


def _is_time_column(col_name: str, sample_values: list) -> bool:
    """Heuristic: is this a time/datetime column?"""
    time_suffixes = ("_t", "_dt", "Timestamp", "TimeGenerated", "Time", "Date", "_date", "_time")
    if any(col_name.endswith(s) or col_name == s for s in time_suffixes):
        return True
    # Check if values look like ISO timestamps
    for v in sample_values:
        s = str(v).strip()
        if len(s) >= 19 and "T" in s and ("Z" in s or "+" in s or s.count("-") >= 2):
            return True
    return False


def _is_numeric_column(sample_values: list) -> bool:
    """Heuristic: are these numeric values?"""
    numeric_count = 0
    for v in sample_values:
        try:
            float(v)
            numeric_count += 1
        except (TypeError, ValueError):
            pass
    return numeric_count > len(sample_values) * 0.7


def _numeric_summary(rows: list[dict], col: str) -> dict:
    """Compute min/max/avg/p95 for a numeric column."""
    values: list[float] = []
    for row in rows:
        v = row.get(col)
        if v is not None:
            try:
                values.append(float(v))
            except (TypeError, ValueError):
                pass

    if not values:
        return {"count": 0}

    values.sort()
    n = len(values)
    p95_idx = min(int(n * 0.95), n - 1)

    return {
        "count": n,
        "min": round(values[0], 2),
        "max": round(values[-1], 2),
        "avg": round(sum(values) / n, 2),
        "p95": round(values[p95_idx], 2),
    }


def _categorical_summary(rows: list[dict], col: str) -> dict:
    """Return top-5 value distribution for a categorical column."""
    counter: Counter = Counter()
    for row in rows:
        v = row.get(col)
        if v is not None and str(v).strip():
            counter[str(v).strip()] += 1

    unique_count = len(counter)
    top5 = counter.most_common(5)

    return {
        "unique_values": unique_count,
        "top_5": [{v: c} for v, c in top5],
    }


def _time_summary(rows: list[dict], col: str) -> dict:
    """Return time range (earliest, latest) for a time column."""
    timestamps: list[str] = []
    for row in rows:
        v = row.get(col)
        if v is not None and str(v).strip():
            timestamps.append(str(v).strip())

    if not timestamps:
        return {"count": 0}

    timestamps.sort()
    return {
        "count": len(timestamps),
        "earliest": timestamps[0],
        "latest": timestamps[-1],
    }


def _pick_samples(rows: list[dict], count: int = 3) -> list[dict]:
    """Pick representative sample rows: first, middle, last."""
    if len(rows) <= count:
        return rows

    indices = [0, len(rows) // 2, len(rows) - 1]
    samples = []
    for i in indices[:count]:
        # Compact the row: omit None/empty values
        row = {k: v for k, v in rows[i].items() if v is not None and str(v).strip()}
        samples.append(row)
    return samples
