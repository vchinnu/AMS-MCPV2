"""Workload statistics analyzer — ST03N performance data.

Handles SapNetweaver_SWNC_CL — aggregated workload metrics per task type
(Dialog, Background, Update, RFC, etc.) per collection interval.

Key capabilities:
  - Per-task-type response time analysis with SLA evaluation
  - Response time breakdown into components (DB, CPU, Queue, RollWait, Processing)
  - Dominant component identification ("72% of response time is DB")
  - Throughput analysis (dialog steps/hour trending)
  - Sequential vs Direct read ratio (indicator of missing indexes)

Supports Scenarios 1 (Batch Job RCA) and 4 (Post-Maintenance Degradation).
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any

import domain_registry as dr
from analyzers import register


def _safe_float(val, default: float = 0.0) -> float:
    """Safely convert a value to float."""
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


@register("workload_statistics")
def analyze_workload(rows: list[dict], context: str) -> dict[str, Any]:
    """Classify and aggregate ST03N workload statistics.

    Flow:
      1. Group rows by Task_Type_Name_s → per-task-type analysis
      2. For each task type: compute avg/max response time, breakdown by component
      3. Identify dominant response time component
      4. Check SLA thresholds (DIALOG > 1000ms = poor UX)
      5. Analyze sequential vs direct read ratio (missing index indicator)
      6. Return structured task-type analysis with findings
    """
    if not rows:
        return {"status": "no_data", "analysis_type": "workload_statistics",
                "summary": "No SWNC workload data returned.", "raw_row_count": 0, "context": context}

    total = len(rows)

    # ── Step 1: Group rows by task type ──────────────────────────────────────
    task_groups: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        task_type = str(row.get("Task_Type_Name_s", "UNKNOWN")).strip()
        task_groups[task_type].append(row)

    # ── Step 2: Per-task-type analysis ───────────────────────────────────────
    task_type_analysis: list[dict] = []
    performance_findings: list[dict] = []

    for task_type, task_rows in sorted(task_groups.items()):
        task_info = dr.classify_task_type(task_type)
        n = len(task_rows)

        # ── Response time: avg and max ───────────────────────────────────────
        rt_values = [_safe_float(r.get("ST03_Avg_Resp_Time_d")) for r in task_rows]
        rt_values = [v for v in rt_values if v > 0]

        avg_rt = sum(rt_values) / len(rt_values) if rt_values else 0
        max_rt = max(rt_values) if rt_values else 0

        # ── Throughput: total dialog steps ───────────────────────────────────
        total_steps = sum(_safe_float(r.get("Total_Steps_d")) for r in task_rows)

        # ── Response time breakdown by component ─────────────────────────────
        # Each ST03_*_Time_d field is a fraction (0.0 – 1.0) of the response time.
        # We average the fractions across all rows to get the typical breakdown.
        component_fields = {
            "db":         "ST03_DB_Time_d",
            "cpu":        "ST03_CPU_Time_d",
            "queue":      "ST03_Queue_Time_d",
            "rollwait":   "ST03_RollWait_Time_d",
            "processing": "ST03_Processing_Time_d",
        }

        breakdown: dict[str, float] = {}
        for comp_name, field in component_fields.items():
            frac_values = [_safe_float(r.get(field)) for r in task_rows]
            frac_values = [v for v in frac_values if v >= 0]
            avg_frac = sum(frac_values) / len(frac_values) if frac_values else 0
            breakdown[comp_name] = round(avg_frac, 4)

        # ── Identify dominant component using domain knowledge ───────────────
        dominant_comp = None
        dominant_fraction = 0
        component_details: list[dict] = []
        for comp_name, frac in breakdown.items():
            classification = dr.classify_response_component(comp_name, frac)
            component_details.append(classification)
            if classification.get("is_dominant") and frac > dominant_fraction:
                dominant_comp = classification["label"]
                dominant_fraction = frac

        # ── SLA check for DIALOG task type ───────────────────────────────────
        sla_threshold = task_info.get("sla_threshold_ms")
        sla_breach = False
        if sla_threshold and avg_rt > sla_threshold:
            sla_breach = True
            performance_findings.append({
                "finding": "SLA_BREACH",
                "severity": "warning",
                "task_type": task_type,
                "avg_response_time_ms": round(avg_rt, 1),
                "sla_threshold_ms": sla_threshold,
                "meaning": f"{task_type} avg response time ({avg_rt:.0f}ms) exceeds SLA ({sla_threshold}ms).",
                "investigation_hints": [
                    f"Dominant component: {dominant_comp} ({dominant_fraction:.0%} of response time)."
                    if dominant_comp else "No single component dominates.",
                ],
            })

        # ── Finding for dominant component ───────────────────────────────────
        if dominant_comp and dominant_fraction > 0.5:
            finding_name = f"{dominant_comp.upper().replace('/', '_')}_BOUND"
            performance_findings.append({
                "finding": finding_name,
                "severity": "info",
                "task_type": task_type,
                "component": dominant_comp,
                "fraction": round(dominant_fraction, 3),
                "meaning": f"{task_type} workload is {dominant_comp}-bound ({dominant_fraction:.0%} of response time).",
                "investigation_hints": [h for cd in component_details
                                        if cd.get("is_dominant")
                                        for h in cd.get("investigation_hints", [])],
            })

        # ── Sequential vs Direct read ratio (missing index indicator) ────────
        total_seq_time = sum(_safe_float(r.get("Total_DB_Seq_Read_Time_d")) for r in task_rows)
        total_dir_time = sum(_safe_float(r.get("Total_DB_Dir_Read_Time_d")) for r in task_rows)
        seq_dir_ratio = total_seq_time / total_dir_time if total_dir_time > 0 else 0

        if seq_dir_ratio > 1.0 and total_seq_time > 0:
            performance_findings.append({
                "finding": "EXPENSIVE_SEQUENTIAL_READS",
                "severity": "warning",
                "task_type": task_type,
                "seq_dir_ratio": round(seq_dir_ratio, 2),
                "meaning": (
                    f"Sequential read time is {seq_dir_ratio:.1f}× higher than direct read time "
                    f"for {task_type} — this often indicates missing DB indexes or full table scans."
                ),
                "investigation_hints": [
                    "Check HANA SQL plan cache for expensive sequential scans.",
                    "Review programs with high DB time for missing WHERE clause optimization.",
                ],
            })

        # ── Build task-type summary entry ────────────────────────────────────
        task_entry = {
            "task_type": task_type,
            "label": task_info.get("label", task_type),
            "meaning": task_info.get("meaning", ""),
            "interval_count": n,
            "avg_response_time_ms": round(avg_rt, 1),
            "max_response_time_ms": round(max_rt, 1),
            "total_steps": int(total_steps),
            "response_time_breakdown": {
                f"{comp}_pct": round(frac * 100, 1) for comp, frac in breakdown.items()
            },
            "dominant_component": dominant_comp,
            "sla_breach": sla_breach,
        }
        task_type_analysis.append(task_entry)

    # ── Step 3: Overall throughput summary ───────────────────────────────────
    dialog_steps = sum(e["total_steps"] for e in task_type_analysis if e["task_type"] == "DIALOG")
    batch_steps  = sum(e["total_steps"] for e in task_type_analysis if e["task_type"] == "BACKGROUND")

    # ── Step 4: Determine overall severity ───────────────────────────────────
    severities = [f["severity"] for f in performance_findings]
    if "critical" in severities:
        overall_severity = "critical"
    elif "warning" in severities:
        overall_severity = "warning"
    else:
        overall_severity = "healthy"

    # ── Build summary text ───────────────────────────────────────────────────
    summary_parts = [
        f"{total} workload record(s) across {len(task_groups)} task type(s).",
        f"Dialog steps: {dialog_steps:,}." if dialog_steps else "",
        f"Batch steps: {batch_steps:,}." if batch_steps else "",
    ]
    if performance_findings:
        summary_parts.append(f"{len(performance_findings)} performance finding(s).")

    return {
        "status": "success",
        "analysis_type": "workload_statistics",
        "severity": overall_severity,
        "summary": " ".join(p for p in summary_parts if p),
        "task_type_analysis": task_type_analysis,
        "performance_findings": performance_findings,
        "throughput_summary": {
            "dialog_steps_total": int(dialog_steps),
            "batch_steps_total": int(batch_steps),
        },
        "raw_row_count": total,
        "context": context,
    }
