"""Batch jobs analyzer — SM37 batch job data.

Handles both BatchJobs_CL (standard) and BatchJobLog_CL (detailed aborted) formats.
"""
from __future__ import annotations

from collections import Counter
from typing import Any

import domain_registry as dr
from analyzers import register


@register("batch_jobs")
def analyze_batch_jobs(rows: list[dict], context: str) -> dict[str, Any]:
    """Classify and aggregate batch job data."""
    # Detect BatchJobLog_CL format (has jobname_s, runtime_error_s, job_status_s)
    if rows and "jobname_s" in rows[0]:
        return _analyze_batch_job_log(rows, context)

    total         = len(rows)
    status_counts = Counter(str(r.get("STATUS_s", "")).strip() for r in rows)
    failed        = [r for r in rows if str(r.get("STATUS_s", "")).strip() == "A"]

    failed_classes = Counter(str(r.get("JOBCLASS_s", "")).strip() for r in failed)
    if failed_classes.get("A", 0) > 0:
        severity = "Critical"
    elif failed:
        severity = "High"
    else:
        severity = "None"

    jobclass_breakdown = [
        {
            "job_class": cls,
            "label":     {"A": "High", "B": "Medium", "C": "Low"}.get(cls, "Unknown"),
            "count":     cnt,
        }
        for cls, cnt in sorted(failed_classes.items(), key=lambda x: x[0])
    ]

    job_counts = Counter(str(r.get("JOBNAME_s", "")).strip() for r in failed if r.get("JOBNAME_s"))
    top_failed = job_counts.most_common(5)

    # Build status_breakdown with meaning + investigation_hints
    status_breakdown = []
    for code, cnt in status_counts.most_common():
        decoded = dr.decode_job_status(code)
        entry = {
            "status_code": code,
            "label":       decoded["label"],
            "is_failure":  decoded["is_failure"],
            "description": decoded.get("description", ""),
            "count":       cnt,
        }
        if "meaning" in decoded:
            entry["meaning"] = decoded["meaning"]
        if "investigation_hints" in decoded:
            entry["investigation_hints"] = decoded["investigation_hints"]
        status_breakdown.append(entry)

    # Build status_investigation for notable statuses
    notable_codes = {"A", "Z", "Y"}
    status_investigation = []
    for code, cnt in status_counts.most_common():
        if code not in notable_codes:
            continue
        decoded = dr.decode_job_status(code)
        if "meaning" not in decoded:
            continue
        status_rows = [r for r in rows if str(r.get("STATUS_s", "")).strip() == code]
        start_times = sorted({
            f"{str(r.get('STRTDATE_s', '')).strip()} {str(r.get('STRTTIME_s', '')).strip()}"
            for r in status_rows
            if r.get("STRTDATE_s") and r.get("STRTTIME_s")
        })
        filter_context = {
            "job_names":    sorted({str(r.get("JOBNAME_s",   "")).strip() for r in status_rows if r.get("JOBNAME_s")}),
            "scheduled_by": sorted({str(r.get("SDLUNAME_s",  "")).strip() for r in status_rows if r.get("SDLUNAME_s")}),
            "released_by":  sorted({str(r.get("RELUNAME_s",  "")).strip() for r in status_rows if r.get("RELUNAME_s")}),
            "servers":      sorted({str(r.get("REAXSERVER_s","")).strip() for r in status_rows if r.get("REAXSERVER_s")}),
            "job_classes":  sorted({str(r.get("JOBCLASS_s",  "")).strip() for r in status_rows if r.get("JOBCLASS_s")}),
            "start_times":  start_times,
        }
        status_investigation.append({
            "status_code":         code,
            "label":               decoded["label"],
            "count":               cnt,
            "meaning":             decoded["meaning"],
            "investigation_hints": decoded["investigation_hints"],
            "filter_context":      filter_context,
        })

    return {
        "status":         "success",
        "analysis_type":  "batch_jobs",
        "summary": (
            f"{total} job records. {len(failed)} cancelled (STATUS_s='A'). "
            f"High-priority (Class A) cancellations: {failed_classes.get('A', 0)}."
        ),
        "severity":            severity,
        "status_breakdown":    status_breakdown,
        "status_investigation": status_investigation,
        "cancelled_job_class_breakdown": jobclass_breakdown,
        "top_cancelled_jobs":  [{"job": j, "count": c} for j, c in top_failed],
        "raw_row_count":       total,
        "context":             context,
    }


