"""HA Cluster domain knowledge — Pacemaker / Corosync metric classification.

Contains:
  HA_METRIC_RULES       : metric name → category / severity / meaning / investigation_hints
  classify_ha_metric()  : look up a metric by name_s

Each entry covers one metric from Prometheus_HaClusterExporter_CL.
value_d = 1 means the condition is active/true; 0 means inactive/false
(except for count-style metrics like fail_count, ring_errors, vote counts).
"""
from __future__ import annotations

# ── HA Cluster Metric Rules ───────────────────────────────────────────────────
# key   : exact name_s value from Prometheus_HaClusterExporter_CL
# value : classification with severity, meaning, and investigation hints.
#
# severity levels (used by _analyze_ha_cluster to set overall severity):
#   "critical"  — cluster cannot operate correctly; immediate action required
#   "high"      — degraded cluster health; failover risk
#   "medium"    — warning; investigate before it escalates
#   "info"      — informational; no immediate action

HA_METRIC_RULES: dict[str, dict] = {

    # ── Corosync — Quorum ─────────────────────────────────────────────────────

    "ha_cluster_corosync_quorate": {
        "category": "Quorum",
        "severity_when_zero": "critical",
        "meaning": (
            "Indicates whether the cluster currently has quorum (majority of nodes agree on cluster state). "
            "value_d == 1: cluster is quorate — normal. "
            "value_d == 0: quorum is LOST — the cluster cannot make resource decisions, failovers are blocked, "
            "and no new resources can be started. This is the most critical HA signal."
        ),
        "investigation_hints": [
            "Check which cluster nodes are online — quorum loss usually means one or more nodes went offline.",
            "Check corosync ring errors (ha_cluster_corosync_ring_errors) — network split between nodes causes quorum loss.",
            "Check OS-level network metrics on all cluster nodes at the time of quorum loss.",
            "Check STONITH status — without quorum, STONITH may be unable to fence failed nodes, risking a split-brain.",
            "Check ha_cluster_pacemaker_nodes for which specific nodes are shown as offline.",
        ],
    },

    "ha_cluster_corosync_member_votes": {
        "category": "Quorum",
        "severity_when_zero": "high",
        "meaning": (
            "Per-node vote contribution to the quorum calculation. "
            "labels_s carries 'node' (IP address of the node, not hostname), "
            "'local' ('true' if this row was reported by this very node, 'false' for remote peers), "
            "and 'node_id' (corosync node ID). "
            "value_d is the number of votes the named node is currently contributing. "
            "Expected: each node contributes its configured vote weight. "
            "Any node with value_d == 0 while the cluster is running is not participating in quorum."
        ),
        "investigation_hints": [
            "A node with member_votes == 0 is not participating in quorum — check if that node is online and corosync is running on it.",
            "Note: parse_json(labels_s).node gives the IP address, not the hostname — cross-reference with known cluster node IPs.",
            "Compare actual vs expected vote counts using ha_cluster_corosync_quorum_votes.",
            "Cross-reference with ha_cluster_pacemaker_nodes to confirm whether the node is also marked offline by Pacemaker.",
        ],
    },

    "ha_cluster_corosync_quorum_votes": {
        "category": "Quorum",
        "severity_when_zero": "high",
        "meaning": (
            "Cluster-wide quorum vote metrics. labels_s carries 'type' with four possible values: "
            "'expected_votes' (votes required for quorum), "
            "'total_votes' (votes the cluster currently has — should equal expected_votes when all nodes up), "
            "'highest_expected' (highest expected_votes value seen — used in 2-node cluster quorum calculation), "
            "'quorum' (current quorum threshold, typically expected_votes/2 + 1). "
            "When total_votes < expected_votes the cluster is at risk of losing quorum."
        ),
        "investigation_hints": [
            "Compare total_votes vs expected_votes — a gap indicates a node has left the cluster.",
            "For a healthy 2-node cluster: expected_votes=2, total_votes=2, quorum=1, highest_expected=2.",
            "If total_votes drops to 1 on a 2-node cluster, the remaining node must have quorate=1 via last-man-standing — check ha_cluster_corosync_quorate.",
            "Check ha_cluster_corosync_member_votes to identify which node's votes are missing.",
        ],
    },

    "ha_cluster_corosync_ring_errors": {
        "category": "Network",
        "severity_when_nonzero": "high",
        "meaning": (
            "Cumulative count of corosync ring communication errors across all rings on this node. "
            "labels_s is empty ({}) — this is an aggregate total, not per-ring breakdown. "
            "value_d > 0 means corosync has detected ring transmission errors — "
            "indicates network instability between cluster nodes that can lead to quorum loss."
        ),
        "investigation_hints": [
            "This metric gives a total error count only — use ha_cluster_corosync_rings to identify which ring interface is active, then check OS network error metrics on that interface.",
            "Check OS network metrics (node_network_receive_errs_total, node_network_transmit_errs_total) on both cluster nodes at the time errors appeared.",
            "Check for physical network issues (cable, switch, NIC) on the corosync ring interface.",
            "If only one corosync ring is configured and it has errors, quorum loss is imminent — check ha_cluster_corosync_quorate.",
            "Persistent ring errors should be resolved before any planned maintenance or failover.",
        ],
    },

    "ha_cluster_corosync_rings": {
        "category": "Network",
        "severity_when_zero": "medium",
        "meaning": (
            "One row per active corosync communication ring on the reporting node. value_d == 1 means the ring is active. "
            "labels_s carries: 'address' (local IP address used on this ring), "
            "'node_id' (corosync node ID of the reporting node), "
            "'number' (ring number starting at 0), and "
            "'ring_id' (current ring sequence identifier in format 'message_seq/token_seq'). "
            "The count of rows with value_d==1 gives the total active rings. "
            "NOTE: this is NOT a count field — do not sum value_d across rows."
        ),
        "investigation_hints": [
            "Count rows with value_d==1 per instance_s to determine how many corosync rings are active on each node.",
            "If fewer rings are active than configured, redundancy is reduced — one ring loss = no redundancy.",
            "parse_json(labels_s).address gives the local IP on each ring — map this to the NIC using OS network config.",
            "Recommended SAP HA best practice: at least 2 corosync rings on separate network interfaces.",
            "Cross-reference with OS network error metrics (node_network_receive_errs_total) on the interface whose IP matches parse_json(labels_s).address.",
            "Check ha_cluster_corosync_ring_errors — if ring errors are non-zero, correlate with which ring interface has OS-level errors.",
        ],
    },

    # ── Pacemaker — Nodes ─────────────────────────────────────────────────────

    "ha_cluster_pacemaker_nodes": {
        "category": "Node Status",
        "severity_when_zero": "high",
        "meaning": (
            "Per-node status as seen by Pacemaker. One row per (node, status) combination. "
            "labels_s carries 'node' (node hostname), 'status' (the state being tested), and 'type' (always 'member'). "
            "value_d == 1: the node IS in that status. value_d == 0: the node is NOT in that status. "
            "Status values and their meaning:\n"
            "  status=online        — Node is active and running resources. Expected normal state. ALERT when value_d=0.\n"
            "  status=dc            — This node is the Designated Coordinator (authoritative cluster state source). Exactly one node should have value_d=1.\n"
            "  status=expected_up   — Pacemaker expects this node to be up. value_d=1 for all healthy cluster members.\n"
            "  status=offline       — Node is unreachable. CRITICAL when value_d=1.\n"
            "  status=unclean       — Node in unclean state, STONITH fencing required. CRITICAL when value_d=1.\n"
            "  status=pending       — Node is joining the cluster. Transient.\n"
            "  status=shutdown      — Node is shutting down gracefully.\n"
            "  status=standby       — Node in standby mode (not running resources). Intentional/informational.\n"
            "  status=standby_onfail — Node went to standby after a resource failure. ALERT when value_d=1.\n"
            "  status=maintenance   — Node in maintenance mode (Pacemaker does not manage resources on it)."
        ),
        "investigation_hints": [
            "Filter status='online' and value_d=0 to find nodes that are offline to Pacemaker.",
            "Filter status='unclean' and value_d=1 to find nodes pending STONITH fencing — this blocks resource recovery.",
            "Filter status='dc' and value_d=1 to identify the current Designated Coordinator node.",
            "Filter status='standby_onfail' and value_d=1 — node self-demoted after a resource failure; investigate the failed resource.",
            "WORKBOOK DC DETECTION PATTERN: filter value_d==1, status=='dc', tostring(parse_json(labels_s).node)==hostname_s — this identifies the DC node's correlation_id_g for authoritative cluster state.",
            "A node with status='expected_up' value_d=1 but status='online' value_d=0 means Pacemaker expected it but it is not online — check network and pacemaker service on that node.",
        ],
    },

    "ha_cluster_pacemaker_node_attributes": {
        "category": "Node Attributes",
        "severity_when_zero": "medium",
        "meaning": (
            "Custom per-node attributes set by cluster resource agents. "
            "labels_s carries 'node' (node hostname), 'name' (attribute name), and 'value' (attribute value as string). "
            "value_d is always 1 (presence indicator). "
            "Attribute naming patterns: "
            "  hana_<sid_lowercase>_<attribute>   for SAP HANA SR resource agent attributes\n"
            "  lpa_<sid_lowercase>_lpt            for HANA Last Primary Timestamp\n"
            "  master-<resource_name>             for HANA promote/demote score\n"
            "  runs_ers_<SID>                     for NW cluster ERS tracking\n"
            "  azure-events-az_*                  for Azure scheduled events integration\n"
            "\nKey HANA SR attributes (DB cluster, SID in lowercase):\n"
            "  hana_<sid>_sync_state  — 'PRIM' (this is the primary), 'SOK' (secondary in sync), 'SFAIL' (secondary NOT in sync — replication broken). ALERT on SFAIL.\n"
            "  hana_<sid>_clone_state — 'PROMOTED' (running as primary), 'DEMOTED' (running as secondary), 'UNDEFINED'.\n"
            "  hana_<sid>_roles       — Role string: '4:P:master1:master:worker:master' (P=primary) or '4:S:...' (S=secondary).\n"
            "  hana_<sid>_op_mode     — HANA SR operation mode: typically 'logreplay'.\n"
            "  hana_<sid>_site        — HANA SR site name (e.g. 'SITEA', 'SITEB').\n"
            "  hana_<sid>_srmode      — SR replication mode: 'sync', 'async', 'syncmem'.\n"
            "  hana_<sid>_remoteHost  — Virtual hostname of the replication partner node.\n"
            "  hana_<sid>_vhost       — Local virtual hostname used by HANA.\n"
            "  hana_<sid>_version     — HANA version string (e.g. '2.00.077.00').\n"
            "  lpa_<sid>_lpt          — Last Primary Timestamp: unix epoch on primary node; small value (e.g. 10) on secondary.\n"
            "  master-rsc_SAPHana_<SID>_<instance> — Promote score: high value (e.g. 150) = preferred primary; '-INFINITY' = permanently excluded from promotion.\n"
            "\nKey NW cluster attributes:\n"
            "  runs_ers_<SID>  — Whether ERS is running on this node ('0' or '1').\n"
            "\nAzure scheduled events attributes:\n"
            "  azure-events-az_curNodeState    — 'AVAILABLE' (no event) or 'STOPPING' (VM restart/redeploy/reimage scheduled).\n"
            "  azure-events-az_pendingEventIDs — GUID of pending Azure events; empty when no event.\n"
            "\nGeneral:\n"
            "  azName — Azure VM resource name for this cluster node."
        ),
        "investigation_hints": [
            "KQL pattern: | where parse_json(labels_s).name == 'hana_cha_sync_state' | extend attr_value = tostring(parse_json(labels_s).value)",
            "For HANA SR: hana_<sid>_sync_state == 'SFAIL' means HANA replication on the secondary node is broken — ALERT even if the cluster overall is green.",
            "For HANA SR: check clone_state — both nodes should have distinct states (PROMOTED + DEMOTED). Two DEMOTED nodes = no HANA primary running anywhere.",
            "For HANA SR: master promote score '-INFINITY' on a node means it is permanently banned from being promoted to primary — run 'crm_resource --cleanup' after resolving the root cause.",
            "For HANA SR: lpa_<sid>_lpt has a very small value (e.g. 10) on the secondary and a large unix timestamp on the primary — this helps identify which node is currently primary.",
            "For Azure events: azure-events-az_curNodeState == 'STOPPING' means Azure is about to disrupt this VM — the cluster should pre-emptively failover resources away from it.",
            "For NW cluster: runs_ers_<SID>==0 on both nodes means ERS is not running anywhere — SAP enqueue replication is not protected.",
            "Attribute timeline changes often correlate with failover events — look for sync_state or clone_state changes in the minutes before a resource failure.",
        ],
    },

    # ── Pacemaker — Resources ─────────────────────────────────────────────────

    "ha_cluster_pacemaker_resources": {
        "category": "Resource Status",
        "severity_when_zero": "high",
        "meaning": (
            "Per-resource Pacemaker status. One row per (resource, node, status) combination. "
            "labels_s carries: 'resource' (resource name), 'agent' (OCF agent identifier, e.g. 'ocf::heartbeat:SAPInstance'), "
            "'node' (node hostname — empty string when resource is stopped with no node assignment), "
            "'role' (lowercase: 'started', 'stopped', 'master', 'slave'), "
            "'status' (lowercase: 'active', 'blocked', 'failed', 'failure_ignored', 'orphaned'), "
            "'managed' ('true' = Pacemaker controls it; 'false' = unmanaged/manual hold), "
            "'group' (resource group name, empty for standalone resources), "
            "'clone' (clone set name, empty for non-clone resources). "
            "value_d == 1: this (resource, node, status, role) combination IS the current state. "
            "value_d == 0: this combination is NOT the current state (only one combination per resource/node will be 1). "
            "WORKBOOK COLOUR CODING: "
            "RED = status='failed' or 'failure_ignored'; "
            "RED (resource detail view) = role='stopped' with empty node (resource is not running anywhere); "
            "YELLOW = status='blocked' or 'orphaned'; "
            "GREEN = status='active' and managed='true'; "
            "GREY = managed='false' (unmanaged)."
        ),
        "investigation_hints": [
            "Filter value_d==1 and status=='failed' to find currently failed resources — confirm failure count with ha_cluster_pacemaker_fail_count.",
            "Filter value_d==1 and role=='stopped' with empty node — resource is completely stopped, not running on any node.",
            "Filter value_d==1 and status=='blocked' — resource cannot start on any available node; check ordering constraints and dependent resource status.",
            "Filter value_d==1 and managed=='false' — resource is unmanaged; Pacemaker will not auto-recover it (intentional maintenance or error).",
            "Filter value_d==1 and status=='failure_ignored' — resource has failed but cluster policy marks it ignored; still warrants review.",
            "parse_json(labels_s).agent identifies the resource type: 'ocf::heartbeat:SAPInstance' (SAP NW instance), 'ocf::suse:SAPHana' (HANA SR), 'stonith:fence_azure_arm' (STONITH fencing), 'ocf::heartbeat:Filesystem' (filesystem), 'ocf::heartbeat:IPaddr2' (virtual IP), 'ocf::heartbeat:azure-lb' (Azure load balancer probe), 'ocf::heartbeat:azure-events-az' (Azure scheduled events).",
            "If an IPaddr2 (VIP) or Filesystem resource is stopped/failed, the associated SAP instance group is inaccessible.",
            "For HANA SR clusters: role=='master' = primary HANA, role=='slave' = secondary HANA. Must have exactly one of each across both nodes.",
            "Correlate stopped/failed resources with ha_cluster_pacemaker_fail_count and ha_cluster_pacemaker_node_attributes (HANA SR state).",
        ],
    },

    "ha_cluster_pacemaker_fail_count": {
        "category": "Resource Failures",
        "severity_when_nonzero": "high",
        "meaning": (
            "Per-resource cumulative failure count on a specific node as tracked by Pacemaker. "
            "labels_s carries 'resource' and 'node'. "
            "value_d is the number of times the resource has failed on that node since the last cleanup. "
            "Interpretation:\n"
            "  value_d == 0       \u2192 No failures. Normal state.\n"
            "  value_d > 0        \u2192 Resource has failed at least once. Investigate.\n"
            "  value_d rising     \u2192 Recurring failure pattern. Admin intervention likely needed.\n"
            "  value_d very large \u2192 Pacemaker has permanently excluded this node for this resource. "
            "                       Manual cleanup ('crm_resource --cleanup') required.\n"
            "When fail_count reaches the migration_threshold (see ha_cluster_pacemaker_migration_threshold), "
            "Pacemaker bans the resource from that node."
        ),
        "investigation_hints": [
            "A non-zero fail count means the resource has previously failed — check resource agent logs on the affected node.",
            "Compare fail_count value_d against ha_cluster_pacemaker_migration_threshold for the same (resource, node) — if fail_count reaches migration_threshold, the next failure triggers a permanent ban.",
            "A very large value_d (e.g. 1000000 or higher, representing INFINITY in Pacemaker) means the node is permanently banned — run 'crm_resource --cleanup' or 'crm_failcount -D' to reset.",
            "Fail counts persist until explicitly cleared — an elevated count may prevent resource re-placement on this node after a failover.",
            "Repeated failures of the same resource indicate a recurring issue — investigate the resource agent, the underlying service (HANA, SAP), or OS-level problems.",
        ],
    },

    "ha_cluster_pacemaker_location_constraints": {
        "category": "Constraints",
        "severity_when_zero": "medium",
        "meaning": (
            "Active location constraints controlling where resources can run. "
            "labels_s carries 'constraint' (constraint name), 'node', 'resource', and 'role' "
            "(node/resource/role may be empty for non-cli permanent constraints). "
            "Constraints prefixed with 'cli-ban-' indicate a resource was manually banned from a node. "
            "Constraints prefixed with 'cli-prefer-' indicate a resource was manually moved to a preferred node. "
            "A 'loc_azure_health' constraint is a permanent cluster-level constraint for Azure events integration."
        ),
        "investigation_hints": [
            "Filter parse_json(labels_s).constraint startswith 'cli-ban' — a resource was manually banned; this can prevent automatic failback.",
            "Filter parse_json(labels_s).constraint startswith 'cli-prefer' — a manual resource move was performed; may block return to original node.",
            "Temporary ban constraints are added automatically when a resource exceeds its migration_threshold — clear the fail count ('crm resource cleanup') to remove the ban.",
            "Unexpected location constraints indicate a previous failover event — investigate why the original node was abandoned.",
            "'loc_azure_health' with empty node/resource/role is the standard Azure events location constraint — not an error.",
        ],
    },

    "ha_cluster_pacemaker_migration_threshold": {
        "category": "Resource Failures",
        "severity_when_zero": "info",
        "meaning": (
            "Configured migration threshold for a resource on a specific node — "
            "the number of failures after which Pacemaker bans the resource from that node and migrates it elsewhere. "
            "labels_s carries 'node' and 'resource'. "
            "Typical values: 3 (SAP NetWeaver clusters, aggressive failover), "
            "5000 (SAP HANA SR clusters — effectively unlimited, Pacemaker will not auto-ban on repeated failures)."
        ),
        "investigation_hints": [
            "Cross-reference with ha_cluster_pacemaker_fail_count for the same (resource, node) — when fail_count reaches this threshold, the next failure triggers a permanent ban.",
            "A migration_threshold of 1 means a single failure immediately bans the resource from the node — very aggressive.",
            "A value of 5000 (as seen on HANA SR resources) means the cluster keeps retrying on the same node indefinitely — manual intervention required if the resource keeps failing.",
            "KQL JOIN pattern: join ha_cluster_pacemaker_fail_count with ha_cluster_pacemaker_migration_threshold on TimeGenerated and resource/node labels to compute headroom.",
        ],
    },

    # ── Pacemaker — STONITH ───────────────────────────────────────────────────

    "ha_cluster_pacemaker_stonith_enabled": {
        "category": "STONITH",
        "severity_when_zero": "high",
        "meaning": (
            "Indicates whether STONITH (Shoot The Other Node In The Head) fencing is enabled. "
            "value_d == 1: STONITH enabled — normal and required for SAP-certified HA. "
            "value_d == 0: STONITH disabled — CRITICAL misconfiguration for production SAP HA clusters. "
            "Without STONITH, Pacemaker cannot safely fence failed nodes and will refuse to start resources "
            "when a node failure is detected, to prevent data corruption (split-brain)."
        ),
        "investigation_hints": [
            "STONITH == 0 is a misconfiguration for any production SAP HA cluster — do not leave in this state.",
            "STONITH may be temporarily disabled for maintenance — confirm this is intentional if value_d == 0.",
            "Check ha_cluster_pacemaker_maintenance_mode_enabled — STONITH is sometimes disabled during maintenance windows.",
            "If STONITH was disabled to work around a fencing failure, identify and fix the fencing device before re-enabling.",
        ],
    },

    # ── Pacemaker — Maintenance ───────────────────────────────────────────────

    "ha_cluster_pacemaker_maintenance_mode_enabled": {
        "category": "Maintenance",
        "severity_when_nonzero": "medium",
        "meaning": (
            "Indicates whether the cluster or a specific node is in Pacemaker maintenance mode. "
            "value_d == 1: maintenance mode is active — resources are not managed by Pacemaker. "
            "In this state Pacemaker will not start, stop, or move resources automatically. "
            "Failovers do not happen. Monitoring alerts may be suppressed."
        ),
        "investigation_hints": [
            "Confirm maintenance mode is intentional — if it was not explicitly set, investigate why.",
            "Ensure maintenance mode is lifted before the cluster is expected to protect production workloads.",
            "Resources that stop while in maintenance mode will not be restarted automatically — verify all resources are running after exiting maintenance.",
        ],
    },

    "ha_cluster_pacemaker_config_last_change_total": {
        "category": "Configuration",
        "severity_when_zero": "info",
        "meaning": (
            "Unix epoch timestamp of the last Pacemaker cluster configuration change (CIB update). "
            "Useful for correlating cluster problems with configuration changes."
        ),
        "investigation_hints": [
            "Convert value_d to a human-readable timestamp to identify when the last config change occurred.",
            "If a cluster problem started recently, check whether a config change occurred just before — a misconfiguration may be the cause.",
        ],
    },

    # ── Exporter Health ───────────────────────────────────────────────────────

    "ha_cluster_scrape_success": {
        "category": "Exporter Health",
        "severity_when_zero": "medium",
        "meaning": (
            "Indicates whether the last Prometheus HA cluster exporter scrape succeeded per collector subsystem. "
            "labels_s carries 'collector' with values: 'corosync', 'pacemaker', 'drbd', 'sbd'. "
            "value_d == 1: this collector's scrape succeeded — data is fresh. "
            "value_d == 0: this collector's scrape FAILED — corresponding metrics from this subsystem are stale or absent. "
            "This is a monitoring gap indicator, not necessarily a cluster problem itself."
        ),
        "investigation_hints": [
            "A scrape failure for 'corosync' or 'pacemaker' collector means cluster state data is stale — do not draw RCA conclusions from those rows.",
            "Check whether the ha_cluster_exporter process is running on the reporting hostname_s.",
            "Check OS-level resource availability on the cluster node — exporter crashes can be caused by memory pressure.",
            "Use ha_cluster_scrape_success grouped by collector to identify which subsystem is failing.",
        ],
    },

    "ha_cluster_scrape_duration_seconds": {
        "category": "Exporter Health",
        "severity_when_zero": "info",
        "meaning": (
            "Duration in seconds of the last Prometheus HA cluster exporter scrape per collector subsystem. "
            "labels_s carries 'collector' with values: 'corosync', 'pacemaker', 'drbd', 'sbd'. "
            "Typical values: corosync ~0.015s, pacemaker ~0.05s, drbd/sbd <0.005s. "
            "Unusually high values for the 'pacemaker' collector may indicate the Pacemaker CIB query is slow "
            "(common when the cluster has many resources or is under stress)."
        ),
        "investigation_hints": [
            "If 'pacemaker' collector scrape duration is consistently > 5 seconds, the Pacemaker CIB is slow — correlate with cluster activity.",
            "Slow scrape duration can cause metric timestamps to lag behind actual state — correlate with ha_cluster_scrape_success.",
        ],
    },

    # ── Exporter Up Status ─────────────────────────────────────────────────────────────

    "up": {
        "category": "Exporter Health",
        "severity_when_zero": "high",
        "meaning": (
            "Exporter liveness indicator for this cluster node. "
            "value_d == 1: the ha_cluster_exporter is running on this node and submitting data. "
            "value_d == 0: the exporter is DOWN — all other HA cluster metrics from this node are absent or stale. "
            "labels_s is empty ({})."
        ),
        "investigation_hints": [
            "If value_d == 0 or no recent 'up' rows exist for an instance_s, the exporter is not running on that node — cluster state data is missing.",
            "Used in workbook to find the latest valid correlation_id_g per node: filter name_s=='sapmon' (or 'up') and summarize arg_max(TimeGenerated, correlation_id_g) by sid_s, clusterName_s, hostname_s.",
            "An exporter outage on both cluster nodes simultaneously means no HA telemetry is available — check AMS collector health.",
        ],
    },

    # ── SAP Monitor Heartbeat (metadata row) ──────────────────────────────────────────

    "sapmon": {
        "category": "Metadata",
        "severity_when_zero": "info",
        "meaning": (
            "SAP Monitor (AMS) heartbeat/metadata row. value_d is always 1. "
            "labels_s carries PROVIDER_INSTANCE (e.g. 'CHA-HA-NW2'), SAPMON_VERSION, sapsid, Time_Generated, and METADATA. "
            "Confirms the AMS collector is active and submitting data from this cluster provider instance. "
            "The workbook uses this row to identify the latest active correlation_id_g per cluster node."
        ),
        "investigation_hints": [
            "Absence of recent 'sapmon' rows for an instance_s indicates the AMS collector may be offline for that cluster node.",
            "WORKBOOK PATTERN: 'sapmon' is used as the heartbeat anchor — summarize arg_max(TimeGenerated, correlation_id_g) by sid_s, clusterName_s, hostname_s where name_s=='sapmon' to get the most recent scrape.",
            "parse_json(labels_s).SAPMON_VERSION identifies the AMS collector version in use.",
            "parse_json(labels_s).PROVIDER_INSTANCE identifies which HA cluster provider this data comes from (e.g. CHA-HA-NW1, CHA-HA-DB2).",
        ],
    },
}


# ── Convenience function ────────────────────────────────────────────────────

def classify_ha_metric(metric_name: str) -> dict:
    """Return category, severity, meaning, and investigation_hints for an HA cluster metric name."""
    entry = HA_METRIC_RULES.get(metric_name)
    if entry:
        return entry
    return {
        "category": "Unknown",
        "severity_when_zero": "info",
        "meaning": f"HA cluster metric '{metric_name}' is not in the local knowledge base.",
        "investigation_hints": [
            f"Check Prometheus HA cluster exporter documentation for metric '{metric_name}'.",
            "Inspect labels_s with parse_json(labels_s) to understand the context of this metric.",
        ],
    }
