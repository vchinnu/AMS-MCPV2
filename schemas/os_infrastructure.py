"""OS Infrastructure layer schemas — Prometheus OS Exporter tables (CPU, memory, disk).

Schema source: SchemaforMCP-Details.csv — Prometheus_OSExporter_CL section.
"""
from __future__ import annotations

SCHEMAS: dict[str, dict] = {

    # ──────────────────────────────────────────────────────────────────────────
    # Prometheus_OSExporter_CL  (OS metrics — CPU, memory, disk, network, swap)
    # Schema source: SchemaforMCP-Details.csv
    # ──────────────────────────────────────────────────────────────────────────
    "Prometheus_OSExporter_CL": {
        "table_name": "Prometheus_OSExporter_CL",
        "domain": "os_infrastructure",
        "description": (
            "OS-level metrics like CPU, memory, disk usage etc., collected by Prometheus node exporter for SAP hosts. "
            "Each row is one metric sample identified by name_s with its value in value_d "
            "and additional context in labels_s (JSON). Covers CPU, memory, disk I/O, "
            "network, swap, filesystem, and process metrics."
        ),
        "data_source": "Prometheus node exporter → Azure Monitor",
        "time_column": "TimeGeneratedPrometheus_t",
        "sid_column": "sid_s",
        "key_columns": ["name_s", "value_d", "labels_s", "sid_s", "instance_s"],
        "analysis_type": "os_metrics",
        "columns": {
            "sid_s": {
                "type": "string",
                "description": (
                    "SAP System ID (e.g. CHA, PRD). Always filter by this first. "
                    "NOTE: lowercase 'sid_s' on this table — NOT 'SID_s' as used by SapNetweaver_* tables. "
                    "KQL column names are case-sensitive."
                ),
            },
            "instance_s": {
                "type": "string",
                "description": (
                    "AMS provider instance name configured for this OS (Prometheus) provider, e.g. 'CHA-OS'. "
                    "This is the monitored-host identity on this table — there is NO hostname_s column here. "
                    "Use it to separate metrics when several hosts of the same SID are monitored. "
                    "Resolve it to a real VM/hostname via COMMON_VM_ArmId_Mapping_CL.PROVIDER_INSTANCE_s."
                ),
            },
            "name_s": {
                "type": "string",
                "description": (
                    "Metric name. Determines what value_d represents. Common values:\n"
                    "  node_cpu_seconds_total          — cumulative CPU seconds per mode (user/system/idle/iowait)\n"
                    "  node_memory_MemTotal_bytes       — total physical RAM\n"
                    "  node_memory_MemAvailable_bytes   — available RAM (not just free)\n"
                    "  node_memory_MemFree_bytes        — free RAM\n"
                    "  node_memory_Buffers_bytes        — kernel buffer RAM\n"
                    "  node_memory_Cached_bytes         — page cache RAM\n"
                    "  node_memory_SwapTotal_bytes      — total swap space\n"
                    "  node_memory_SwapFree_bytes       — free swap space\n"
                    "  node_memory_SwapCached_bytes     — cached swap\n"
                    "  node_disk_io_now                 — outstanding I/O operations at collection time\n"
                    "  node_disk_io_time_seconds_total  — cumulative time spent on disk I/O\n"
                    "  node_disk_read_bytes_total       — total bytes read\n"
                    "  node_disk_written_bytes_total    — total bytes written\n"
                    "  node_disk_reads_completed_total  — total read operations\n"
                    "  node_disk_writes_completed_total — total write operations\n"
                    "  node_disk_read_time_seconds_total  — cumulative read wait time\n"
                    "  node_disk_write_time_seconds_total — cumulative write wait time\n"
                    "  node_network_receive_bytes_total    — total bytes received\n"
                    "  node_network_transmit_bytes_total   — total bytes transmitted\n"
                    "  node_network_receive_packets_total  — total packets received\n"
                    "  node_network_transmit_packets_total — total packets transmitted\n"
                    "  node_filesystem_size_bytes       — total filesystem size\n"
                    "  node_filesystem_free_bytes       — free filesystem space\n"
                    "  node_filesystem_avail_bytes      — available filesystem space (unprivileged)\n"
                    "  node_procs_running               — number of processes currently running\n"
                    "  node_procs_blocked               — number of processes blocked on I/O\n"
                    "  node_forks_total                 — total number of forks\n"
                    "  node_vmstat_pgpgin               — pages paged in from disk\n"
                    "  node_vmstat_pgpgout              — pages paged out to disk\n"
                    "  node_vmstat_pswpin               — swap pages swapped in\n"
                    "  node_vmstat_pswpout              — swap pages swapped out\n"
                    "  node_boot_time_seconds           — system boot time (Unix epoch)\n"
                    "  node_time_seconds                — current system time (Unix epoch)\n"
                    "  node_uname_info                  — kernel/OS version info (value_d=1; details in labels_s)\n"
                    "  node_cooling_device_cur_state    — current cooling device state"
                ),
            },
            "labels_s": {
                "type": "string",
                "description": (
                    "JSON string of metric labels. ALWAYS parse with parse_json() before accessing fields. "
                    "Common label keys vary by metric: 'cpu', 'mode' (for node_cpu_seconds_total), "
                    "'device' (for disk/network metrics), 'mountpoint', 'fstype' (for filesystem metrics), "
                    "'interface' (for network metrics)."
                ),
            },
            "value_d": {
                "type": "real",
                "description": "Metric value. Interpretation depends on name_s (see name_s description).",
            },
            "TimeGeneratedPrometheus_t": {
                "type": "datetime",
                "description": "Metric collection timestamp. USE THIS column for all time filters (not TimeGenerated).",
            },
            "correlation_id_g": {
                "type": "guid",
                "description": "Batch correlation ID that links all metrics collected in the same scrape cycle.",
            },
            "PromInstance_s": {
                "type": "string",
                "description": (
                    "Raw Prometheus 'instance' label of the node_exporter scrape target (host:port). "
                    "Emitted only by newer AMS agent versions and frequently empty — do not rely on it; "
                    "use instance_s instead. Guard with isnotempty(PromInstance_s) if you query it."
                ),
            },
            "metadata_s": {
                "type": "string",
                "description": (
                    "JSON metadata emitted by newer AMS agent versions. Usually '{}' — not useful for RCA."
                ),
            },
            "TimeGenerated": {
                "type": "datetime",
                "description": "Log Analytics ingestion time. Do NOT use for analysis — use TimeGeneratedPrometheus_t.",
            },
        },
        "kql_hints": [
            "ALWAYS filter by sid_s (LOWERCASE on this table): | where sid_s == '<sid>'. Using 'SID_s' returns a semantic error.",
            "This table has NO hostname_s column. Use instance_s to identify the monitored host.",
            "PromInstance_s and metadata_s exist only in newer AMS agent versions and may be missing entirely in older workspaces — avoid them in portable queries.",
            "Use the time_column shown in this schema (TimeGeneratedPrometheus_t for this table) — NOT TimeGenerated.",
            "labels_s is a JSON string — use parse_json(labels_s) to access label fields, e.g.: | extend parsed = parse_json(labels_s) | where parsed.device == 'sda'",
            "For CPU analysis: filter name_s == 'node_cpu_seconds_total', group by parse_json(labels_s).mode to see idle/user/system/iowait breakdown.",
            "For memory pressure: query node_memory_MemAvailable_bytes and node_memory_MemTotal_bytes together, compute (1 - available/total) * 100 for usage %.",
            "For swap usage: query node_memory_SwapTotal_bytes and node_memory_SwapFree_bytes; high swap usage alongside memory pressure indicates memory exhaustion.",
            "For disk I/O saturation: use node_disk_io_now > 0 sustained over time, or high node_disk_io_time_seconds_total delta.",
            "For filesystem full: compare node_filesystem_avail_bytes to node_filesystem_size_bytes; alert if avail < 10% of size.",
            "Use bin(TimeGeneratedPrometheus_t, 5m) with avg(value_d) to show trends.",
            "node_uname_info has value_d=1 always — use labels_s for kernel/OS version details.",
        ],
    },
}