def _analyze_batch_job_log(rows: list[dict], context: str) -> dict[str, Any]:
    """Classify BatchJobLog_CL rows — detailed aborted job analysis."""
    total = len(rows)

    error_counts   = Counter(str(r.get("runtime_error_s", "")).strip() for r in rows)
    program_counts = Counter(str(r.get("failed_step_program_s", "")).strip() for r in rows if r.get("failed_step_program_s"))
    job_counts     = Counter(str(r.get("jobname_s", "")).strip() for r in rows if r.get("jobname_s"))
    host_counts    = Counter(str(r.get("hostname_s", "")).strip() for r in rows if r.get("hostname_s"))
    user_counts    = Counter(str(r.get("failed_step_user_s", "")).strip() for r in rows if r.get("failed_step_user_s"))

    error_investigation: list[dict] = []
    for error_code, count in error_counts.most_common():
        if not error_code:
            continue
        info = dr.classify_runtime_error(error_code)
        error_rows = [r for r in rows if str(r.get("runtime_error_s", "")).strip() == error_code]
        affected_jobs     = sorted({str(r.get("jobname_s", "")).strip() for r in error_rows if r.get("jobname_s")})
        affected_programs = sorted({str(r.get("failed_step_program_s", "")).strip() for r in error_rows if r.get("failed_step_program_s")})
        affected_hosts    = sorted({str(r.get("hostname_s", "")).strip() for r in error_rows if r.get("hostname_s")})
        affected_users    = sorted({str(r.get("failed_step_user_s", "")).strip() for r in error_rows if r.get("failed_step_user_s")})
        sample_errors = sorted({str(r.get("error_message_s", "")).strip() for r in error_rows if r.get("error_message_s")})[:3]
        sample_logs   = [str(r.get("job_log_text_s", "")).strip()[:300] for r in error_rows[:2] if r.get("job_log_text_s")]

        error_investigation.append({
            "runtime_error":       error_code,
            "category":            info["category"],
            "subcategory":         info["subcategory"],
            "meaning":             info.get("meaning", ""),
            "count":               count,
            "affected_jobs":       affected_jobs,
            "affected_programs":   affected_programs,
            "affected_hosts":      affected_hosts,
            "affected_users":      affected_users,
            "sample_error_messages": sample_errors,
            "sample_log_snippets": sample_logs,
            "investigation_hints": info.get("investigation_hints", []),
        })

    # Jobs without a classified runtime error
    no_error_rows = [r for r in rows if not str(r.get("runtime_error_s", "")).strip()]
    unclassified_jobs: list[dict] = []
    if no_error_rows:
        for row in no_error_rows[:5]:
            unclassified_jobs.append({
                "jobname":       str(row.get("jobname_s", "")).strip(),
                "jobcount":      str(row.get("jobcount_s", "")).strip(),
                "program":       str(row.get("failed_step_program_s", "")).strip(),
                "error_message": str(row.get("error_message_s", "")).strip()[:200],
                "log_snippet":   str(row.get("job_log_text_s", "")).strip()[:200],
            })

    periodic_count = sum(1 for r in rows if str(r.get("is_periodic_s", "")).strip() == "X")
    severity = "Critical" if total >= 5 else "High" if total > 0 else "None"

    return {
        "status":              "success",
        "analysis_type":       "batch_jobs",
        "data_source":         "SapNetweaver_BatchJobLog_CL",
        "summary": (
            f"{total} aborted job(s) with detailed log analysis. "
            f"{len(error_counts) - (1 if '' in error_counts else 0)} unique runtime error type(s). "
            f"Top failing jobs: {', '.join(j for j, _ in job_counts.most_common(3))}. "
            f"Periodic jobs affected: {periodic_count}."
        ),
        "severity":            severity,
        "error_investigation": error_investigation,
        "top_failed_jobs":     [{"job": j, "count": c} for j, c in job_counts.most_common(10)],
        "top_programs":        [{"program": p, "count": c} for p, c in program_counts.most_common(5)],
        "top_hosts":           [{"host": h, "count": c} for h, c in host_counts.most_common(5)],
        "top_users":           [{"user": u, "count": c} for u, c in user_counts.most_common(5)],
        "unclassified_jobs":   unclassified_jobs,
        "periodic_failures":   periodic_count,
        "raw_row_count":       total,
        "context":             context,
    }
