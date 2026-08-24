"""SAP instance availability analyzer — GetSystemInstanceList / GetProcessList data."""
from __future__ import annotations

from collections import Counter
from typing import Any

import domain_registry as dr
from analyzers import register


@register("availability", "SAP_system_availability", "SAP_Process_Availability")
def analyze_availability(rows: list[dict], context: str) -> dict[str, Any]:
    """Classify SAP instance availability from GetSystemInstanceList data."""
    total = len(rows)

    # ── helpers ───────────────────────────────────────────────────────────────
    def _instance_type(features: str) -> str:
        f = features.upper()
        if "MESSAGESERVER" in f and "ENQUE" in f:
            return "ASCS"
        if "ENQREP" in f:
            return "ERS"
        if "WEBDISP" in f:
            return "WebDispatcher"
        if "TREX" in f:
            return "TREX"
        if "ICMAN" in f or "ABAP" in f:
            return "AppServer"
        return "Unknown"

    def _status_bucket(dispstatus: str) -> str:
        if dispstatus in ("SAPControl-RED", "SAPControl-GRAY"):
            return "DOWN"
        if dispstatus == "SAPControl-YELLOW":
            return "YELLOW"
        return ""

    _STATUS_LABEL: dict[str, str] = {
        "SAPControl-GREEN":  "Available",
        "SAPControl-RED":    "Error",
        "SAPControl-GRAY":   "Offline",
        "SAPControl-YELLOW": "Degraded",
    }

    # ── group rows by instance ─────────────────────────────────────────────
    instance_latest:           dict[str, dict]     = {}
    instance_statuses:         dict[str, Counter]  = {}
    instance_down_timestamps:  dict[str, list]     = {}

    for row in rows:
        hostname   = str(row.get("hostname_s",   "")).strip()
        inst_raw   = str(row.get("instanceNr_d", "")).strip()
        try:
            inst_nr = str(int(float(inst_raw))).zfill(2)
        except ValueError:
            inst_nr = inst_raw.zfill(2) if inst_raw.isdigit() else inst_raw

        dispstatus = str(row.get("dispstatus_s",      "")).strip()
        timestamp  = str(row.get("serverTimestamp_t", "")).strip()

        key = f"{hostname}_{inst_nr}"

        if dispstatus:
            instance_statuses.setdefault(key, Counter())[dispstatus] += 1
            if dispstatus != "SAPControl-GREEN" and timestamp:
                instance_down_timestamps.setdefault(key, []).append(timestamp)

        if key not in instance_latest:
            instance_latest[key] = row
        else:
            existing_ts = str(instance_latest[key].get("serverTimestamp_t", "")).strip()
            if timestamp > existing_ts:
                instance_latest[key] = row

    # ── analyse each instance ──────────────────────────────────────────────
    critical_findings: list[dict] = []
    warnings:          list[dict] = []
    informational:     list[dict] = []
    instance_summary:  list[dict] = []

    ascs_healthy      = True
    ascs_seen         = False
    app_servers_up    = 0
    app_servers_total = 0

    for key in sorted(instance_latest):
        row        = instance_latest[key]
        hostname   = str(row.get("hostname_s",   "")).strip()
        features   = str(row.get("features_s",   "")).strip()
        dispstatus = str(row.get("dispstatus_s", "")).strip()
        inst_raw   = str(row.get("instanceNr_d", "")).strip()
        try:
            inst_nr = str(int(float(inst_raw))).zfill(2)
        except ValueError:
            inst_nr = inst_raw.zfill(2) if inst_raw.isdigit() else inst_raw

        inst_type    = _instance_type(features)
        status_label = _STATUS_LABEL.get(dispstatus, dispstatus)
        status_counts = instance_statuses.get(key, Counter())
        all_statuses  = set(status_counts.keys()) or {dispstatus}
        bucket        = _status_bucket(dispstatus)

        green_count   = status_counts.get("SAPControl-GREEN", 0)
        total_samples = sum(status_counts.values())
        down_count_i  = total_samples - green_count
        intermittent  = green_count > 0 and down_count_i > 0

        instance_summary.append({
            "instance":              key,
            "hostname":              hostname,
            "instance_nr":           inst_nr,
            "instance_type":         inst_type,
            "current_status":        status_label,
            "intermittent_failures": intermittent,
        })

        # ── ASCS ──────────────────────────────────────────────────────────
        if inst_type == "ASCS":
            ascs_seen = True
            if bucket == "DOWN":
                ascs_healthy = False
                info = dr.classify_nw_instance("ASCS", "DOWN")
                critical_findings.append({
                    "instance": key, "instance_type": inst_type,
                    "current_status": status_label,
                    "issue": f"ASCS ({hostname}) is {status_label} — {info['meaning']}",
                    "investigation_hints": info["investigation_hints"],
                })
            elif bucket == "YELLOW":
                info = dr.classify_nw_instance("ASCS", "YELLOW")
                warnings.append({
                    "instance": key, "instance_type": inst_type,
                    "current_status": status_label,
                    "issue": f"ASCS ({hostname}) is DEGRADED. {info['meaning']}",
                    "investigation_hints": info["investigation_hints"],
                })

        elif inst_type == "AppServer":
            app_servers_total += 1
            if dispstatus == "SAPControl-GREEN":
                app_servers_up += 1
            elif bucket == "DOWN":
                info = dr.classify_nw_instance("AppServer", "DOWN")
                warnings.append({
                    "instance": key, "instance_type": inst_type,
                    "current_status": status_label,
                    "issue": f"Application server '{hostname}' (instance {inst_nr}) is {status_label}. {info['meaning']}",
                    "investigation_hints": info["investigation_hints"],
                })
            elif bucket == "YELLOW":
                info = dr.classify_nw_instance("AppServer", "YELLOW")
                warnings.append({
                    "instance": key, "instance_type": inst_type,
                    "current_status": status_label,
                    "issue": f"Application server '{hostname}' (instance {inst_nr}) is DEGRADED. {info['meaning']}",
                    "investigation_hints": info["investigation_hints"],
                })

        elif inst_type == "ERS":
            if bucket == "DOWN":
                info = dr.classify_nw_instance("ERS", "DOWN")
                warnings.append({
                    "instance": key, "instance_type": inst_type,
                    "current_status": status_label,
                    "issue": f"Enqueue Replication Server '{hostname}' (instance {inst_nr}) is {status_label}. {info['meaning']}",
                    "investigation_hints": info["investigation_hints"],
                })

        elif inst_type == "WebDispatcher":
            if bucket == "DOWN":
                info = dr.classify_nw_instance("WebDispatcher", "DOWN")
                warnings.append({
                    "instance": key, "instance_type": inst_type,
                    "current_status": status_label,
                    "issue": f"Web Dispatcher '{hostname}' is {status_label}. {info['meaning']}",
                    "investigation_hints": info["investigation_hints"],
                })

        elif inst_type == "Unknown":
            if bucket in ("DOWN", "YELLOW"):
                info = dr.classify_nw_instance("Unknown", bucket)
                warnings.append({
                    "instance": key, "instance_type": inst_type,
                    "current_status": status_label,
                    "issue": f"Instance '{hostname}' (instance {inst_nr}) has an unrecognised role and is {status_label}. {info['meaning']}",
                    "investigation_hints": info["investigation_hints"],
                })

        # ── Intermittent failure ───────────────────────────────────────────
        if intermittent:
            info = dr.classify_nw_instance(inst_type, "INTERMITTENT")
            raw_ts = sorted(instance_down_timestamps.get(key, []))
            capped_ts = raw_ts[:10]
            first_down = raw_ts[0] if raw_ts else None
            last_down  = raw_ts[-1] if raw_ts else None
            warnings.append({
                "instance": key, "instance_type": inst_type,
                "current_status": status_label,
                "issue": (
                    f"Instance '{key}' ({inst_type}) showed INTERMITTENT status changes — "
                    f"{down_count_i} non-GREEN samples out of {total_samples} total. "
                    f"First down: {first_down}  |  Last down: {last_down}"
                ),
                "investigation_hints": info["investigation_hints"],
            })

    # ── Aggregate findings ─────────────────────────────────────────────────────
    if app_servers_total > 0 and app_servers_up == 0 and ascs_healthy and ascs_seen:
        info = dr.classify_nw_instance("AppServer", "ALL_DOWN")
        critical_findings.append({
            "instance": "all_app_servers", "instance_type": "AppServer",
            "current_status": "All Down",
            "issue": f"All {app_servers_total} application server(s) are DOWN while ASCS is healthy. {info['meaning']}",
            "investigation_hints": info["investigation_hints"],
        })

    if app_servers_total > 1 and 0 < app_servers_up < app_servers_total:
        down_count = app_servers_total - app_servers_up
        info = dr.classify_nw_instance("AppServer", "PARTIAL_DOWN")
        warnings.append({
            "instance": "partial_app_servers", "instance_type": "AppServer",
            "current_status": f"{down_count}/{app_servers_total} Down",
            "issue": f"{down_count} of {app_servers_total} application server(s) are DOWN. {info['meaning']}",
            "investigation_hints": info["investigation_hints"],
        })

    if not ascs_seen:
        info = dr.classify_nw_instance("ASCS", "NOT_SEEN")
        informational.append({"issue": info["meaning"], "investigation_hints": info["investigation_hints"]})
    if app_servers_total == 0:
        info = dr.classify_nw_instance("AppServer", "NOT_SEEN")
        informational.append({"issue": info["meaning"], "investigation_hints": info["investigation_hints"]})

    # ── Overall severity ──────────────────────────────────────────────────
    if critical_findings:
        severity = "critical"
    elif any(w.get("instance_type") == "AppServer" and w.get("current_status") in ("Error", "Offline") for w in warnings):
        severity = "high"
    elif warnings:
        severity = "medium"
    elif informational:
        severity = "informational"
    else:
        severity = "healthy"

    # System health label
    if not ascs_healthy or not ascs_seen or critical_findings:
        system_health = "Offline"
    elif app_servers_total > 0 and app_servers_up == 0:
        system_health = "Offline"
    elif app_servers_up < app_servers_total:
        system_health = "Partially Running"
    elif any(w.get("current_status") == "Degraded" for w in warnings):
        system_health = "Degraded"
    else:
        system_health = "Available"

    # When healthy, omit instance_summary to save tokens
    include_instance_summary = severity != "healthy"

    return {
        "status":             "success",
        "analysis_type":      "availability",
        "summary": (
            f"{total} availability record(s) analysed across "
            f"{len(instance_latest)} instance(s). "
            f"System health: {system_health}. "
            f"ASCS: {'healthy' if ascs_healthy else 'DOWN'}. "
            f"App servers up: {app_servers_up}/{app_servers_total}. "
            f"Findings: {len(critical_findings)} critical, "
            f"{len(warnings)} warning(s), {len(informational)} informational."
        ),
        "severity":           severity,
        "system_health":      system_health,
        "ascs_healthy":       ascs_healthy,
        "app_servers_up":     app_servers_up,
        "app_servers_total":  app_servers_total,
        **({"instance_summary": instance_summary} if include_instance_summary else {}),
        "critical_findings":  critical_findings,
        "warnings":           warnings,
        "informational":      informational,
        "raw_row_count":      total,
        "context":            context,
    }
