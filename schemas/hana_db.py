"""HANA DB layer schemas — SAP HANA database monitoring tables.

HOW TO ADD A TABLE
──────────────────
1. Add a new entry to SCHEMAS below.
2. Set "domain": "hana_db" and "analysis_type": "hana_db".
3. Add a handler for "hana_db" in MCP/tools/analyze_results.py.
4. Restart the MCP server.
"""
from __future__ import annotations

SCHEMAS: dict[str, dict] = {

    # -------------------------------------------------------------------------
    # Table 1 — SapHana_Alerts_CL
    # HANA internal alert log
    # -------------------------------------------------------------------------
    "SapHana_Alerts_CL": {
        "table_name": "SapHana_Alerts_CL",
        "domain": "hana_db",
        "description": (
            "SAP HANA internal alert log. Each row represents one HANA alert raised by "
            "the HANA statistics service (e.g. disk usage, memory, replication lag). "
            "Equivalent to the HANA Alerts view in HANA Studio / cockpit."
        ),
        "data_source": "SAP Monitor HANA provider — HANA alerts API",
        "time_column": "TimeGenerated",
        "sid_column": "sapsid_s",
        "key_columns": ["ALERT_ID_s", "RATING_s", "ALERT_DETAILS_s", "RECOMMENDATION_s"],
        "analysis_type": "hana_db",
        "columns": {
            "TimeGenerated": {"type": "datetime", "description": "UTC ingest timestamp. Primary time filter column."},
            "SERVER_UTC_t": {"type": "datetime", "description": "UTC timestamp from the HANA server at collection time."},
            "TIMESERIES_UTC_t": {"type": "datetime", "description": "UTC timestamp of the HANA monitoring timeseries data point."},
            "ALERT_ID_s": {"type": "string", "description": "HANA internal alert number (e.g. '2' = disk usage). Maps to HANA M_ALERTS system view."},
            "ALERT_DETAILS_s": {"type": "string", "description": "Human-readable alert description including affected resource and measured value. Key field for RCA."},
            "ALERT_TIME_s": {"type": "string", "description": "Alert timestamp as string in SAP local time (DD-MM-YYYY HH:mm). Do not use for KQL time filters."},
            "RATING_s": {"type": "string", "description": "Alert severity: HIGH (critical), MEDIUM (warning), LOW (informational)."},
            "RECOMMENDATION_s": {"type": "string", "description": "HANA-provided remediation recommendation for this alert. May be empty."},
            "PROVIDER_INSTANCE_s": {"type": "string", "description": "SAP Monitor provider instance name (e.g. 'CHA-HANA')."},
            "sapsid_s": {"type": "string", "description": "SAP System ID (SID) of the HANA system (e.g. 'CHA'). Always use for filtering."},
            "SAPMON_VERSION_s": {"type": "string", "description": "Version of the SAP Monitor agent that collected this record."},
        },
        "kql_hints": [
            "ALWAYS filter by sapsid_s: | where sapsid_s == '<sid>'",
            "Alerts are re-collected each cycle — deduplicate before counting: | summarize arg_max(TimeGenerated, *) by ALERT_ID_s, ALERT_DETAILS_s",
            "Start RCA with HIGH ratings: | where RATING_s == 'HIGH' | summarize count() by ALERT_ID_s, ALERT_DETAILS_s",
            "ALERT_TIME_s is a STRING (DD-MM-YYYY HH:mm) — never use it in a KQL time filter; filter on TimeGenerated.",
            "RECOMMENDATION_s often contains the remediation — always surface it alongside the alert in RCA output.",
        ],
    },

    # -------------------------------------------------------------------------
    # Table 2 — SapHana_BackupCatalog_CL
    # HANA backup catalog — history of all backup operations
    # -------------------------------------------------------------------------
    "SapHana_BackupCatalog_CL": {
        "table_name": "SapHana_BackupCatalog_CL",
        "domain": "hana_db",
        "description": (
            "SAP HANA backup catalog. Each row is one backup entry "
            "(data backup, log backup, or log snapshot). Equivalent to HANA BACKUP_CATALOG view. "
            "Use to identify failed backups, backup gaps, or RPO violations."
        ),
        "data_source": "SAP Monitor HANA provider — backup catalog API",
        "time_column": "TimeGenerated",
        "sid_column": "sapsid_s",
        "key_columns": ["STATE_NAME_s", "ENTRY_TYPE_NAME_s", "DATABASE_NAME_s", "UTC_START_TIME_t", "UTC_END_TIME_t", "Message"],
        "analysis_type": "hana_db",
        "columns": {
            "TimeGenerated": {"type": "datetime", "description": "UTC ingest timestamp."},
            "SERVER_UTC_t": {"type": "datetime", "description": "UTC timestamp from the HANA server at collection time."},
            "TIMESERIES_UTC_t": {"type": "datetime", "description": "UTC timestamp of the timeseries data point for this backup entry."},
            "UTC_START_TIME_t": {"type": "datetime", "description": "UTC start time of the backup operation."},
            "UTC_END_TIME_t": {"type": "datetime", "description": "UTC end time of the backup operation."},
            "BACKUP_ID_d": {"type": "real", "description": "Unique numeric backup ID in the HANA backup catalog."},
            "DATABASE_NAME_s": {"type": "string", "description": "HANA tenant database name (e.g. 'SYSTEMDB' or tenant SID). HANA MDC can have multiple tenant DBs."},
            "ENTRY_TYPE_NAME_s": {"type": "string", "description": "Backup type: 'complete data backup', 'log backup', 'log snapshot', 'differential data backup'."},
            "STATE_NAME_s": {"type": "string", "description": "Backup result: 'successful', 'failed', 'running', 'canceled'. Filter on 'failed' for backup RCA."},
            "Message": {"type": "string", "description": "Status message — '<ok>' for success or error description on failure."},
            "DESTINATION_TYPE_NAME_s": {"type": "string", "description": "Backup destination: 'backint' (Azure Backup/third-party), 'file', 'pipe'."},
            "BACKUP_SIZE_BYTES_d": {"type": "real", "description": "Total backup size in bytes."},
            "BACKUP_RATE_KBYTES_PER_SECOND_d": {"type": "real", "description": "Backup throughput in KB/s."},
            "NUMBER_OF_FILES_d": {"type": "real", "description": "Number of backup files or streams for this entry."},
            "TIME_ELAPSED_SECONDS_d": {"type": "real", "description": "Duration of the backup operation in seconds."},
            "SYSTEM_ID_s": {"type": "string", "description": "SAP System ID from the HANA backup catalog record."},
            "sapsid_s": {"type": "string", "description": "SAP System ID tag added by SAP Monitor. Use for filtering."},
            "PROVIDER_INSTANCE_s": {"type": "string", "description": "SAP Monitor provider instance name (e.g. 'CHA-HANA')."},
        },
        "kql_hints": [
            "ALWAYS filter by sapsid_s: | where sapsid_s == '<sid>'",
            "The catalog is re-sent each cycle — deduplicate on BACKUP_ID_d: | summarize arg_max(TimeGenerated, *) by BACKUP_ID_d",
            "Failed backups: | where STATE_NAME_s == 'failed' | project UTC_START_TIME_t, DATABASE_NAME_s, ENTRY_TYPE_NAME_s, Message",
            "Filter on UTC_START_TIME_t (real backup time) for backup-window analysis — TimeGenerated is only the collection time.",
            "Log backup gap (RPO risk): | where ENTRY_TYPE_NAME_s == 'log backup' | summarize max(UTC_END_TIME_t) by DATABASE_NAME_s — a stale value means log backups stopped and the log volume will fill.",
            "Backup slowdown: | where ENTRY_TYPE_NAME_s == 'complete data backup' | summarize avg(TIME_ELAPSED_SECONDS_d), avg(BACKUP_RATE_KBYTES_PER_SECOND_d) by bin(UTC_START_TIME_t, 1d)",
            "Message == '<ok>' means success — treat any other text as the failure reason.",
        ],
    },

    # -------------------------------------------------------------------------
    # Table 3 — SapHana_Disks_CL
    # HANA disk volume usage per mount point
    # -------------------------------------------------------------------------
    "SapHana_Disks_CL": {
        "table_name": "SapHana_Disks_CL",
        "domain": "hana_db",
        "description": (
            "SAP HANA disk volume usage. Each row is one HANA volume mount point "
            "(data, log, or backup) on a specific host with total and used size. "
            "Use to identify disk full conditions contributing to HANA failures or alerts."
        ),
        "data_source": "SAP Monitor HANA provider — disk volumes API",
        "time_column": "TimeGenerated",
        "sid_column": "sapsid_s",
        "key_columns": ["HOST_s", "PATH_s", "USAGE_TYPE_s", "TOTAL_SIZE_d", "USED_SIZE_d"],
        "analysis_type": "hana_db",
        "columns": {
            "TimeGenerated": {"type": "datetime", "description": "UTC ingest timestamp."},
            "SERVER_UTC_t": {"type": "datetime", "description": "UTC timestamp from the HANA server at collection time."},
            "HOST_s": {"type": "string", "description": "Hostname of the HANA node (e.g. 'vchadcha01l10c')."},
            "PATH_s": {"type": "string", "description": "Filesystem mount path (e.g. '/hana/data/CHA/', '/hana/log/CHA/')."},
            "SUBPATH_s": {"type": "string", "description": "Sub-directory or volume mount name within the path (e.g. 'mnt00001')."},
            "USAGE_TYPE_s": {"type": "string", "description": "Volume type: 'DATA' (column store), 'LOG' (redo log), 'BACKUP', 'TRACE'."},
            "TOTAL_SIZE_d": {"type": "real", "description": "Total available disk size in bytes. Compute usage%: USED_SIZE_d / TOTAL_SIZE_d * 100."},
            "USED_SIZE_d": {"type": "real", "description": "Used disk in bytes. Compare against TOTAL_SIZE_d to assess fill level."},
            "sapsid_s": {"type": "string", "description": "SAP System ID. Use for filtering."},
            "PROVIDER_INSTANCE_s": {"type": "string", "description": "SAP Monitor provider instance name."},
        },
        "kql_hints": [
            "ALWAYS filter by sapsid_s: | where sapsid_s == '<sid>'",
            "Sizes are in BYTES. Usage %: | extend used_pct = round(100.0 * USED_SIZE_d / TOTAL_SIZE_d, 1)",
            "Newest sample per volume: | summarize arg_max(TimeGenerated, *) by HOST_s, PATH_s, SUBPATH_s",
            "Disk-full risk: | extend used_pct = round(100.0 * USED_SIZE_d / TOTAL_SIZE_d, 1) | where used_pct > 85 | project HOST_s, PATH_s, USAGE_TYPE_s, used_pct",
            "A full LOG volume stops HANA accepting writes — check USAGE_TYPE_s == 'LOG' first during an outage.",
            "Cross-check with Prometheus_OSExporter_CL node_filesystem_avail_bytes for the same mount point.",
        ],
    },

    # -------------------------------------------------------------------------
    # Table 4 — SapHana_HighMemoryUsageService_CL
    # Per-HANA-service memory allocation and usage
    # -------------------------------------------------------------------------
    "SapHana_HighMemoryUsageService_CL": {
        "table_name": "SapHana_HighMemoryUsageService_CL",
        "domain": "hana_db",
        "description": (
            "SAP HANA per-service memory usage snapshot. Each row is memory stats for "
            "one HANA service. Use to identify out-of-memory conditions or services "
            "consuming excessive heap memory. Source: M_SERVICE_MEMORY."
        ),
        "data_source": "SAP Monitor HANA provider — M_SERVICE_MEMORY",
        "time_column": "TimeGenerated",
        "sid_column": "sapsid_s",
        "key_columns": ["SERVICE_NAME_s", "PORT_d", "SYSTEM_ID_s", "PERCENTAGE_HEAP_USED_MEMORY_d", "PERCENTAGE_USED_MEMORY_d"],
        "analysis_type": "hana_db",
        "columns": {
            "TimeGenerated": {"type": "datetime", "description": "UTC ingest timestamp."},
            "SERVER_UTC_t": {"type": "datetime", "description": "UTC timestamp from the HANA server."},
            "SNAPSHOT_TIME_t": {"type": "datetime", "description": "Exact timestamp when the memory snapshot was taken on HANA."},
            "SERVICE_NAME_s": {"type": "string", "description": "HANA service consuming memory: 'indexserver', 'nameserver', 'preprocessor', 'scriptserver', 'xsengine'."},
            "PORT_d": {"type": "real", "description": "TCP port of the service (e.g. 30001=nameserver, 30003=indexserver). Distinguishes multiple services on same host."},
            "DATABASE_NAME_s": {"type": "string", "description": "HANA tenant database this service belongs to."},
            "DATA_SOURCE_s": {"type": "string", "description": "'CURRENT' = live snapshot of current memory state."},
            "ALLOCATION_LIMIT_MB_d": {"type": "real", "description": "Maximum memory the service may allocate, in MB."},
            "LOGICAL_MEMORY_SIZE_MB_d": {"type": "real", "description": "Total virtual (logical) memory allocated by the service, in MB."},
            "PHYSICAL_MEMORY_SIZE_MB_d": {"type": "real", "description": "RSS — physical pages in use by the service, in MB."},
            "HEAP_MEMORY_ALLOCATED_SIZE_MB_d": {"type": "real", "description": "Total heap memory allocated by this service, in MB."},
            "HEAP_MEMORY_USED_SIZE_MB_d": {"type": "real", "description": "Heap memory actively in use, in MB."},
            "TOTAL_MEMORY_USED_SIZE_MB_d": {"type": "real", "description": "Total memory used (heap + shared + stack), in MB."},
            "FREE_MEMORY_SIZE_MB_d": {"type": "real", "description": "Free memory within the allocation limit, in MB."},
            "PERCENTAGE_USED_MEMORY_d": {"type": "real", "description": "% of ALLOCATION_LIMIT used. Values above 85% indicate high memory pressure."},
            "PERCENTAGE_HEAP_USED_MEMORY_d": {"type": "real", "description": "% of allocated heap that is actively in use. High = potential memory leak or load spike."},
            "SYSTEM_ID_s": {"type": "string", "description": "SAP System ID from the HANA memory record."},
            "Time_Generated_t": {"type": "datetime", "description": "Provider-side timestamp."},
            "sapsid_s": {"type": "string", "description": "SAP System ID. Use for filtering."},
            "PROVIDER_INSTANCE_s": {"type": "string", "description": "SAP Monitor provider instance name."},
        },
        "kql_hints": [
            "ALWAYS filter by sapsid_s: | where sapsid_s == '<sid>'",
            "This table has NO HOST_s column — services are identified by SERVICE_NAME_s + PORT_d (+ SYSTEM_ID_s).",
            "Host RAM is NOT on this table; PHYSICAL_MEMORY_SIZE_MB_d is the service RSS. For host-level memory use SapHana_LoadHistory_CL (MEMORY_SIZE_d / MEMORY_RESIDENT_d).",
            "Memory pressure: | where PERCENTAGE_USED_MEMORY_d > 85 | summarize max(PERCENTAGE_USED_MEMORY_d) by SERVICE_NAME_s, PORT_d",
            "Suspected leak: trend PERCENTAGE_HEAP_USED_MEMORY_d over time — | summarize avg(PERCENTAGE_HEAP_USED_MEMORY_d) by bin(TimeGenerated, 1h), SERVICE_NAME_s",
            "indexserver is normally the largest consumer; high usage on nameserver or scriptserver is abnormal.",
            "Correlate OOM short dumps (SapNetweaver_ShortDumps_CL) with spikes here on the same SID/time window.",
        ],
    },

    # -------------------------------------------------------------------------
    # Table 5 — SapHana_HostConfig_CL
    # HANA host configuration and failover role assignments
    # -------------------------------------------------------------------------
    "SapHana_HostConfig_CL": {
        "table_name": "SapHana_HostConfig_CL",
        "domain": "hana_db",
        "description": (
            "SAP HANA host configuration and role assignments. Each row is "
            "configuration and actual runtime roles for one HANA host. "
            "Use to detect role mismatches, host failures, or failover state changes."
        ),
        "data_source": "SAP Monitor HANA provider — M_LANDSCAPE_HOST_CONFIGURATION",
        "time_column": "TimeGenerated",
        "sid_column": "sapsid_s",
        "key_columns": ["HOST_s", "HOST_STATUS_s", "HOST_ACTIVE_s", "INDEXSERVER_ACTUAL_ROLE_s", "INDEXSERVER_CONFIG_ROLE_s"],
        "analysis_type": "hana_db",
        "columns": {
            "TimeGenerated": {"type": "datetime", "description": "UTC ingest timestamp."},
            "SERVER_UTC_t": {"type": "datetime", "description": "UTC timestamp from the HANA server."},
            "HOST_s": {"type": "string", "description": "Hostname of the HANA node (e.g. 'vchadcha01l10c')."},
            "HOST_ACTIVE_s": {"type": "string", "description": "Whether host is active: 'YES' or 'NO'. 'NO' = host is down or unreachable."},
            "HOST_STATUS_s": {"type": "string", "description": "HANA host health: 'OK', 'WARNING', 'ERROR', 'IGNORE', 'UNKNOWN'."},
            "HOST_ACTUAL_ROLES_s": {"type": "string", "description": "Actual runtime role(s): 'MASTER', 'WORKER', 'STANDBY'. Compare with HOST_CONFIG_ROLES_s — mismatch may indicate failover."},
            "HOST_CONFIG_ROLES_s": {"type": "string", "description": "Configured (intended) role(s) for this host."},
            "INDEXSERVER_ACTUAL_ROLE_s": {"type": "string", "description": "Actual indexserver role: 'MASTER' (active primary), 'SLAVE' (secondary), 'STANDBY'."},
            "INDEXSERVER_CONFIG_ROLE_s": {"type": "string", "description": "Configured indexserver role (e.g. 'WORKER', 'MASTER 1')."},
            "NAMESERVER_ACTUAL_ROLE_s": {"type": "string", "description": "Actual nameserver role: 'MASTER' or 'SLAVE'."},
            "NAMESERVER_CONFIG_ROLE_s": {"type": "string", "description": "Configured nameserver role."},
            "FAILOVER_STATUS_s": {"type": "string", "description": "Failover status — non-empty indicates failover activity or pending condition."},
            "FAILOVER_ACTUAL_GROUP_s": {"type": "string", "description": "Actual failover group this host belongs to at runtime."},
            "FAILOVER_CONFIG_GROUP_s": {"type": "string", "description": "Configured failover group for this host."},
            "FAILOVER_GROUP_s": {"type": "string", "description": "Failover group name (combined actual/config view)."},
            "IP_s": {"type": "string", "description": "IP address of the HANA host."},
            "STORAGE_ACTUAL_PARTITION_d": {"type": "real", "description": "Actual storage partition number assigned to this host at runtime."},
            "STORAGE_CONFIG_PARTITION_d": {"type": "real", "description": "Configured storage partition number for this host."},
            "STORAGE_PARTITION_d": {"type": "real", "description": "Storage partition number (combined view)."},
            "WORKER_ACTUAL_GROUPS_s": {"type": "string", "description": "Actual worker group(s) at runtime."},
            "WORKER_CONFIG_GROUPS_s": {"type": "string", "description": "Configured worker groups."},
            "REMOVE_STATUS_s": {"type": "string", "description": "Non-empty if this host is being decommissioned from the landscape."},
            "sapsid_s": {"type": "string", "description": "SAP System ID. Use for filtering."},
            "PROVIDER_INSTANCE_s": {"type": "string", "description": "SAP Monitor provider instance name."},
        },
        "kql_hints": [
            "ALWAYS filter by sapsid_s: | where sapsid_s == '<sid>'",
            "Newest state per host: | summarize arg_max(TimeGenerated, *) by HOST_s",
            "Host down: | where HOST_ACTIVE_s == 'NO' or HOST_STATUS_s in ('ERROR','UNKNOWN')",
            "Failover detection: | where INDEXSERVER_ACTUAL_ROLE_s != INDEXSERVER_CONFIG_ROLE_s or HOST_ACTUAL_ROLES_s != HOST_CONFIG_ROLES_s — an actual/config mismatch means a takeover occurred.",
            "Role flip in window: | summarize dcount(INDEXSERVER_ACTUAL_ROLE_s) by HOST_s — more than 1 means the role changed.",
            "Correlate role flips with Prometheus_HaClusterExporter_CL (ha_cluster_pacemaker_resources / node_attributes) to confirm a Pacemaker-driven takeover.",
        ],
    },

    # -------------------------------------------------------------------------
    # Table 6 — SapHana_HostInformation_CL
    # HANA host-level key-value properties
    # -------------------------------------------------------------------------
    "SapHana_HostInformation_CL": {
        "table_name": "SapHana_HostInformation_CL",
        "domain": "hana_db",
        "description": (
            "SAP HANA host information as key-value pairs. Each row is one host property. "
            "Equivalent to M_HOST_INFORMATION system view."
        ),
        "data_source": "SAP Monitor HANA provider — M_HOST_INFORMATION",
        "time_column": "TimeGenerated",
        "sid_column": "sapsid_s",
        "key_columns": ["HOST_s", "KEY_s", "VALUE_s"],
        "analysis_type": "hana_db",
        "columns": {
            "TimeGenerated": {"type": "datetime", "description": "UTC ingest timestamp."},
            "SERVER_UTC_t": {"type": "datetime", "description": "UTC timestamp from the HANA server."},
            "HOST_s": {"type": "string", "description": "Hostname the property applies to."},
            "KEY_s": {"type": "string", "description": "Property key from M_HOST_INFORMATION (e.g. 'active', 'os_version', 'cpu_count', 'mem_size', 'net_publicname')."},
            "VALUE_s": {"type": "string", "description": "Value of the property. Example: KEY_s='active' -> VALUE_s='yes' or 'no'."},
            "sapsid_s": {"type": "string", "description": "SAP System ID. Use for filtering."},
            "PROVIDER_INSTANCE_s": {"type": "string", "description": "SAP Monitor provider instance name."},
        },
        "kql_hints": [
            "ALWAYS filter by sapsid_s: | where sapsid_s == '<sid>'",
            "This is a KEY/VALUE table — always filter KEY_s, never scan it unfiltered.",
            "Pivot to columns: | summarize arg_max(TimeGenerated, VALUE_s) by HOST_s, KEY_s | evaluate pivot(KEY_s, any(max_VALUE_s), HOST_s)",
            "Host inventory: | where KEY_s in ('cpu_count','mem_size','os_name','os_version','net_publicname')",
            "Host down check: | where KEY_s == 'active' and VALUE_s != 'yes'",
            "Use this for static capacity facts (CPU count, RAM size); use SapHana_LoadHistory_CL for actual utilization.",
        ],
    },

    # -------------------------------------------------------------------------
    # Table 7 — SapHana_LoadHistory_CL
    # HANA host-level CPU / memory / disk / network load over time
    # -------------------------------------------------------------------------
    "SapHana_LoadHistory_CL": {
        "table_name": "SapHana_LoadHistory_CL",
        "domain": "hana_db",
        "description": (
            "SAP HANA host load history — CPU, memory, disk, and network metrics at regular intervals. "
            "Equivalent to HANA Load Monitor (M_LOAD_HISTORY_HOST). "
            "Use to correlate HANA performance degradation with resource exhaustion."
        ),
        "data_source": "SAP Monitor HANA provider — M_LOAD_HISTORY_HOST",
        "time_column": "TimeGenerated",
        "sid_column": "sapsid_s",
        "key_columns": ["HOST_s", "SCOPE_s", "CPU_d", "MEMORY_USED_d", "MEMORY_RESIDENT_d", "DISK_USED_d"],
        "analysis_type": "hana_db",
        "columns": {
            "TimeGenerated": {"type": "datetime", "description": "UTC ingest timestamp. Use as primary time filter."},
            "SERVER_UTC_t": {"type": "datetime", "description": "UTC timestamp from the HANA server."},
            "TIMESERIES_UTC_t": {"type": "datetime", "description": "UTC timestamp of this load data point (actual measurement time)."},
            "SERVER_LOCALTIME_t": {"type": "datetime", "description": "HANA server local time of the load data point."},
            "HOST_s": {"type": "string", "description": "HANA host this row belongs to."},
            "SCOPE_s": {"type": "string", "description": "'HOST' = host-level aggregated metrics."},
            "CPU_d": {"type": "real", "description": "CPU usage % (0-100). Values above 80% indicate CPU contention."},
            "MEMORY_SIZE_d": {"type": "real", "description": "Total physical memory of the host in MB."},
            "MEMORY_RESIDENT_d": {"type": "real", "description": "RSS — physical pages in use by HANA on this host, in MB."},
            "MEMORY_TOTAL_RESIDENT_d": {"type": "real", "description": "Total resident memory of all processes on the host, in MB."},
            "MEMORY_USED_d": {"type": "real", "description": "Memory used by HANA (HANA perspective), in MB."},
            "MEMORY_ALLOCATION_LIMIT_d": {"type": "real", "description": "HANA global memory allocation limit for this host, in MB."},
            "DISK_SIZE_d": {"type": "real", "description": "Total disk capacity referenced by HANA on this host, in GB."},
            "DISK_USED_d": {"type": "real", "description": "Disk used by HANA on this host, in GB."},
            "NETWORK_IN_d": {"type": "real", "description": "Network bytes received since last sample (-1 if not available)."},
            "NETWORK_OUT_d": {"type": "real", "description": "Network bytes sent since last sample (-1 if not available)."},
            "sapsid_s": {"type": "string", "description": "SAP System ID. Use for filtering."},
            "PROVIDER_INSTANCE_s": {"type": "string", "description": "SAP Monitor provider instance name."},
        },
        "kql_hints": [
            "ALWAYS filter by sapsid_s: | where sapsid_s == '<sid>'",
            "Use TIMESERIES_UTC_t for the real measurement time when trending; TimeGenerated is the collection time.",
            "CPU pressure: | where CPU_d > 80 | summarize max(CPU_d) by bin(TIMESERIES_UTC_t, 5m), HOST_s",
            "Memory pressure: | extend mem_pct = round(100.0 * MEMORY_USED_d / MEMORY_ALLOCATION_LIMIT_d, 1) | where mem_pct > 90",
            "NETWORK_IN_d / NETWORK_OUT_d are -1 when unavailable — always exclude negatives before aggregating.",
            "This is the primary HANA host-level resource table — use it (not SapHana_HighMemoryUsageService_CL) for host CPU/RAM.",
            "Correlate spikes with SapNetweaver_SWNC_CL ST03_DB_Time_d to prove that DB-side resource pressure is driving application response times.",
        ],
    },

    # -------------------------------------------------------------------------
    # Table 8 — SapHana_Services_CL
    # HANA process/service list with active status and port
    # -------------------------------------------------------------------------
    "SapHana_Services_CL": {
        "table_name": "SapHana_Services_CL",
        "domain": "hana_db",
        "description": (
            "SAP HANA services (processes) running on each host. "
            "Each row is one HANA service at a point in time. "
            "Equivalent to M_SERVICES. Use to detect stopped or failed HANA services."
        ),
        "data_source": "SAP Monitor HANA provider — M_SERVICES",
        "time_column": "TimeGenerated",
        "sid_column": "sapsid_s",
        "key_columns": ["HOST_s", "SERVICE_NAME_s", "ACTIVE_STATUS_s", "PORT_d", "PROCESS_ID_d"],
        "analysis_type": "hana_db",
        "columns": {
            "TimeGenerated": {"type": "datetime", "description": "UTC ingest timestamp."},
            "HOST_s": {"type": "string", "description": "Hostname where this HANA service is running."},
            "SERVICE_NAME_s": {"type": "string", "description": "HANA service name: 'daemon', 'nameserver', 'indexserver', 'preprocessor', 'scriptserver', 'xsengine', 'compileserver'."},
            "ACTIVE_STATUS_s": {"type": "string", "description": "Service active: 'YES' or 'NO'. 'NO' = service is stopped — critical if indexserver or nameserver."},
            "COORDINATOR_TYPE_s": {"type": "string", "description": "Coordinator role: 'MASTER', 'SLAVE', or 'NONE'."},
            "DETAIL_s": {"type": "string", "description": "Additional status detail for the service."},
            "IS_DATABASE_LOCAL_s": {"type": "string", "description": "Whether service runs local to a tenant DB ('TRUE'/'FALSE')."},
            "PORT_d": {"type": "real", "description": "TCP port (30000=daemon, 30001=nameserver, 30003=indexserver)."},
            "SQL_PORT_d": {"type": "real", "description": "SQL/JDBC port (0 if not applicable)."},
            "PROCESS_ID_d": {"type": "real", "description": "OS process ID (PID) of this service."},
            "sapsid_s": {"type": "string", "description": "SAP System ID. Use for filtering."},
            "PROVIDER_INSTANCE_s": {"type": "string", "description": "SAP Monitor provider instance name."},
        },
        "kql_hints": [
            "ALWAYS filter by sapsid_s: | where sapsid_s == '<sid>'",
            "Newest state per service: | summarize arg_max(TimeGenerated, *) by HOST_s, SERVICE_NAME_s, PORT_d",
            "Stopped services: | where ACTIVE_STATUS_s == 'NO' — indexserver or nameserver down is a full outage.",
            "Service restart detection: | summarize dcount(PROCESS_ID_d) by HOST_s, SERVICE_NAME_s — a changing PID means the service restarted/crashed.",
            "Use DETAIL_s for the reason when ACTIVE_STATUS_s is 'NO'.",
            "Correlate restarts with SapHana_SystemAvailability_CL events and OS memory pressure in Prometheus_OSExporter_CL.",
        ],
    },

    # -------------------------------------------------------------------------
    # Table 9 — SapHana_SystemAvailability_CL
    # HANA system availability events
    # -------------------------------------------------------------------------
    "SapHana_SystemAvailability_CL": {
        "table_name": "SapHana_SystemAvailability_CL",
        "domain": "hana_db",
        "description": (
            "SAP HANA system availability monitoring events. Each row is one availability check "
            "(PING, state transition, or error) from the SAP Monitor HANA provider. "
            "Use to detect HANA system downtime, host failures, or service interruptions."
        ),
        "data_source": "SAP Monitor HANA provider — availability check API",
        "time_column": "TimeGenerated",
        "sid_column": "sapsid_s",
        "key_columns": ["EVENT_NAME_s", "SYSTEM_ACTIVE_s", "SYSTEM_STATUS_s", "HOST_ACTIVE_s", "HOST_STATUS_s", "ERROR_MESSAGE_s"],
        "analysis_type": "hana_db",
        "columns": {
            "TimeGenerated": {"type": "datetime", "description": "UTC ingest timestamp. Use as primary time filter."},
            "SERVER_UTC_t": {"type": "datetime", "description": "UTC timestamp from the HANA server."},
            "TIMESERIES_UTC_t": {"type": "datetime", "description": "UTC timestamp of this availability event."},
            "EVENT_TIME_t": {"type": "datetime", "description": "Timestamp of the specific availability event."},
            "EVENT_NAME_s": {"type": "string", "description": "'PING' = regular heartbeat check. Other values = state-change events or errors."},
            "SYSTEM_ACTIVE_s": {"type": "string", "description": "Whether the overall HANA system is active: 'YES' or 'NO'."},
            "SYSTEM_STATUS_s": {"type": "string", "description": "System-level health: 'OK', 'WARNING', or 'ERROR'."},
            "HOST_s": {"type": "string", "description": "Hostname of the HANA node this event originates from."},
            "HOST_ACTIVE_s": {"type": "string", "description": "Whether this host is active at event time: 'YES' or 'NO'."},
            "HOST_STATUS_s": {"type": "string", "description": "Host health at event time: 'OK', 'WARNING', 'ERROR', 'IGNORE'."},
            "HOST_ACTUAL_ROLES_s": {"type": "string", "description": "Actual roles of this host at event time."},
            "HOST_CONFIG_ROLES_s": {"type": "string", "description": "Configured roles for this host."},
            "SERVICE_NAME_s": {"type": "string", "description": "HANA service involved (if applicable)."},
            "SERVICE_ACTIVE_s": {"type": "string", "description": "Whether the service was active at event time."},
            "DATABASE_NAME_s": {"type": "string", "description": "Tenant database name associated with this event."},
            "DATABASE_ACTIVE_s": {"type": "string", "description": "Whether the tenant database was active at event time."},
            "ERROR_MESSAGE_s": {"type": "string", "description": "Error message if availability check failed. Non-empty = connection or auth failure."},
            "EVENT_DETAIL_s": {"type": "string", "description": "Additional event detail."},
            "IS_ORIGIN_s": {"type": "string", "description": "Whether this host originated the event ('TRUE'/'FALSE')."},
            "TRACE_HOST_s": {"type": "string", "description": "Host that generated the availability trace entry."},
            "SITE_ID_d": {"type": "real", "description": "HANA SR site ID (0=primary, 1/2=secondary sites)."},
            "PORT_d": {"type": "real", "description": "Port of the service involved in this event."},
            "STORAGE_ACTUAL_PARTITION_d": {"type": "real", "description": "Actual storage partition number at event time."},
            "STORAGE_CONFIG_PARTITION_d": {"type": "real", "description": "Configured storage partition at event time."},
            "TARGET_HOST_s": {"type": "string", "description": "Target host for this event (in failover/migration scenarios)."},
            "TARGET_HOST_ACTUAL_ROLES_s": {"type": "string", "description": "Actual roles of the target host."},
            "TARGET_HOST_CONFIG_ROLES_s": {"type": "string", "description": "Configured roles of the target host."},
            "TARGET_STORAGE_ACTUAL_PARTITION_d": {"type": "real", "description": "Actual storage partition of the target host."},
            "TARGET_STORAGE_CONFIG_PARTITION_d": {"type": "real", "description": "Configured storage partition of the target host."},
            "VOLUME_ID_d": {"type": "real", "description": "HANA volume ID involved in this event."},
            "GUID_g": {"type": "string", "description": "Unique identifier for this availability event record."},
            "sapsid_s": {"type": "string", "description": "SAP System ID. Use for filtering."},
            "PROVIDER_INSTANCE_s": {"type": "string", "description": "SAP Monitor provider instance name."},
        },
        "kql_hints": [
            "ALWAYS filter by sapsid_s: | where sapsid_s == '<sid>'",
            "Downtime windows: | where SYSTEM_ACTIVE_s == 'NO' or SYSTEM_STATUS_s == 'ERROR' | summarize min(EVENT_TIME_t), max(EVENT_TIME_t) by HOST_s",
            "Exclude routine heartbeats to see only real events: | where EVENT_NAME_s != 'PING'",
            "Connection failures: | where isnotempty(ERROR_MESSAGE_s) | summarize count() by ERROR_MESSAGE_s, HOST_s",
            "Availability %: | summarize round(100.0 * countif(SYSTEM_ACTIVE_s == 'YES') / count(), 2) by bin(TimeGenerated, 1h)",
            "Takeover / failover events populate TARGET_HOST_s and SITE_ID_d — filter isnotempty(TARGET_HOST_s) to isolate them.",
            "Pair with SapHana_SqlProbe_CL (earliest outage signal) and Prometheus_HaClusterExporter_CL (cluster-side cause).",
        ],
    },

    # -------------------------------------------------------------------------
    # Table 10 — SapHana_SystemOverview_CL
    # HANA system overview key-value pairs
    # -------------------------------------------------------------------------
    "SapHana_SystemOverview_CL": {
        "table_name": "SapHana_SystemOverview_CL",
        "domain": "hana_db",
        "description": (
            "SAP HANA system overview as key-value pairs. Each row is one property "
            "from the HANA System Overview screen. Contains system identity, version, and status."
        ),
        "data_source": "SAP Monitor HANA provider — system overview API",
        "time_column": "TimeGenerated",
        "sid_column": "sapsid_s",
        "key_columns": ["SECTION_s", "NAME_s", "VALUE_s", "STATUS_s"],
        "analysis_type": "hana_db",
        "columns": {
            "TimeGenerated": {"type": "datetime", "description": "UTC ingest timestamp."},
            "SERVER_UTC_t": {"type": "datetime", "description": "UTC timestamp from the HANA server."},
            "SECTION_s": {"type": "string", "description": "Logical section grouping: 'System', 'Services', 'Memory', 'Disk', 'Alerts'."},
            "NAME_s": {"type": "string", "description": "Property name (e.g. 'Instance ID', 'Version', 'Start Time', 'Overall Service Status', 'CPU')."},
            "VALUE_s": {"type": "string", "description": "Property value as string (e.g. NAME_s='Instance ID' -> VALUE_s='CHA')."},
            "STATUS_s": {"type": "string", "description": "Status indicator: 'OK', 'WARNING', 'ERROR', or empty. Filter for degraded properties."},
            "sapsid_s": {"type": "string", "description": "SAP System ID. Use for filtering."},
            "PROVIDER_INSTANCE_s": {"type": "string", "description": "SAP Monitor provider instance name."},
        },
        "kql_hints": [
            "ALWAYS filter by sapsid_s: | where sapsid_s == '<sid>'",
            "This is a KEY/VALUE table — filter SECTION_s and/or NAME_s rather than scanning it.",
            "Fastest health triage: | where STATUS_s in ('WARNING','ERROR') | summarize arg_max(TimeGenerated, *) by SECTION_s, NAME_s",
            "Newest snapshot: | summarize arg_max(TimeGenerated, VALUE_s, STATUS_s) by SECTION_s, NAME_s",
            "Useful NAME_s values: 'Version', 'Start Time', 'Overall Service Status', 'All Started', 'Data Backup', 'Log Backup'.",
            "VALUE_s is always a string — cast explicitly if you need to compare numerically.",
        ],
    },

    # -------------------------------------------------------------------------
    # Table 11 — SapHana_SystemReplication_CL
    # HANA System Replication (HSR) state and statistics
    # -------------------------------------------------------------------------
    "SapHana_SystemReplication_CL": {
        "table_name": "SapHana_SystemReplication_CL",
        "domain": "hana_db",
        "description": (
            "SAP HANA System Replication (HSR) status and performance metrics. "
            "Each row is replication state for one service on the primary site. "
            "Use to detect replication lag, disconnection, or takeover conditions "
            "that are root cause for HA failover events. Source: M_SERVICE_REPLICATION."
        ),
        "data_source": "SAP Monitor HANA provider — M_SERVICE_REPLICATION",
        "time_column": "TimeGenerated",
        "sid_column": "sapsid_s",
        "key_columns": [
            "SERVICE_NAME_s", "HOST_s", "SITE_NAME_s", "SECONDARY_HOST_s",
            "SYSTEM_REPLICATION_STATUS_s", "SERVICE_REPLICATION_STATUS_s",
            "REPLICATION_MODE_s", "TIME_DIFF_SECONDS_d", "SECONDARY_FULLY_RECOVERABLE_s",
        ],
        "analysis_type": "hana_db",
        "columns": {
            "TimeGenerated": {"type": "datetime", "description": "UTC ingest timestamp. Use as primary time filter."},
            "SERVER_UTC_t": {"type": "datetime", "description": "UTC timestamp from the HANA server."},
            "SERVER_LOCALTIME_t": {"type": "datetime", "description": "HANA server local time at collection."},
            "HOST_s": {"type": "string", "description": "Primary site hostname where this replication service runs."},
            "SERVICE_NAME_s": {"type": "string", "description": "HANA service being replicated (e.g. 'nameserver', 'indexserver')."},
            "DATABASE_NAME_s": {"type": "string", "description": "Tenant database being replicated."},
            "SYSTEM_ID_s": {"type": "string", "description": "SAP System ID from the HANA replication catalog."},
            "SITE_NAME_s": {"type": "string", "description": "Name of the primary replication site (e.g. 'SITEB')."},
            "SECONDARY_HOST_s": {"type": "string", "description": "Hostname of the HANA secondary node."},
            "SECONDARY_SITE_NAME_s": {"type": "string", "description": "Name of the secondary replication site (e.g. 'SITEA')."},
            "SYSTEM_REPLICATION_STATUS_s": {"type": "string", "description": "Overall HSR status: 'ACTIVE' = healthy, 'ERROR' = broken/disconnected, 'UNKNOWN'/'INITIALIZING' = transitional."},
            "SERVICE_REPLICATION_STATUS_s": {"type": "string", "description": "Per-service replication status: 'ACTIVE' = normal, 'ERROR' = issue with this service."},
            "SERVICE_REPLICATION_STATUS_DETAILS_s": {"type": "string", "description": "Detailed error message for service replication state."},
            "REPLICATION_MODE_s": {"type": "string", "description": "HSR mode: 'SYNC' (zero data loss), 'SYNCMEM' (lower latency), 'ASYNC' (RPO > 0)."},
            "OPERATION_MODE_s": {"type": "string", "description": "HSR operation mode: 'logreplay' (default), 'delta_datashipping'."},
            "ACTIVE_STATUS_s": {"type": "string", "description": "Whether replication is active: 'YES' or 'NO'."},
            "FULL_SYNC_s": {"type": "string", "description": "'DISABLED' = normal. 'ENABLED' = primary blocking commits until secondary confirms (maximum durability)."},
            "SECONDARY_FULLY_RECOVERABLE_s": {"type": "string", "description": "'TRUE' = secondary caught up, no data loss on takeover. 'FALSE' = secondary lagging, takeover would lose data."},
            "SECONDARY_FAILOVER_COUNT_d": {"type": "real", "description": "Number of times secondary has failed over to primary role."},
            "SECONDARY_RECONNECT_COUNT_d": {"type": "real", "description": "Number of secondary reconnections after disconnects."},
            "TIER_d": {"type": "real", "description": "Replication tier (1=direct secondary, 2=tertiary in multitier setup)."},
            "TIME_DIFF_SECONDS_d": {"type": "real", "description": "Replication lag in seconds (last shipped vs replayed log). 0 = in sync. >30 = falling behind."},
            "LAST_LOG_POSITION_d": {"type": "real", "description": "Last redo log position on the primary."},
            "SHIPPED_LOG_POSITION_d": {"type": "real", "description": "Last log position shipped to the secondary."},
            "REPLAYED_LOG_POSITION_d": {"type": "real", "description": "Last log position replayed on the secondary."},
            "LAST_LOG_POSITION_TIME_t": {"type": "datetime", "description": "Timestamp of the last log position on the primary."},
            "SHIPPED_LOG_POSITION_TIME_t": {"type": "datetime", "description": "Timestamp when the last log was shipped to secondary."},
            "REPLAYED_LOG_POSITION_TIME_t": {"type": "datetime", "description": "Timestamp when the last log was replayed on secondary."},
            "ASYNC_BUFF_USED_MB_d": {"type": "real", "description": "Async replication buffer used in MB. Non-zero in SYNC mode = backpressure."},
            "SHIPPED_LOG_BUFFERS_COUNT_d": {"type": "real", "description": "Total log buffers shipped since HANA start."},
            "SHIPPED_LOG_BUFFERS_SIZE_d": {"type": "real", "description": "Total bytes of log data shipped since HANA start."},
            "SHIPPED_LOG_BUFFERS_DURATION_d": {"type": "real", "description": "Total microseconds spent shipping log buffers."},
            "TOTAL_WRITE_SIZE_d": {"type": "real", "description": "Total bytes written to the replication channel since HANA start."},
            "TOTAL_WRITE_TIME_d": {"type": "real", "description": "Total microseconds writing to the replication channel."},
            "TOTAL_TRIGGER_ASYNC_WRITES_d": {"type": "real", "description": "Total async write trigger events since HANA start."},
            "SHIPPED_FULL_REPLICA_SIZE_d": {"type": "real", "description": "Size of full data replica shipped during initial replication setup, in bytes."},
            "SHIPPED_FULL_REPLICA_DURATION_d": {"type": "real", "description": "Duration of full replica shipment in microseconds."},
            "sapsid_s": {"type": "string", "description": "SAP System ID. Use for filtering."},
            "PROVIDER_INSTANCE_s": {"type": "string", "description": "SAP Monitor provider instance name."},
        },
        "kql_hints": [
            "ALWAYS filter by sapsid_s: | where sapsid_s == '<sid>'",
            "Replication broken: | where SYSTEM_REPLICATION_STATUS_s != 'ACTIVE' or SERVICE_REPLICATION_STATUS_s != 'ACTIVE' | project TimeGenerated, HOST_s, SERVICE_NAME_s, SERVICE_REPLICATION_STATUS_DETAILS_s",
            "Lag trend: | summarize max(TIME_DIFF_SECONDS_d) by bin(TimeGenerated, 5m), SERVICE_NAME_s — sustained values above 30s mean the secondary is falling behind.",
            "Data-loss risk on takeover: | where SECONDARY_FULLY_RECOVERABLE_s == 'FALSE'",
            "Instability: | summarize max(SECONDARY_RECONNECT_COUNT_d), max(SECONDARY_FAILOVER_COUNT_d) by SECONDARY_HOST_s — rising reconnects mean a flapping network link.",
            "Log shipping backlog: compare SHIPPED_LOG_POSITION_d against REPLAYED_LOG_POSITION_d; a widening gap means the secondary cannot replay fast enough.",
            "Counters (SHIPPED_*, TOTAL_WRITE_*) are cumulative since HANA start — always use delta/rate, never the raw value.",
            "This table maps to SFAIL in Prometheus_HaClusterExporter_CL node attributes — check both for HA failover RCA.",
        ],
    },

    # -------------------------------------------------------------------------
    # Table 12 — SapHana_size01_CL
    # HANA table size and row count statistics
    # -------------------------------------------------------------------------
    "SapHana_size01_CL": {
        "table_name": "SapHana_size01_CL",
        "domain": "hana_db",
        "description": (
            "SAP HANA table size statistics. Each row is one HANA database table "
            "with row count, partition count, and memory footprint. "
            "Use to identify tables causing excessive memory or performance issues."
        ),
        "data_source": "SAP Monitor HANA provider — table size API",
        "time_column": "TimeGenerated",
        "sid_column": "sapsid_s",
        "key_columns": ["TABLE_NAME_s", "DATABASE_NAME_s", "RECORDS_d", "MEMORY_SIZE_IN_TOTAL_GIB_d", "PARTITION_COUNT_d"],
        "analysis_type": "hana_db",
        "columns": {
            "TimeGenerated": {"type": "datetime", "description": "UTC ingest timestamp."},
            "SERVER_UTC_t": {"type": "datetime", "description": "UTC timestamp from the HANA server."},
            "TABLE_NAME_s": {"type": "string", "description": "Name of the HANA table (e.g. 'ALL_TABLES' for aggregated, or individual table names)."},
            "DATABASE_NAME_s": {"type": "string", "description": "Tenant database name the table belongs to (e.g. 'SYSTEMDB')."},
            "SYSTEM_ID_s": {"type": "string", "description": "SAP System ID from the HANA table size record."},
            "RECORDS_d": {"type": "real", "description": "Number of rows (records) in this table."},
            "PARTITION_COUNT_d": {"type": "real", "description": "Number of partitions this table is split across."},
            "MEMORY_SIZE_IN_TOTAL_GIB_d": {"type": "real", "description": "Current total in-memory size of this table in GiB."},
            "ESTIMATED_MAX_MEMORY_SIZE_IN_TOTAL_GIB_d": {"type": "real", "description": "Estimated max memory this table could consume based on data growth, in GiB. Use for capacity planning."},
            "sapsid_s": {"type": "string", "description": "SAP System ID. Use for filtering."},
            "PROVIDER_INSTANCE_s": {"type": "string", "description": "SAP Monitor provider instance name."},
        },
        "kql_hints": [
            "ALWAYS filter by sapsid_s: | where sapsid_s == '<sid>'",
            "TABLE_NAME_s == 'ALL_TABLES' is the landscape-wide AGGREGATE row — exclude it when ranking individual tables, or you will double count.",
            "Largest tables: | where TABLE_NAME_s != 'ALL_TABLES' | summarize arg_max(TimeGenerated, *) by TABLE_NAME_s | top 20 by MEMORY_SIZE_IN_TOTAL_GIB_d desc",
            "Growth: | where TABLE_NAME_s == '<table>' | summarize max(MEMORY_SIZE_IN_TOTAL_GIB_d) by bin(TimeGenerated, 1d)",
            "Capacity risk: | extend headroom = ESTIMATED_MAX_MEMORY_SIZE_IN_TOTAL_GIB_d - MEMORY_SIZE_IN_TOTAL_GIB_d | where headroom < 10",
            "High PARTITION_COUNT_d with high RECORDS_d indicates a table near the 2-billion-row-per-partition limit — flag for repartitioning.",
        ],
    },

    # -------------------------------------------------------------------------
    # Table 13 — SapHana_SqlProbe_CL
    # HANA SQL connectivity probe (heartbeat check)
    # -------------------------------------------------------------------------
    "SapHana_SqlProbe_CL": {
        "table_name": "SapHana_SqlProbe_CL",
        "domain": "hana_db",
        "description": (
            "SAP HANA SQL connectivity probe — heartbeat check that executes a simple SQL "
            "against the HANA database and measures latency. Each row is one probe result. "
            "SUCCESS_b=false indicates HANA is unreachable. Use as the earliest indicator of "
            "HANA connectivity failures before other tables stop reporting."
        ),
        "data_source": "SAP Monitor HANA provider — SQL connectivity probe",
        "time_column": "TimeGenerated",
        "sid_column": "sapsid_s",
        "key_columns": ["sapsid_s", "HOST_s", "SUCCESS_b", "LATENCY_MS_d"],
        "analysis_type": "hana_db",
        "columns": {
            "TimeGenerated": {"type": "datetime", "description": "UTC ingest timestamp. Use as primary time filter."},
            "Time_Generated_t": {"type": "datetime", "description": "Provider-side timestamp."},
            "LOCAL_UTC_t": {"type": "datetime", "description": "Local UTC timestamp of probe execution."},
            "HOST_s": {"type": "string", "description": "HANA host IP or hostname being probed."},
            "SUCCESS_b": {"type": "bool", "description": "Probe result: true=HANA reachable, false=HANA unreachable (CRITICAL)."},
            "LATENCY_MS_d": {"type": "real", "description": "SQL round-trip latency in milliseconds (only present when SUCCESS_b=true). >100ms = slow."},
            "sapsid_s": {"type": "string", "description": "SAP System ID. Use for filtering."},
            "PROVIDER_INSTANCE_s": {"type": "string", "description": "SAP Monitor provider instance name."},
        },
        "kql_hints": [
            "ALWAYS filter by sapsid_s: | where sapsid_s == '<sid>'",
            "Outage windows: | where SUCCESS_b == false | summarize failures = count(), first = min(TimeGenerated), last = max(TimeGenerated) by HOST_s",
            "Availability %: | summarize round(100.0 * countif(SUCCESS_b == true) / count(), 2) by bin(TimeGenerated, 1h), HOST_s",
            "Latency trend: | where SUCCESS_b == true | summarize avg(LATENCY_MS_d), percentile(LATENCY_MS_d, 95) by bin(TimeGenerated, 15m)",
            "This is the earliest signal of a HANA outage — check it FIRST, before other SapHana_* tables simply stop reporting.",
            "Gaps in this table (no rows at all) mean the AMS collector itself is down, not necessarily HANA.",
        ],
    },

    # -------------------------------------------------------------------------
    # Table 14 — SapHana_StatisticsServerHealth_CL
    # HANA Statistics Server health status
    # -------------------------------------------------------------------------
    "SapHana_StatisticsServerHealth_CL": {
        "table_name": "SapHana_StatisticsServerHealth_CL",
        "domain": "hana_db",
        "description": (
            "SAP HANA Statistics Server health check. Reports whether the embedded "
            "statistics server is active and its installation status. The statistics server "
            "drives internal monitoring, alerting, and advisor features within HANA."
        ),
        "data_source": "SAP Monitor HANA provider — Statistics Server health",
        "time_column": "TimeGenerated",
        "sid_column": "sapsid_s",
        "key_columns": ["sapsid_s", "CURRENTSTATUS_s", "INSTALLATIONSTATUS_s"],
        "analysis_type": "hana_db",
        "columns": {
            "TimeGenerated": {"type": "datetime", "description": "UTC ingest timestamp."},
            "Time_Generated_t": {"type": "datetime", "description": "Provider-side timestamp."},
            "CURRENTSTATUS_s": {"type": "string", "description": "Current status of statistics server: 'active' or 'inactive'. 'inactive' = internal monitoring disabled."},
            "INSTALLATIONSTATUS_s": {"type": "string", "description": "Installation status with timestamp (e.g. 'Done (okay) since ...')."},
            "sapsid_s": {"type": "string", "description": "SAP System ID. Use for filtering."},
            "PROVIDER_INSTANCE_s": {"type": "string", "description": "SAP Monitor provider instance name."},
        },
        "kql_hints": [
            "ALWAYS filter by sapsid_s: | where sapsid_s == '<sid>'",
            "Newest state only: | summarize arg_max(TimeGenerated, *) by sapsid_s",
            "Problem check: | where CURRENTSTATUS_s != 'active'",
            "IMPORTANT: when the statistics server is inactive, SapHana_Alerts_CL stops being populated — an empty alerts table is then a collection artefact, not a healthy system. Always check this table before concluding 'no HANA alerts'.",
        ],
    },

    # -------------------------------------------------------------------------
    # Table 15 — SapHana_DiskFragmentation_CL
    # HANA data/log volume fragmentation metrics
    # -------------------------------------------------------------------------
    "SapHana_DiskFragmentation_CL": {
        "table_name": "SapHana_DiskFragmentation_CL",
        "domain": "hana_db",
        "description": (
            "SAP HANA disk fragmentation metrics. Each row is one data/log volume file "
            "with its total size, used size, and fragmentation percentage. "
            "High fragmentation (>30%) can impact I/O performance and disk space efficiency."
        ),
        "data_source": "SAP Monitor HANA provider — disk fragmentation check",
        "time_column": "TimeGenerated",
        "sid_column": "sapsid_s",
        "key_columns": ["sapsid_s", "HOST_s", "FILE_NAME_s", "FILE_TYPE_s", "UNUSED_FRAGMENTATION_PCT_d"],
        "analysis_type": "hana_db",
        "columns": {
            "TimeGenerated": {"type": "datetime", "description": "UTC ingest timestamp."},
            "Time_Generated_t": {"type": "datetime", "description": "Provider-side timestamp."},
            "SERVER_UTC_t": {"type": "datetime", "description": "HANA server UTC timestamp at collection."},
            "HOST_s": {"type": "string", "description": "HANA host where the volume resides."},
            "DATABASE_NAME_s": {"type": "string", "description": "Tenant database name (e.g. SYSTEMDB or tenant SID)."},
            "PORT_d": {"type": "real", "description": "Service port owning the volume."},
            "FILE_NAME_s": {"type": "string", "description": "Full path of the data/log volume file (e.g. /hana/data/T09/mnt00001/hdb00001/datavolume_0000.dat)."},
            "FILE_TYPE_s": {"type": "string", "description": "Volume type: 'DATA' or 'LOG'."},
            "TOTAL_SIZE_MB_d": {"type": "real", "description": "Total allocated volume file size in MB."},
            "USED_SIZE_MB_d": {"type": "real", "description": "Used portion of the volume in MB."},
            "UNUSED_FRAGMENTATION_PCT_d": {"type": "real", "description": "Fragmentation percentage of unused space. >30% = consider online data volume reorganization."},
            "ENCRYPTION_ACTIVE_s": {"type": "string", "description": "Whether volume encryption is active: 'TRUE' or 'FALSE'."},
            "sapsid_s": {"type": "string", "description": "SAP System ID. Use for filtering."},
            "PROVIDER_INSTANCE_s": {"type": "string", "description": "SAP Monitor provider instance name."},
        },
        "kql_hints": [
            "ALWAYS filter by sapsid_s: | where sapsid_s == '<sid>'",
            "Take the newest sample per file: | summarize arg_max(TimeGenerated, *) by HOST_s, FILE_NAME_s",
            "Reorg candidates: | where FILE_TYPE_s == 'DATA' and UNUSED_FRAGMENTATION_PCT_d > 30 | project HOST_s, FILE_NAME_s, TOTAL_SIZE_MB_d, USED_SIZE_MB_d, UNUSED_FRAGMENTATION_PCT_d",
            "Reclaimable space: | extend reclaimable_mb = TOTAL_SIZE_MB_d - USED_SIZE_MB_d | summarize sum(reclaimable_mb) by HOST_s",
            "High fragmentation on LOG volumes usually points to log backup problems — cross-check SapHana_BackupCatalog_CL for 'log backup' failures.",
            "Correlate with SapHana_Disks_CL (mount-point fill level) before recommending a reorg.",
        ],
    },

    # -------------------------------------------------------------------------
    # Table 16 — SapHana_Mvcc_CL
    # HANA MVCC (Multi-Version Concurrency Control) version count
    # -------------------------------------------------------------------------
    "SapHana_Mvcc_CL": {
        "table_name": "SapHana_Mvcc_CL",
        "domain": "hana_db",
        "description": (
            "SAP HANA MVCC version count monitoring. Tracks the number of active MVCC versions "
            "per service. High version counts (>10M) indicate long-running transactions or "
            "uncommitted write transactions preventing garbage collection, which can lead to "
            "memory exhaustion and performance degradation."
        ),
        "data_source": "SAP Monitor HANA provider — M_MVCC_OVERVIEW",
        "time_column": "TimeGenerated",
        "sid_column": "sapsid_s",
        "key_columns": ["sapsid_s", "HOST_s", "NAME_s", "VALUE_s", "PORT_d"],
        "analysis_type": "hana_db",
        "columns": {
            "TimeGenerated": {"type": "datetime", "description": "UTC ingest timestamp."},
            "Time_Generated_t": {"type": "datetime", "description": "Provider-side timestamp."},
            "SERVER_UTC_t": {"type": "datetime", "description": "HANA server UTC timestamp at collection."},
            "HOST_s": {"type": "string", "description": "HANA host where the service is running."},
            "PORT_d": {"type": "real", "description": "Service port (e.g. 31001=nameserver, 31003=indexserver)."},
            "NAME_s": {"type": "string", "description": "MVCC metric name: 'NUM_VERSIONS' = total active row versions across all tables."},
            "VALUE_s": {"type": "string", "description": "Metric value as string. Parse to integer. >10M versions = investigate long-running transactions."},
            "sapsid_s": {"type": "string", "description": "SAP System ID. Use for filtering."},
            "PROVIDER_INSTANCE_s": {"type": "string", "description": "SAP Monitor provider instance name."},
        },
        "kql_hints": [
            "ALWAYS filter by sapsid_s: | where sapsid_s == '<sid>'",
            "VALUE_s is a STRING — cast before comparing: | extend versions = tolong(VALUE_s)",
            "Version growth trend: | where NAME_s == 'NUM_VERSIONS' | extend versions = tolong(VALUE_s) | summarize max(versions) by bin(TimeGenerated, 15m), HOST_s, PORT_d",
            "Alert threshold: versions > 10000000 sustained = MVCC garbage collection is blocked.",
            "RCA chain for rising versions: check SapHana_UncommittedWriteTransactions_CL (oldest MVCC_TIMESTAMP_d), then SapHana_LongRunningTransactions_CL, then SapHana_LongIdlingCursors_CL.",
            "Rising versions plus rising PERCENTAGE_USED_MEMORY_d in SapHana_HighMemoryUsageService_CL is the classic pre-OOM signature.",
        ],
    },

    # -------------------------------------------------------------------------
    # Table 17 — SapHana_License_Status_CL
    # HANA license status and memory usage vs licensed limit
    # -------------------------------------------------------------------------
    "SapHana_License_Status_CL": {
        "table_name": "SapHana_License_Status_CL",
        "domain": "hana_db",
        "description": (
            "SAP HANA license status. Reports the licensed memory limit, current memory usage, "
            "and license validity. Use to detect if HANA is approaching or exceeding its "
            "licensed memory capacity, which can cause HANA to enter lockdown mode."
        ),
        "data_source": "SAP Monitor HANA provider — M_LICENSE",
        "time_column": "TimeGenerated",
        "sid_column": "sapsid_s",
        "key_columns": ["sapsid_s", "PRODUCT_LIMIT_d", "PRODUCT_USAGE_d", "VALID_s", "PERMANENT_s"],
        "analysis_type": "hana_db",
        "columns": {
            "TimeGenerated": {"type": "datetime", "description": "UTC ingest timestamp."},
            "Time_Generated_t": {"type": "datetime", "description": "Provider-side timestamp."},
            "SERVER_UTC_t": {"type": "datetime", "description": "HANA server UTC timestamp at collection."},
            "SID_s": {"type": "string", "description": "SAP System ID (from license record)."},
            "SYSTEM_ID_s": {"type": "string", "description": "HANA system ID in the license."},
            "HOSTNAME_s": {"type": "string", "description": "Licensed hostname."},
            "HARDWARE_KEY_s": {"type": "string", "description": "Hardware key for license validation."},
            "INSTALL_NO_s": {"type": "string", "description": "SAP installation number."},
            "SYSTEM_NO_s": {"type": "string", "description": "SAP system number."},
            "PRODUCT_LIMIT_d": {"type": "real", "description": "Licensed memory limit in GB. HANA locks down if usage exceeds this."},
            "PRODUCT_USAGE_d": {"type": "real", "description": "Current peak memory usage in GB. Compare with PRODUCT_LIMIT_d."},
            "VALID_s": {"type": "string", "description": "License validity: 'TRUE' = valid. 'FALSE' = expired — HANA may lock down."},
            "PERMANENT_s": {"type": "string", "description": "Whether license is permanent: 'TRUE' or 'FALSE' (temporary/trial)."},
            "START_DATE_t": {"type": "datetime", "description": "License start date."},
            "EXPIRATION_DATE_t": {"type": "datetime", "description": "License expiry date. Empty for permanent licenses. HANA enters lockdown 28 days after expiry."},
            "sapsid_s": {"type": "string", "description": "SAP System ID. Use for filtering."},
            "PROVIDER_INSTANCE_s": {"type": "string", "description": "SAP Monitor provider instance name."},
        },
        "kql_hints": [
            "ALWAYS filter by sapsid_s: | where sapsid_s == '<sid>'",
            "This is a slowly-changing table — take the newest row: | summarize arg_max(TimeGenerated, *) by sapsid_s, HOSTNAME_s",
            "Memory headroom: | extend usage_pct = round(100.0 * PRODUCT_USAGE_d / PRODUCT_LIMIT_d, 1) | where usage_pct > 90",
            "Expiry risk: | where PERMANENT_s == 'FALSE' and isnotempty(EXPIRATION_DATE_t) | extend days_left = datetime_diff('day', EXPIRATION_DATE_t, now())",
            "Lockdown risk: VALID_s == 'FALSE' or usage above PRODUCT_LIMIT_d — both cause HANA to reject new connections.",
            "If HANA suddenly refuses connections, check VALID_s here BEFORE investigating network or service failures.",
        ],
    },

    # -------------------------------------------------------------------------
    # Table 18 — SapHana_ConfigurationParameters_CL
    # HANA configuration parameter recommendations
    # -------------------------------------------------------------------------
    "SapHana_ConfigurationParameters_CL": {
        "table_name": "SapHana_ConfigurationParameters_CL",
        "domain": "hana_db",
        "description": (
            "SAP HANA configuration parameter recommendations. Each row is one parameter "
            "where the configured value deviates from SAP's recommended value per SAP Notes. "
            "Includes the exact SQL commands to implement and undo the recommended change."
        ),
        "data_source": "SAP Monitor HANA provider — configuration parameter check",
        "time_column": "TimeGenerated",
        "sid_column": "sapsid_s",
        "key_columns": ["sapsid_s", "PARAMETER_NAME_s", "SECTION_s", "CONFIGURED_VALUE_s", "RECOMMENDED_VALUE_s"],
        "analysis_type": "hana_db",
        "columns": {
            "TimeGenerated": {"type": "datetime", "description": "UTC ingest timestamp."},
            "Time_Generated_t": {"type": "datetime", "description": "Provider-side timestamp."},
            "PARAMETER_NAME_s": {"type": "string", "description": "HANA parameter name (e.g. statement_memory_limit, max_concurrency)."},
            "SECTION_s": {"type": "string", "description": "INI file section (e.g. memorymanager, indexserver, persistence)."},
            "FILE_NAME_s": {"type": "string", "description": "Configuration file name (e.g. global.ini, indexserver.ini)."},
            "CONFIG_LAYER_s": {"type": "string", "description": "Configuration layer: DEFAULT, SYSTEM, DATABASE, HOST."},
            "CONFIGURED_VALUE_s": {"type": "string", "description": "Current configured value (may be very large for defaults like max int)."},
            "RECOMMENDED_VALUE_s": {"type": "string", "description": "SAP-recommended value or range (e.g. '30 to 500')."},
            "SAP_NOTE_s": {"type": "string", "description": "SAP Note number providing the recommendation (e.g. 1999997, 2222250)."},
            "P_s": {"type": "string", "description": "Priority indicator for the recommendation."},
            "IMPLEMENTATION_COMMAND_s": {"type": "string", "description": "Exact ALTER SYSTEM command to apply the recommended value."},
            "UNDO_COMMAND_s": {"type": "string", "description": "Exact ALTER SYSTEM command to revert the change."},
            "sapsid_s": {"type": "string", "description": "SAP System ID. Use for filtering."},
            "PROVIDER_INSTANCE_s": {"type": "string", "description": "SAP Monitor provider instance name."},
        },
        "kql_hints": [
            "ALWAYS filter by sapsid_s: | where sapsid_s == '<sid>'",
            "Slowly-changing table — deduplicate: | summarize arg_max(TimeGenerated, *) by PARAMETER_NAME_s, SECTION_s, FILE_NAME_s",
            "Every row is already a DEVIATION from SAP's recommendation — the row's existence is the finding.",
            "Memory-related RCA: | where SECTION_s in ('memorymanager','global') or PARAMETER_NAME_s has 'memory'",
            "Always cite SAP_NOTE_s in RCA output, and surface IMPLEMENTATION_COMMAND_s / UNDO_COMMAND_s as the remediation pair.",
            "CONFIGURED_VALUE_s can be a huge default (e.g. max int) — that usually means 'unlimited', not a real tuned value.",
        ],
    },

    # -------------------------------------------------------------------------
    # Table 19 — SapHana_LongIdlingCursors_CL
    # HANA long-idling open cursors (no current data — schema from LA metadata)
    # -------------------------------------------------------------------------
    "SapHana_LongIdlingCursors_CL": {
        "table_name": "SapHana_LongIdlingCursors_CL",
        "domain": "hana_db",
        "description": (
            "SAP HANA long-idling cursors. Each row is one cursor/statement that has been "
            "idle beyond the configured threshold. Idle cursors hold resources (memory, MVCC versions) "
            "and can lead to memory leaks and growing version counts. "
            "Source: M_EXPENSIVE_STATEMENTS filtered for idle cursors."
        ),
        "data_source": "SAP Monitor HANA provider — long-idling cursors check",
        "time_column": "TimeGenerated",
        "sid_column": "sapsid_s",
        "key_columns": ["sapsid_s", "HOST_s", "APP_USER_s", "APP_SOURCE_s", "TIME_S_d", "STATEMENT_STRING_s"],
        "analysis_type": "hana_db",
        "columns": {
            "TimeGenerated": {"type": "datetime", "description": "UTC ingest timestamp. Use as primary time filter."},
            "Time_Generated_t": {"type": "datetime", "description": "Provider-side timestamp."},
            "START_TIME_t": {"type": "datetime", "description": "When the cursor/statement was opened."},
            "SNAPSHOT_TIME_t": {"type": "datetime", "description": "When this snapshot of open cursors was taken on HANA."},
            "SERVER_UTC_t": {"type": "datetime", "description": "HANA server UTC timestamp at collection."},
            "SERVER_LOCALTIME_t": {"type": "datetime", "description": "HANA server local time at collection."},
            "TIMESERIES_UTC_t": {"type": "datetime", "description": "UTC timestamp of this timeseries data point."},
            "HOST_s": {"type": "string", "description": "HANA host where the cursor is held."},
            "PORT_d": {"type": "real", "description": "Service port."},
            "SID_s": {"type": "string", "description": "SAP System ID from the HANA record. Prefer sapsid_s for filtering."},
            "CONN_ID_d": {"type": "real", "description": "Connection ID holding the cursor. Join to SapHana_BlockedTransactions_CL LOCK_OWNER_CONNECTION_ID_d to see if it is also blocking others."},
            "CONN_STATUS_s": {"type": "string", "description": "Connection status: 'IDLE', 'RUNNING', 'QUEUEING'. 'IDLE' with a long TIME_S_d is the classic leaked-cursor pattern."},
            "TIME_S_d": {"type": "real", "description": "Seconds the cursor has been idle/open. This is the duration metric for this table (there is no IDLE_TIME_d column)."},
            "STATEMENT_STRING_s": {"type": "string", "description": "SQL text of the statement holding the cursor. Primary field for identifying the offending application code."},
            "STATEMENT_STATUS_s": {"type": "string", "description": "Statement status (e.g. 'ACTIVE', 'SUSPENDED')."},
            "MVCC_TIMESTAMP_d": {"type": "real", "description": "MVCC snapshot timestamp pinned by this cursor. An old value blocks MVCC garbage collection — correlate with SapHana_Mvcc_CL NUM_VERSIONS."},
            "APP_USER_s": {"type": "string", "description": "Application user associated with the idle cursor."},
            "APP_SOURCE_s": {"type": "string", "description": "Application source/program that opened the cursor."},
            "APP_NAME_s": {"type": "string", "description": "Application name."},
            "APP_VERSION_s": {"type": "string", "description": "Application version."},
            "CLIENT_HOST_s": {"type": "string", "description": "Client host that opened the cursor."},
            "CLIENT_PID_d": {"type": "real", "description": "OS process ID on the client host. Use to pin the exact work process / application server process."},
            "sapsid_s": {"type": "string", "description": "SAP System ID. Use for filtering."},
            "PROVIDER_INSTANCE_s": {"type": "string", "description": "SAP Monitor provider instance name."},
        },
        "kql_hints": [
            "ALWAYS filter by sapsid_s: | where sapsid_s == '<sid>'",
            "Duration column is TIME_S_d (seconds) — there is no IDLE_TIME_d or STATEMENT_ID_d column on this table.",
            "Worst offenders: | summarize max(TIME_S_d) by APP_USER_s, APP_SOURCE_s, CLIENT_HOST_s, CONN_ID_d | top 20 by max_TIME_S_d desc",
            "Leaked-cursor pattern: | where CONN_STATUS_s == 'IDLE' and TIME_S_d > 3600",
            "Use STATEMENT_STRING_s to identify the application code; truncate with substring(STATEMENT_STRING_s, 0, 300) to save tokens.",
            "MVCC growth RCA: old MVCC_TIMESTAMP_d here explains rising NUM_VERSIONS in SapHana_Mvcc_CL.",
            "Correlate CONN_ID_d with SapHana_BlockedTransactions_CL.LOCK_OWNER_CONNECTION_ID_d to prove a cursor is causing lock waits.",
        ],
    },

    # -------------------------------------------------------------------------
    # Table 20 — SapHana_UncommittedWriteTransactions_CL
    # HANA uncommitted write transactions
    # -------------------------------------------------------------------------
    "SapHana_UncommittedWriteTransactions_CL": {
        "table_name": "SapHana_UncommittedWriteTransactions_CL",
        "domain": "hana_db",
        "description": (
            "SAP HANA uncommitted write transactions. Each row is a transaction that has "
            "performed write operations but has not yet committed. These block MVCC garbage "
            "collection and can cause memory growth. Source: M_TRANSACTIONS."
        ),
        "data_source": "SAP Monitor HANA provider — uncommitted write transactions",
        "time_column": "TimeGenerated",
        "sid_column": "sapsid_s",
        "key_columns": ["sapsid_s", "HOST_s", "CONN_ID_d", "TID_d", "STATUS_DETAILS_s", "TIME_S_d"],
        "analysis_type": "hana_db",
        "columns": {
            "TimeGenerated": {"type": "datetime", "description": "UTC ingest timestamp. Use as primary time filter."},
            "Time_Generated_t": {"type": "datetime", "description": "Provider-side timestamp."},
            "START_TIME_t": {"type": "datetime", "description": "Transaction start time."},
            "SNAPSHOT_TIME_t": {"type": "datetime", "description": "When this transaction snapshot was taken on HANA."},
            "SERVER_UTC_t": {"type": "datetime", "description": "HANA server UTC timestamp at collection."},
            "SERVER_LOCALTIME_t": {"type": "datetime", "description": "HANA server local time at collection."},
            "TIMESERIES_UTC_t": {"type": "datetime", "description": "UTC timestamp of this timeseries data point."},
            "HOST_s": {"type": "string", "description": "HANA host where the transaction is running."},
            "PORT_d": {"type": "real", "description": "Service port."},
            "SID_s": {"type": "string", "description": "SAP System ID from the HANA record. Prefer sapsid_s for filtering."},
            "CONN_ID_d": {"type": "real", "description": "Connection ID of the transaction."},
            "TID_d": {"type": "real", "description": "Transaction ID."},
            "UTID_d": {"type": "real", "description": "Update transaction ID — the write-transaction identifier that blocks MVCC garbage collection."},
            "STATUS_DETAILS_s": {"type": "string", "description": "Transaction status detail (e.g. 'ACTIVE', 'INACTIVE'). This is the status column on this table — there is NO TRANSACTION_STATUS_s column."},
            "TIME_S_d": {"type": "real", "description": "Seconds the transaction has been open without committing. Long values block MVCC cleanup."},
            "MVCC_TIMESTAMP_d": {"type": "real", "description": "MVCC snapshot timestamp pinned by this transaction. Oldest value across rows sets the MVCC garbage-collection horizon."},
            "OBJECT_ID_d": {"type": "real", "description": "HANA object ID being written to, when available."},
            "CLIENT_HOST_s": {"type": "string", "description": "Client host that initiated the transaction."},
            "CLIENT_PID_d": {"type": "real", "description": "OS process ID on the client host. Use to pin the exact SAP work process."},
            "sapsid_s": {"type": "string", "description": "SAP System ID. Use for filtering."},
            "PROVIDER_INSTANCE_s": {"type": "string", "description": "SAP Monitor provider instance name."},
        },
        "kql_hints": [
            "ALWAYS filter by sapsid_s: | where sapsid_s == '<sid>'",
            "Status column is STATUS_DETAILS_s — there is NO TRANSACTION_STATUS_s column on this table.",
            "Longest uncommitted writes: | summarize max(TIME_S_d) by CONN_ID_d, TID_d, CLIENT_HOST_s, CLIENT_PID_d | top 20 by max_TIME_S_d desc",
            "MVCC blocker: | summarize min(MVCC_TIMESTAMP_d) by bin(TimeGenerated, 15m) — the oldest pinned timestamp is what stops version cleanup.",
            "Correlate with SapHana_Mvcc_CL (NUM_VERSIONS) and SapHana_HighMemoryUsageService_CL to explain memory growth.",
            "CLIENT_PID_d + CLIENT_HOST_s map back to the SAP work process in SapNetweaver_ABAPGetWPTable_CL.",
        ],
    },

    # -------------------------------------------------------------------------
    # Table 21 — SapHana_LongRunningTransactions_CL
    # HANA long-running transactions
    # -------------------------------------------------------------------------
    "SapHana_LongRunningTransactions_CL": {
        "table_name": "SapHana_LongRunningTransactions_CL",
        "domain": "hana_db",
        "description": (
            "SAP HANA long-running transactions that exceed the configured duration threshold. "
            "Long-running transactions hold locks, consume memory, and block MVCC cleanup. "
            "Source: M_TRANSACTIONS filtered by duration."
        ),
        "data_source": "SAP Monitor HANA provider — long-running transactions",
        "time_column": "TimeGenerated",
        "sid_column": "sapsid_s",
        "key_columns": ["sapsid_s", "HOST_s", "CONNECTION_ID_d", "TRANSACTION_ID_d", "DURATION_d", "USER_NAME_s"],
        "analysis_type": "hana_db",
        "columns": {
            "TimeGenerated": {"type": "datetime", "description": "UTC ingest timestamp. Use as primary time filter."},
            "Time_Generated_t": {"type": "datetime", "description": "Provider-side timestamp."},
            "START_TIME_t": {"type": "datetime", "description": "Transaction start time."},
            "SNAPSHOT_TIME_t": {"type": "datetime", "description": "When this transaction snapshot was taken on HANA."},
            "SERVER_UTC_t": {"type": "datetime", "description": "HANA server UTC timestamp at collection."},
            "SERVER_LOCALTIME_t": {"type": "datetime", "description": "HANA server local time at collection."},
            "TIMESERIES_UTC_t": {"type": "datetime", "description": "UTC timestamp of this timeseries data point."},
            "HOST_s": {"type": "string", "description": "HANA host."},
            "PORT_d": {"type": "real", "description": "Service port."},
            "SID_s": {"type": "string", "description": "SAP System ID from the HANA record. Prefer sapsid_s for filtering."},
            "CONNECTION_ID_d": {"type": "real", "description": "Connection ID. NOTE: full name CONNECTION_ID_d on this table (NOT CONN_ID_d as on the cursor/uncommitted tables)."},
            "TRANSACTION_ID_d": {"type": "real", "description": "Transaction ID."},
            "UPDATE_TRANSACTION_ID_d": {"type": "real", "description": "Update (write) transaction ID. Non-zero means the transaction has written and is blocking MVCC cleanup."},
            "THREAD_ID_d": {"type": "real", "description": "HANA thread ID executing the transaction."},
            "THREAD_DETAIL_s": {"type": "string", "description": "What the thread is currently doing (SQL text / internal operation). Primary field for identifying what the transaction is stuck on."},
            "DURATION_d": {"type": "real", "description": "Transaction duration in seconds. This is the duration metric on this table."},
            "INDEX_s": {"type": "string", "description": "Row index within the collected snapshot. Not an SAP index name."},
            "AUTO_COMMIT_s": {"type": "string", "description": "Whether auto-commit is enabled for this session ('TRUE'/'FALSE'). 'FALSE' plus long DURATION_d = application forgot to commit."},
            "USER_NAME_s": {"type": "string", "description": "Database user executing the transaction (e.g. SAPABAP1)."},
            "APPLICATION_USER_NAME_s": {"type": "string", "description": "Application (SAP) user behind the DB session. Maps to the SAP user in ST22/SM21."},
            "CLIENT_HOST_s": {"type": "string", "description": "Client host."},
            "CLIENT_IP_s": {"type": "string", "description": "Client IP address."},
            "CLIENT_PID_d": {"type": "real", "description": "OS process ID on the client host. Use to pin the exact SAP work process."},
            "sapsid_s": {"type": "string", "description": "SAP System ID. Use for filtering."},
            "PROVIDER_INSTANCE_s": {"type": "string", "description": "SAP Monitor provider instance name."},
        },
        "kql_hints": [
            "ALWAYS filter by sapsid_s: | where sapsid_s == '<sid>'",
            "Column is CONNECTION_ID_d here (NOT CONN_ID_d) and DURATION_d (NOT TIME_S_d). There is NO TRANSACTION_STATUS_s column.",
            "Longest transactions: | summarize max(DURATION_d) by CONNECTION_ID_d, TRANSACTION_ID_d, USER_NAME_s, APPLICATION_USER_NAME_s | top 20 by max_DURATION_d desc",
            "Forgotten commits: | where AUTO_COMMIT_s == 'FALSE' and DURATION_d > 1800 and UPDATE_TRANSACTION_ID_d > 0",
            "Use THREAD_DETAIL_s to see what the transaction is executing; truncate with substring() to save tokens.",
            "Join CONNECTION_ID_d to SapHana_BlockedTransactions_CL.LOCK_OWNER_CONNECTION_ID_d to prove this transaction is the blocker.",
            "CLIENT_PID_d + CLIENT_HOST_s map back to SapNetweaver_ABAPGetWPTable_CL work processes.",
        ],
    },

    # -------------------------------------------------------------------------
    # Table 22 — SapHana_BlockedTransactions_CL
    # HANA blocked transactions (lock waits)
    # -------------------------------------------------------------------------
    "SapHana_BlockedTransactions_CL": {
        "table_name": "SapHana_BlockedTransactions_CL",
        "domain": "hana_db",
        "description": (
            "SAP HANA blocked transactions — transactions waiting for locks held by other "
            "transactions. Each row shows who is blocked and who is blocking. "
            "Use to identify lock contention chains that cause application hangs. "
            "Source: M_BLOCKED_TRANSACTIONS."
        ),
        "data_source": "SAP Monitor HANA provider — M_BLOCKED_TRANSACTIONS",
        "time_column": "TimeGenerated",
        "sid_column": "sapsid_s",
        "key_columns": [
            "sapsid_s", "HOST_s", "LOCK_TYPE_s", "LOCK_MODE_s",
            "BLOCKED_CONNECTION_ID_d", "LOCK_OWNER_CONNECTION_ID_d",
            "WAITING_SCHEMA_NAME_s", "WAITING_TABLE_NAME_s",
        ],
        "analysis_type": "hana_db",
        "columns": {
            "TimeGenerated": {"type": "datetime", "description": "UTC ingest timestamp. Use as primary time filter."},
            "Time_Generated_t": {"type": "datetime", "description": "Provider-side timestamp."},
            "BLOCKED_TIME_t": {"type": "datetime", "description": "Time when the blocking started. Derive wait duration as SERVER_UTC_t - BLOCKED_TIME_t (there is no duration column on this table)."},
            "SERVER_UTC_t": {"type": "datetime", "description": "HANA server UTC timestamp at collection."},
            "SERVER_LOCALTIME_t": {"type": "datetime", "description": "HANA server local time at collection."},
            "TIMESERIES_UTC_t": {"type": "datetime", "description": "UTC timestamp of this timeseries data point."},
            "HOST_s": {"type": "string", "description": "HANA host where the blocking occurs."},
            "PORT_d": {"type": "real", "description": "Service port."},
            "LOCK_TYPE_s": {"type": "string", "description": "Type of lock causing the block: RECORD, TABLE, OBJECT, METADATA."},
            "LOCK_MODE_s": {"type": "string", "description": "Lock mode requested/held (e.g. 'EXCLUSIVE', 'ROW EXCLUSIVE', 'INTENTIONAL EXCLUSIVE'). Determines how wide the blast radius is."},
            "BLOCKED_CONNECTION_ID_d": {"type": "real", "description": "Connection ID that is blocked (the victim waiting for the lock)."},
            "BLOCKED_TRANSACTION_ID_d": {"type": "real", "description": "Transaction ID of the blocked transaction."},
            "BLOCKED_UPDATE_TRANSACTION_ID_d": {"type": "real", "description": "Update transaction ID of the blocked transaction."},
            "LOCK_OWNER_CONNECTION_ID_d": {"type": "real", "description": "Connection ID that holds the lock (the blocker). ROOT CAUSE side of the chain."},
            "LOCK_OWNER_TRANSACTION_ID_d": {"type": "real", "description": "Transaction ID of the lock holder."},
            "LOCK_OWNER_UPDATE_TRANSACTION_ID_d": {"type": "real", "description": "Update transaction ID of the lock holder."},
            "WAITING_SCHEMA_NAME_s": {"type": "string", "description": "Schema of the object being waited on (e.g. 'SAPABAP1')."},
            "WAITING_TABLE_NAME_s": {"type": "string", "description": "Table being waited on. Primary field for identifying the contended object."},
            "WAITING_OBJECT_NAME_s": {"type": "string", "description": "Full name of the object being waited on."},
            "WAITING_OBJECT_TYPE_s": {"type": "string", "description": "Type of object being waited on (TABLE, VIEW, PROCEDURE, ...)."},
            "WAITING_RECORD_ID_s": {"type": "string", "description": "Record ID being waited on when LOCK_TYPE_s = 'RECORD'."},
            "sapsid_s": {"type": "string", "description": "SAP System ID. Use for filtering."},
            "PROVIDER_INSTANCE_s": {"type": "string", "description": "SAP Monitor provider instance name."},
        },
        "kql_hints": [
            "ALWAYS filter by sapsid_s: | where sapsid_s == '<sid>'",
            "Column names are the FULL forms: BLOCKED_CONNECTION_ID_d / LOCK_OWNER_CONNECTION_ID_d. There is NO BLOCKED_CONN_ID_d, BLOCKED_THREAD_ID_d or BLOCKED_DURATION_S_d column.",
            "Wait duration must be computed: | extend blocked_seconds = datetime_diff('second', SERVER_UTC_t, BLOCKED_TIME_t)",
            "Top contended objects: | summarize blocks = count() by WAITING_SCHEMA_NAME_s, WAITING_TABLE_NAME_s, LOCK_TYPE_s, LOCK_MODE_s | top 20 by blocks desc",
            "Find the root blocker: | summarize victims = dcount(BLOCKED_CONNECTION_ID_d) by LOCK_OWNER_CONNECTION_ID_d | top 10 by victims desc",
            "A blocker that never appears as BLOCKED_CONNECTION_ID_d is the head of the chain — look it up in SapHana_LongRunningTransactions_CL by CONNECTION_ID_d.",
            "Correlate with SapNetweaver_ShortDumps_CL TIME_OUT / DBIF_RSQL_SQL_ERROR dumps in the same window.",
        ],
    },

    # -------------------------------------------------------------------------
    # Table 23 — SapHana_IO_Savepoint_CL
    # HANA I/O savepoint statistics (no current data — schema from LA metadata)
    # -------------------------------------------------------------------------
    "SapHana_IO_Savepoint_CL": {
        "table_name": "SapHana_IO_Savepoint_CL",
        "domain": "hana_db",
        "description": (
            "SAP HANA I/O savepoint statistics. Each row is one savepoint operation "
            "with duration, I/O throughput, and volume details. Long savepoints (>300s) "
            "indicate disk I/O bottlenecks that can impact write performance."
        ),
        "data_source": "SAP Monitor HANA provider — M_SAVEPOINTS",
        "time_column": "TimeGenerated",
        "sid_column": "sapsid_s",
        "key_columns": ["sapsid_s", "HOST_s", "TOTAL_S_s", "CRIT_S_s", "BLK_S_s", "MB_PER_S_s", "SIZE_MB_s"],
        "analysis_type": "hana_db",
        "columns": {
            "TimeGenerated": {"type": "datetime", "description": "UTC ingest timestamp. Use as primary time filter."},
            "Time_Generated_t": {"type": "datetime", "description": "Provider-side timestamp."},
            "SERVER_UTC_t": {"type": "datetime", "description": "HANA server UTC timestamp at collection."},
            "TIMESERIES_UTC_t": {"type": "datetime", "description": "UTC timestamp of this timeseries data point."},
            "HOST_s": {"type": "string", "description": "HANA host where the savepoint ran."},
            "PORT_s": {"type": "string", "description": "Service port (as string)."},
            "START_TIME_s": {"type": "string", "description": "Savepoint start time (string, not datetime — do not use in KQL time filters)."},
            "END_TIME_s": {"type": "string", "description": "Savepoint end time (string)."},
            "TOTAL_S_s": {"type": "string", "description": "Total savepoint duration in seconds (string — cast with todouble()). >300s = investigate disk I/O. This replaces the non-existent DURATION_S_s."},
            "CRIT_S_s": {"type": "string", "description": "Critical (blocking) phase duration in seconds. This is the phase that stalls all writers — the most important savepoint metric."},
            "CRIT_PHASE_START_TIME_s": {"type": "string", "description": "Start time of the critical phase."},
            "BLK_S_s": {"type": "string", "description": "Blocking phase duration in seconds."},
            "BLK_PHASE_START_TIME_s": {"type": "string", "description": "Start time of the blocking phase."},
            "LOCK_S_s": {"type": "string", "description": "Time spent waiting for the savepoint lock, in seconds."},
            "MB_PER_S_s": {"type": "string", "description": "Write throughput during the savepoint in MB/s. Low value with high TOTAL_S_s = storage I/O bottleneck."},
            "SIZE_MB_s": {"type": "string", "description": "Data written during the savepoint in MB. Replaces the non-existent TOTAL_SIZE_MB_s."},
            "COUNT_s": {"type": "string", "description": "Number of pages/blocks written in the savepoint."},
            "RETRIES_s": {"type": "string", "description": "Number of savepoint retries. Non-zero indicates contention or I/O errors."},
            "RS_SIZE_PCT_s": {"type": "string", "description": "Row store size as a percentage of the savepoint payload."},
            "AGG_s": {"type": "string", "description": "Aggregation bucket for this row (e.g. hourly/daily rollup identifier)."},
            "I_s": {"type": "string", "description": "Row index within the collected snapshot."},
            "P_s": {"type": "string", "description": "Partition / priority indicator for the savepoint row."},
            "VERSION_s": {"type": "string", "description": "HANA version string reported with the savepoint record."},
            "sapsid_s": {"type": "string", "description": "SAP System ID. Use for filtering."},
            "PROVIDER_INSTANCE_s": {"type": "string", "description": "SAP Monitor provider instance name."},
        },
        "kql_hints": [
            "ALWAYS filter by sapsid_s: | where sapsid_s == '<sid>'",
            "ALL metric columns on this table are STRINGS (_s) — cast before comparing: | extend total_s = todouble(TOTAL_S_s), crit_s = todouble(CRIT_S_s)",
            "There is NO DURATION_S_s, TOTAL_SIZE_MB_s, CRITICAL_PHASE_DURATION_S_s, VOLUME_ID_s or PURPOSE_s column. Use TOTAL_S_s, SIZE_MB_s, CRIT_S_s instead.",
            "Long savepoints: | extend total_s = todouble(TOTAL_S_s) | where total_s > 300 | project TimeGenerated, HOST_s, TOTAL_S_s, CRIT_S_s, MB_PER_S_s",
            "Write stalls: high CRIT_S_s (critical phase) is what actually blocks application COMMITs — prioritise it over TOTAL_S_s.",
            "I/O bottleneck signature: low todouble(MB_PER_S_s) together with high todouble(TOTAL_S_s).",
            "Correlate with Prometheus_OSExporter_CL node_disk_io_time_seconds_total on the same host/time window.",
        ],
    },

    # -------------------------------------------------------------------------
    # Table 24 — SapHana_DeltaMerge_Count_CL
    # HANA delta merge operation counts (no current data — schema from LA metadata)
    # -------------------------------------------------------------------------
    "SapHana_DeltaMerge_Count_CL": {
        "table_name": "SapHana_DeltaMerge_Count_CL",
        "domain": "hana_db",
        "description": (
            "SAP HANA delta merge operation counts. Tracks the number and duration of "
            "delta merge operations per table. Failed or excessively long delta merges "
            "indicate resource issues (CPU, memory) that degrade column store performance."
        ),
        "data_source": "SAP Monitor HANA provider — M_DELTA_MERGE_STATISTICS",
        "time_column": "TimeGenerated",
        "sid_column": "sapsid_s",
        "key_columns": ["sapsid_s", "HOST_s", "SCHEMA_NAME_s", "TABLE_NAME_s", "COUNT_s", "DURATION_S_s", "LAST_ERROR_s"],
        "analysis_type": "hana_db",
        "columns": {
            "TimeGenerated": {"type": "datetime", "description": "UTC ingest timestamp. Use as primary time filter."},
            "Time_Generated_t": {"type": "datetime", "description": "Provider-side timestamp."},
            "SERVER_UTC_t": {"type": "datetime", "description": "HANA server UTC timestamp at collection."},
            "HOST_s": {"type": "string", "description": "HANA host."},
            "PORT_s": {"type": "string", "description": "Service port (as string)."},
            "START_TIME_s": {"type": "string", "description": "Merge start time (string, not datetime)."},
            "END_TIME_s": {"type": "string", "description": "Merge end time (string, not datetime)."},
            "COUNT_s": {"type": "string", "description": "Number of delta merge operations in the reporting period (string — cast with toint())."},
            "DURATION_S_s": {"type": "string", "description": "Total duration of merge operations in seconds (string — cast with todouble())."},
            "SCHEMA_NAME_s": {"type": "string", "description": "Schema of the merged table (e.g. 'SAPABAP1'). Required to uniquely identify the table."},
            "TABLE_NAME_s": {"type": "string", "description": "Table being merged."},
            "TYPE_s": {"type": "string", "description": "Merge type: 'AUTO' (automatic), 'HINT', 'SMART', 'FORCED', 'CRITICAL', 'MEMORY', 'RECLAIM'. Repeated 'CRITICAL'/'MEMORY' merges signal memory pressure."},
            "MOTIVATION_s": {"type": "string", "description": "Why the merge was triggered (e.g. 'AUTO', 'MERGEDOG', 'CRITICAL'). Key field for explaining unexpected merge load."},
            "LAST_ERROR_s": {"type": "string", "description": "HANA error code of the last failed merge. Non-zero / non-empty = merges are FAILING and the column store is degrading."},
            "ROWS_MERGED_s": {"type": "string", "description": "Number of rows moved from delta to main storage (string — cast with tolong())."},
            "sapsid_s": {"type": "string", "description": "SAP System ID. Use for filtering."},
            "PROVIDER_INSTANCE_s": {"type": "string", "description": "SAP Monitor provider instance name."},
        },
        "kql_hints": [
            "ALWAYS filter by sapsid_s: | where sapsid_s == '<sid>'",
            "Metric columns are STRINGS (_s) — cast before comparing: | extend dur = todouble(DURATION_S_s), cnt = toint(COUNT_s)",
            "Failed merges (highest priority): | where isnotempty(LAST_ERROR_s) and LAST_ERROR_s != '0' | summarize count() by SCHEMA_NAME_s, TABLE_NAME_s, LAST_ERROR_s",
            "Slowest merges: | extend dur = todouble(DURATION_S_s) | top 20 by dur desc | project TimeGenerated, SCHEMA_NAME_s, TABLE_NAME_s, DURATION_S_s, ROWS_MERGED_s",
            "Memory-pressure signature: | where TYPE_s in ('CRITICAL','MEMORY') or MOTIVATION_s == 'CRITICAL' — correlate with SapHana_HighMemoryUsageService_CL.",
            "Always group by SCHEMA_NAME_s AND TABLE_NAME_s — table names are not unique across schemas.",
        ],
    },

    # -------------------------------------------------------------------------
    # Table 25 — SapHana_InternodeSendThroughput_CL
    # HANA inter-node communication throughput (no current data — schema from LA metadata)
    # -------------------------------------------------------------------------
    "SapHana_InternodeSendThroughput_CL": {
        "table_name": "SapHana_InternodeSendThroughput_CL",
        "domain": "hana_db",
        "description": (
            "SAP HANA inter-node send throughput. Monitors network communication between "
            "HANA scale-out nodes. Low throughput or high latency between nodes impacts "
            "distributed query performance and replication."
        ),
        "data_source": "SAP Monitor HANA provider — inter-node throughput",
        "time_column": "TimeGenerated",
        "sid_column": "sapsid_s",
        "key_columns": ["sapsid_s", "SENDER_s", "RECEIVER_s", "THROUGHPUT_MBPS_d", "DURATION_SECONDS_d", "SIZE_MB_d"],
        "analysis_type": "hana_db",
        "columns": {
            "TimeGenerated": {"type": "datetime", "description": "UTC ingest timestamp. Use as primary time filter."},
            "Time_Generated_t": {"type": "datetime", "description": "Provider-side timestamp."},
            "SERVER_UTC_t": {"type": "datetime", "description": "HANA server UTC timestamp at collection."},
            "SENDER_s": {"type": "string", "description": "Sending HANA node hostname."},
            "RECEIVER_s": {"type": "string", "description": "Receiving HANA node hostname."},
            "THROUGHPUT_MBPS_d": {"type": "real", "description": "Measured throughput in MB/s between the two nodes. Low values on a 10GbE interconnect indicate a network problem."},
            "DURATION_SECONDS_d": {"type": "real", "description": "Transfer duration in SECONDS (not milliseconds)."},
            "SIZE_MB_d": {"type": "real", "description": "Data transferred in MB."},
            "sapsid_s": {"type": "string", "description": "SAP System ID. Use for filtering."},
            "PROVIDER_INSTANCE_s": {"type": "string", "description": "SAP Monitor provider instance name."},
        },
        "kql_hints": [
            "ALWAYS filter by sapsid_s: | where sapsid_s == '<sid>'",
            "Columns are THROUGHPUT_MBPS_d / DURATION_SECONDS_d / SIZE_MB_d — there are NO SEND_* prefixed columns on this table.",
            "Only populated for HANA scale-out and System Replication landscapes; single-node systems return no rows.",
            "Slowest links: | summarize avg(THROUGHPUT_MBPS_d), min(THROUGHPUT_MBPS_d) by SENDER_s, RECEIVER_s | order by avg_THROUGHPUT_MBPS_d asc",
            "Trend a link: | where SENDER_s == '<host>' | summarize avg(THROUGHPUT_MBPS_d) by bin(TimeGenerated, 15m)",
            "Low throughput here explains rising TIME_DIFF_SECONDS_d in SapHana_SystemReplication_CL — check both together for replication lag RCA.",
            "Correlate with Prometheus_OSExporter_CL node_network_transmit_bytes_total on the sender host.",
        ],
    },

}
