"""OS metrics analyzer — Prometheus_OSExporter_CL node exporter data."""
from __future__ import annotations

from typing import Any

import domain_registry as dr
from analyzers import register


@register("os_metrics")
def analyze_os_metrics(rows: list[dict], context: str) -> dict[str, Any]:
    """Classify and interpret Prometheus OS node exporter metrics."""
    total = len(rows)

    # Separate sapmon heartbeat rows — not an OS metric
    metric_rows = [r for r in rows if str(r.get("name_s", "")).strip() != "sapmon"]
    sapmon_count = total - len(metric_rows)

    metric_names: set[str] = {
        str(r.get("name_s", "")).strip() for r in metric_rows if r.get("name_s")
    }
    instances: set[str] = {
        str(r.get("instance_s", "")).strip() for r in metric_rows if r.get("instance_s")
    }
    sids: set[str] = {
        str(r.get("SID_s", "")).strip() for r in metric_rows if r.get("SID_s")
    }

    # Classify each unique metric and group by category
    categories: dict[str, list[dict]] = {}
    unknown_metrics: list[str] = []
    metrics_with_thresholds: list[dict] = []

    for metric_name in sorted(metric_names):
        info     = dr.classify_os_metric(metric_name)
        category = info.get("category", "Unknown")
        if category == "Unknown":
            unknown_metrics.append(metric_name)
            continue
        entry: dict = {
            "metric":              metric_name,
            "metric_type":         info.get("metric_type", "unknown"),
            "meaning":             info.get("meaning", ""),
            "investigation_hints": info.get("investigation_hints", []),
        }
        if info.get("filter_hints"):
            entry["filter_hints"] = info["filter_hints"]
        if info.get("thresholds"):
            entry["thresholds"] = info["thresholds"]
            metrics_with_thresholds.append({
                "metric":     metric_name,
                "category":   category,
                "thresholds": info["thresholds"],
            })
        categories.setdefault(category, []).append(entry)

    # Category overview
    category_summary: list[dict] = [
        {
            "category":     cat,
            "metrics_seen": [m["metric"] for m in categories[cat]],
            "metric_count": len(categories[cat]),
        }
        for cat in sorted(categories)
    ]

    # Per-category investigation hints (de-duplicated)
    investigation_by_category: list[dict] = []
    for cat in sorted(categories):
        seen: set[str] = set()
        hints: list[str] = []
        for m in categories[cat]:
            for h in m.get("investigation_hints", []):
                if h not in seen:
                    seen.add(h)
                    hints.append(h)
        if hints:
            investigation_by_category.append({
                "category":            cat,
                "investigation_hints": hints,
            })

    return {
        "status":        "success",
        "analysis_type": "os_metrics",
        "summary": (
            f"{total} OS metric row(s) ({len(metric_rows)} metric rows, "
            f"{sapmon_count} sapmon heartbeat row(s) excluded). "
            f"Unique metrics: {len(metric_names)} across {len(categories)} categories. "
            f"Instances: {', '.join(sorted(instances))}. "
            f"{len(metrics_with_thresholds)} metric(s) have threshold guidance — "
            f"apply KQL delta computation to evaluate actuals."
        ),
        "severity":                  "informational",
        "instances":                 sorted(instances),
        "sids":                      sorted(sids),
        "category_summary":          category_summary,
        "metrics_by_category":       {cat: categories[cat] for cat in sorted(categories)},
        "threshold_guidance":        metrics_with_thresholds,
        "investigation_by_category": investigation_by_category,
        "unknown_metrics":           unknown_metrics,
        "raw_row_count":             total,
        "context":                   context,
    }
