"""HA Cluster layer schemas — Prometheus HA Cluster Exporter tables (Pacemaker/Corosync).

Schema source: SchemaforMCP-Details.csv — Prometheus_HaClusterExporter_CL section.
"""
from __future__ import annotations

SCHEMAS: dict[str, dict] = {

    # ──────────────────────────────────────────────────────────────────────────
    # Prometheus_HaClusterExporter_CL  (Pacemaker + Corosync HA cluster signals)
    # Schema source: SchemaforMCP-Details.csv
    # ──────────────────────────────────────────────────────────────────────────
    "Prometheus_HaClusterExporter_CL": {
        "table_name": "Prometheus_HaClusterExporter_CL",
        "domain": "ha_cluster",
        "description": (
            "High Availability cluster signals from the Prometheus HA cluster exporter. "
            "Covers Pacemaker resource state, Corosync quorum/ring health, STONITH status, "
            "node attributes, location constraints, and failover counts. Each row is one "
            "metric sample: name_s identifies the metric; labels_s (JSON) carries all detail; "
            "value_d is 1 (condition true/active) or 0 (condition false/inactive)."
        ),
        "data_source": "Prometheus HA cluster exporter → Azure Monitor",
        "time_column": "TimeGeneratedPrometheus_t",
        "sid_column": "sid_s",
        "key_columns": ["name_s", "value_d", "labels_s", "hostname_s", "sid_s"],
        "analysis_type": "ha_cluster",
        "columns": {
            "clusterName_s": {
                "type": "string",
                "description": "Name of the HA cluster this metric belongs to.",
            },
            "correlation_id_g": {
                "type": "guid",
                "description": "Batch ID that links all metrics collected in the same scrape cycle.",
            },
            "hostname_s": {
                "type": "string",
                "description": "Cluster node that reported this metric (actual OS hostname, e.g. 'chascs01l0c2').",
            },
            "instance_s": {
                "type": "string",
                "description": (
                    "AMS provider instance name configured for this HA cluster provider "
                    "(e.g. 'CHA-DB-Cluster', 'HA-CHA-chascs01l0c2'). Groups metrics by the "
                    "monitored cluster/node pair as registered in AMS. Use hostname_s for the "
                    "real node name and instance_s to scope to one provider registration; "
                    "resolve it via COMMON_VM_ArmId_Mapping_CL.PROVIDER_INSTANCE_s."
                ),
            },
            "labels_s": {
                "type": "string",
                "description": (
                    "JSON string of metric labels. ALWAYS parse with parse_json() before accessing fields. "
                    "Label keys vary by metric name. Key examples:\n"
                    "  ha_cluster_pacemaker_nodes        → 'node' (hostname), 'status', 'type' (always 'member')\n"
                    "  ha_cluster_pacemaker_resources    → 'resource', 'role', 'managed', 'status', 'node', 'group', 'clone'\n"
                    "  ha_cluster_pacemaker_fail_count   → 'node', 'resource'\n"
                    "  ha_cluster_corosync_member_votes  → 'node' (IP address), 'local' ('true'/'false'), 'node_id'\n"
                    "  ha_cluster_corosync_ring_errors   → {} (empty — aggregate total, no per-ring labels)\n"
                    "  ha_cluster_corosync_rings         → 'address', 'node_id', 'number', 'ring_id'\n"
                    "  ha_cluster_pacemaker_location_constraints → 'constraint', 'node', 'resource', 'role'\n"
                    "  ha_cluster_pacemaker_node_attributes      → 'node', 'name', 'value'\n"
                    "  ha_cluster_pacemaker_migration_threshold  → 'node', 'resource'"
                ),
            },
            "name_s": {
                "type": "string",
                "description": (
                    "Metric name. Determines the meaning of value_d and the labels_s structure. Values:\n"
                    "  ha_cluster_corosync_member_votes     — per-node expected/actual vote counts for quorum\n"
                    "  ha_cluster_corosync_quorate          — 1=cluster is quorate; 0=quorum lost (CRITICAL)\n"
                    "  ha_cluster_corosync_quorum_votes     — total expected vs actual quorum votes\n"
                    "  ha_cluster_corosync_ring_errors      — corosync ring error count (>0 = network issue)\n"
                    "  ha_cluster_corosync_rings            — one row per active ring; value_d=1 = ring active; labels: address/node_id/number/ring_id\n"
                    "  ha_cluster_pacemaker_config_last_change_total — timestamp of last cluster config change\n"
                    "  ha_cluster_pacemaker_fail_count      — per-resource fail count on a node (>0 = degraded)\n"
                    "  ha_cluster_pacemaker_location_constraints — active location constraints on resources\n"
                    "  ha_cluster_pacemaker_maintenance_mode_enabled — 1=node/cluster is in maintenance mode\n"
                    "  ha_cluster_pacemaker_migration_threshold — configured migration threshold per resource\n"
                    "  ha_cluster_pacemaker_node_attributes — per-node custom attributes (e.g. hana_<sid>_roles)\n"
                    "  ha_cluster_pacemaker_nodes           — per-node status; type=always 'member'; value_d=1 means node IS in that status\n"
                    "  ha_cluster_pacemaker_resources       — per-resource status (1=running/managed as expected)\n"
                    "  ha_cluster_pacemaker_stonith_enabled — 1=STONITH is enabled; 0=STONITH disabled (risky)\n"
                    "  ha_cluster_scrape_duration_seconds   — time taken for the last exporter scrape\n"
                    "  ha_cluster_scrape_success            — 1=exporter scrape succeeded; 0=scrape failed\n"
                    "  up                                   — 1=exporter running on this node; 0=exporter DOWN (all cluster data absent)\n"
                    "  sapmon                               — AMS heartbeat row; value_d always 1; anchor for latest correlation_id_g"
                ),
            },
            "sid_s": {
                "type": "string",
                "description": "SAP SID associated with this cluster metric. Filter by this first.",
            },
            "TimeGeneratedPrometheus_t": {
                "type": "datetime",
                "description": "Metric collection timestamp. USE THIS column for all time filters (not TimeGenerated).",
            },
            "value_d": {
                "type": "real",
                "description": (
                    "Metric value. For most HA cluster metrics: 1 = condition true/active/healthy; "
                    "0 = condition false/inactive/failed. "
                    "Exception: ha_cluster_pacemaker_fail_count and vote/count metrics carry actual counts."
                ),
            },
        },
        "kql_hints": [
            "ALWAYS filter by the sid_column shown in this schema (sid_s for this table): | where sid_s == '<sid>'",
            "Use the time_column shown in this schema (TimeGeneratedPrometheus_t for this table) — NOT TimeGenerated.",
            "labels_s is a JSON string — use parse_json(labels_s) to access label fields, e.g.: | extend lbl = parse_json(labels_s) | where lbl.node == 'myhost'",
            "Quorum check: filter name_s == 'ha_cluster_corosync_quorate' — value_d == 0 means quorum is LOST (cluster cannot take decisions — CRITICAL).",
            "STONITH check: filter name_s == 'ha_cluster_pacemaker_stonith_enabled' — value_d == 0 means STONITH is disabled, which is a cluster misconfiguration risk.",
            "Resource failure: filter name_s == 'ha_cluster_pacemaker_fail_count' and value_d > 0 to find failing resources. Use parse_json(labels_s).resource and .node.",
            "Node online status: filter name_s == 'ha_cluster_pacemaker_nodes' and parse_json(labels_s).type == 'online' — value_d == 0 means that node is offline.",
            "Resource status: filter name_s == 'ha_cluster_pacemaker_resources' — value_d == 0 on a resource means it is not running as expected.",
            "Exporter health: filter name_s == 'ha_cluster_scrape_success' — value_d == 0 means the monitoring agent failed to collect — data gap, not a cluster issue.",
            "Maintenance mode: filter name_s == 'ha_cluster_pacemaker_maintenance_mode_enabled' and value_d == 1 to detect planned maintenance windows.",
            "Corosync ring errors: filter name_s == 'ha_cluster_corosync_ring_errors' and value_d > 0 — indicates corosync network communication problems.",
            "Use correlation_id_g to join multiple metric rows from the same collection cycle for a point-in-time cluster state snapshot.",
        ],
    },
}
