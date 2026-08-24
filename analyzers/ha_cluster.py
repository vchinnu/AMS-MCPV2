"""HA cluster analyzer — Pacemaker / Corosync metrics from Prometheus_HaClusterExporter_CL."""
from __future__ import annotations

import json
from typing import Any

import domain_registry as dr
from analyzers import register


@register("ha_cluster")
def analyze_ha_cluster(rows: list[dict], context: str) -> dict[str, Any]:
    """Classify and interpret Prometheus HA cluster exporter metrics."""

    def _labels(row: dict) -> dict:
        try:
            raw = row.get("labels_s", "{}")
            return json.loads(raw) if isinstance(raw, str) and raw else {}
        except (ValueError, TypeError):
            return {}

    total = len(rows)
    critical_findings: list[dict] = []
    warnings: list[dict] = []
    informational: list[dict] = []

    # Cluster-state accumulators
    quorate: bool | None = None
    stonith_on: bool | None = None
    maintenance_active = False
    nodes_online: set[str] = set()
    nodes_unclean: set[str] = set()
    nodes_offline: set[str] = set()
    nodes_standby_onfail: set[str] = set()
    resources_active: set[str] = set()
    resources_failed: list[dict] = []
    resources_blocked: list[dict] = []
    resources_failure_ignored: list[dict] = []
    resources_stopped_no_node: list[dict] = []
    resources_unmanaged: list[dict] = []
    fail_counts: list[dict] = []
    scrape_failures: list[str] = []
    exporter_down: list[str] = []
    azure_stopping: list[dict] = []
    hana_sfail: list[dict] = []
    negative_infinity_score: list[dict] = []

    for row in rows:
        name  = str(row.get("name_s",     "")).strip()
        host  = str(row.get("hostname_s", "")).strip()
        try:
            value = float(row.get("value_d", 0))
        except (TypeError, ValueError):
            value = 0.0
        lbl = _labels(row)

        if name == "ha_cluster_corosync_quorate":
            quorate = (value == 1.0)
        elif name == "ha_cluster_pacemaker_stonith_enabled":
            stonith_on = (value == 1.0)
        elif name == "ha_cluster_pacemaker_maintenance_mode_enabled":
            if value == 1.0:
                maintenance_active = True
        elif name == "ha_cluster_pacemaker_nodes":
            if value == 1.0:
                status    = str(lbl.get("status", "")).strip()
                node_name = str(lbl.get("node", host)).strip()
                if status == "online":
                    nodes_online.add(node_name)
                elif status == "unclean":
                    nodes_unclean.add(node_name)
                elif status == "offline":
                    nodes_offline.add(node_name)
                elif status == "standby_onfail":
                    nodes_standby_onfail.add(node_name)
        elif name == "ha_cluster_pacemaker_resources":
            if value == 1.0:
                resource  = str(lbl.get("resource", "")).strip()
                status    = str(lbl.get("status",   "")).strip()
                role      = str(lbl.get("role",     "")).strip()
                node_name = str(lbl.get("node",     "")).strip()
                managed   = str(lbl.get("managed",  "true")).strip().lower()
                if status == "active" and managed == "true":
                    resources_active.add(resource)
                elif status == "failed":
                    resources_failed.append({"resource": resource, "node": node_name, "role": role})
                elif status == "blocked":
                    resources_blocked.append({"resource": resource, "node": node_name})
                elif status == "failure_ignored":
                    resources_failure_ignored.append({"resource": resource, "node": node_name})
                if role == "stopped" and not node_name:
                    resources_stopped_no_node.append({"resource": resource})
                if managed == "false":
                    resources_unmanaged.append({"resource": resource, "node": node_name})
        elif name == "ha_cluster_pacemaker_fail_count":
            if value > 0:
                resource  = str(lbl.get("resource", "")).strip()
                node_name = str(lbl.get("node", host)).strip()
                fail_counts.append({
                    "resource":    resource,
                    "node":        node_name,
                    "count":       int(value),
                    "is_infinity": value >= 1_000_000,
                })
        elif name == "ha_cluster_scrape_success":
            if value == 0.0:
                scrape_failures.append(str(lbl.get("collector", "unknown")).strip())
        elif name == "up":
            if value == 0.0:
                exporter_down.append(host or str(row.get("instance_s", "unknown")))
        elif name == "ha_cluster_pacemaker_node_attributes":
            attr_name  = str(lbl.get("name",  "")).strip()
            attr_value = str(lbl.get("value", "")).strip()
            node_name  = str(lbl.get("node",  host)).strip()
            if attr_name.endswith("_sync_state") and attr_value == "SFAIL":
                hana_sfail.append({"node": node_name, "attribute": attr_name})
            elif attr_name == "azure-events-az_curNodeState" and attr_value == "STOPPING":
                azure_stopping.append({"node": node_name})
            elif attr_name.startswith("master-") and attr_value == "-INFINITY":
                negative_infinity_score.append({"node": node_name, "attribute": attr_name})

    # ── Build findings ─────────────────────────────────────────────────────────
    info_quorate = dr.classify_ha_metric("ha_cluster_corosync_quorate")
    if quorate is False:
        critical_findings.append({
            "metric": "ha_cluster_corosync_quorate",
            "category": info_quorate["category"],
            "issue": "Cluster has LOST quorum — no resource decisions can be made.",
            "investigation_hints": info_quorate["investigation_hints"],
        })
    elif quorate is None:
        warnings.append({
            "metric": "ha_cluster_corosync_quorate",
            "category": info_quorate["category"],
            "issue": "Quorum state not observed — check time range or scrape health.",
            "investigation_hints": info_quorate["investigation_hints"],
        })

    if stonith_on is False:
        info_s = dr.classify_ha_metric("ha_cluster_pacemaker_stonith_enabled")
        warnings.append({
            "metric": "ha_cluster_pacemaker_stonith_enabled",
            "category": info_s["category"],
            "issue": "STONITH is DISABLED — cluster cannot safely fence failed nodes. Risk of split-brain.",
            "investigation_hints": info_s["investigation_hints"],
        })

    info_nodes = dr.classify_ha_metric("ha_cluster_pacemaker_nodes")
    if nodes_unclean:
        critical_findings.append({
            "metric": "ha_cluster_pacemaker_nodes",
            "category": info_nodes["category"],
            "issue": f"Node(s) in UNCLEAN state — STONITH fencing required: {sorted(nodes_unclean)}",
            "investigation_hints": [
                "An unclean node blocks resource recovery — STONITH must fence it first.",
                "Check STONITH device health and network connectivity between nodes.",
            ],
        })
    if nodes_offline:
        warnings.append({
            "metric": "ha_cluster_pacemaker_nodes",
            "category": info_nodes["category"],
            "issue": f"Node(s) OFFLINE in Pacemaker: {sorted(nodes_offline)}",
            "investigation_hints": info_nodes["investigation_hints"],
        })
    if nodes_standby_onfail:
        warnings.append({
            "metric": "ha_cluster_pacemaker_nodes",
            "category": info_nodes["category"],
            "issue": f"Node(s) in standby_onfail (auto-demoted after resource failure): {sorted(nodes_standby_onfail)}",
            "investigation_hints": [
                "Investigate which resource failed on this node — check ha_cluster_pacemaker_fail_count.",
                "Node will not accept resources until fail count is cleared and standby is lifted.",
            ],
        })

    info_res = dr.classify_ha_metric("ha_cluster_pacemaker_resources")
    for rf in resources_failed:
        warnings.append({
            "metric": "ha_cluster_pacemaker_resources",
            "category": info_res["category"],
            "issue": f"Resource '{rf['resource']}' is FAILED on node '{rf['node']}'.",
            "investigation_hints": info_res["investigation_hints"],
        })
    for rs in resources_stopped_no_node:
        warnings.append({
            "metric": "ha_cluster_pacemaker_resources",
            "category": info_res["category"],
            "issue": f"Resource '{rs['resource']}' is STOPPED — not running on any node.",
            "investigation_hints": info_res["investigation_hints"],
        })
    for rb in resources_blocked:
        warnings.append({
            "metric": "ha_cluster_pacemaker_resources",
            "category": info_res["category"],
            "issue": f"Resource '{rb['resource']}' is BLOCKED — cannot start on any node.",
            "investigation_hints": info_res["investigation_hints"],
        })
    for ri in resources_failure_ignored:
        informational.append({
            "metric": "ha_cluster_pacemaker_resources",
            "category": info_res["category"],
            "issue": f"Resource '{ri['resource']}' status=failure_ignored.",
            "investigation_hints": ["Review cluster policy — confirm this failure is expected/intentional."],
        })
    for ru in resources_unmanaged:
        informational.append({
            "metric": "ha_cluster_pacemaker_resources",
            "category": "Resource Status",
            "issue": f"Resource '{ru['resource']}' is UNMANAGED on '{ru['node']}' (maintenance hold).",
            "investigation_hints": ["Ensure maintenance hold is intentional and will be lifted."],
        })

    info_fail = dr.classify_ha_metric("ha_cluster_pacemaker_fail_count")
    for fc in fail_counts:
        finding = {
            "metric": "ha_cluster_pacemaker_fail_count",
            "category": info_fail["category"],
            "issue": (
                f"Resource '{fc['resource']}' has fail_count={fc['count']} on node '{fc['node']}'."
                + (" INFINITY — node permanently banned; run 'crm_resource --cleanup'." if fc["is_infinity"] else "")
            ),
            "investigation_hints": info_fail["investigation_hints"],
        }
        if fc["is_infinity"]:
            critical_findings.append(finding)
        else:
            warnings.append(finding)

    info_attr = dr.classify_ha_metric("ha_cluster_pacemaker_node_attributes")
    for hs in hana_sfail:
        warnings.append({
            "metric": "ha_cluster_pacemaker_node_attributes",
            "category": info_attr["category"],
            "issue": f"HANA replication BROKEN on node '{hs['node']}' ({hs['attribute']} = SFAIL).",
            "investigation_hints": [
                "HANA system replication not in sync — secondary cannot take over immediately.",
                "Run 'hdbnsutil -sr_state' on both nodes to check replication status.",
                "Investigate HANA nameserver logs for replication errors.",
            ],
        })
    for az in azure_stopping:
        warnings.append({
            "metric": "ha_cluster_pacemaker_node_attributes",
            "category": info_attr["category"],
            "issue": f"Azure scheduled event STOPPING on node '{az['node']}' — VM restart/redeploy imminent.",
            "investigation_hints": [
                "Cluster should pre-emptively failover resources away from this node.",
                "Check Azure portal for the scheduled event type and timeline.",
            ],
        })
    for ni in negative_infinity_score:
        critical_findings.append({
            "metric": "ha_cluster_pacemaker_node_attributes",
            "category": info_attr["category"],
            "issue": f"Node '{ni['node']}' promote score = -INFINITY ({ni['attribute']}) — permanently banned from primary promotion.",
            "investigation_hints": [
                "Run 'crm_resource --cleanup' after resolving the underlying failure.",
                "-INFINITY score means this node cannot be selected as primary until cleared.",
            ],
        })

    if scrape_failures:
        info_sc = dr.classify_ha_metric("ha_cluster_scrape_success")
        warnings.append({
            "metric": "ha_cluster_scrape_success",
            "category": info_sc["category"],
            "issue": f"Exporter scrape FAILED for collector(s): {sorted(set(scrape_failures))} — data may be stale.",
            "investigation_hints": info_sc["investigation_hints"],
        })
    if exporter_down:
        info_up = dr.classify_ha_metric("up")
        warnings.append({
            "metric": "up",
            "category": info_up["category"],
            "issue": f"HA cluster exporter DOWN on node(s): {sorted(set(exporter_down))} — cluster data absent.",
            "investigation_hints": info_up["investigation_hints"],
        })
    if maintenance_active:
        info_m = dr.classify_ha_metric("ha_cluster_pacemaker_maintenance_mode_enabled")
        informational.append({
            "metric": "ha_cluster_pacemaker_maintenance_mode_enabled",
            "category": info_m["category"],
            "issue": "Cluster/node is in MAINTENANCE MODE — Pacemaker is not managing resources.",
            "investigation_hints": info_m["investigation_hints"],
        })

    # ── Overall severity ────────────────────────────────────────────────────────
    if critical_findings:
        severity = "critical"
    elif any(
        keyword in f.get("issue", "")
        for f in warnings
        for keyword in ("FAILED", "UNCLEAN", "BROKEN", "STOPPING", "OFFLINE")
    ):
        severity = "high"
    elif warnings:
        severity = "medium"
    elif informational:
        severity = "informational"
    else:
        severity = "healthy"

    cluster_summary = {
        "quorate":               quorate,
        "stonith_enabled":       stonith_on,
        "maintenance_mode":      maintenance_active,
        "nodes_online":          sorted(nodes_online),
        "nodes_offline":         sorted(nodes_offline),
        "nodes_unclean":         sorted(nodes_unclean),
        "nodes_standby_onfail":  sorted(nodes_standby_onfail),
        "resources_active_count":  len(resources_active),
        "resources_failed_count":  len(resources_failed),
        "resources_blocked_count": len(resources_blocked),
        "resources_stopped_count": len(resources_stopped_no_node),
        "resources_unmanaged":     [r["resource"] for r in resources_unmanaged],
        "scrape_failures":         sorted(set(scrape_failures)),
        "exporter_down_nodes":     sorted(set(exporter_down)),
    }

    return {
        "status":            "success",
        "analysis_type":     "ha_cluster",
        "summary": (
            f"{total} HA metric row(s) analysed. "
            f"Quorate: {quorate}. "
            f"Nodes online: {len(nodes_online)}. "
            f"Resources active/failed/blocked: "
            f"{len(resources_active)}/{len(resources_failed)}/{len(resources_blocked)}. "
            f"Findings: {len(critical_findings)} critical, {len(warnings)} warning(s), "
            f"{len(informational)} informational."
        ),
        "severity":          severity,
        "cluster_summary":   cluster_summary,
        "critical_findings": critical_findings,
        "warnings":          warnings,
        "informational":     informational,
        "raw_row_count":     total,
        "context":           context,
    }
