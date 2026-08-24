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
        "key_columns": ["SERVICE_NAME_s", "HOST_s", "PORT_d", "PERCENTAGE_HEAP_USED_MEMORY_d", "PERCENTAGE_USED_MEMORY_d"],
        "analysis_type": "hana_db",
        "columns": {
            "TimeGenerated": {"type": "datetime", "description": "UTC ingest timestamp."},
            "SERVER_UTC_t": {"type": "datetime", "description": "UTC timestamp from the HANA server."},
            "SNAPSHOT_TIME_t": {"type": "datetime", "description": "Exact timestamp when the memory snapshot was taken on HANA."},
            "HOST_s": {"type": "string", "description": "Hostname of the HANA node."},
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
            "MEMORY_SIZE_d": {"type": "real", "description": "Total physical memory of the host in MB (system-wide)."},
            "PERCENTAGE_USED_MEMORY_d": {"type": "real", "description": "% of ALLOCATION_LIMIT used. Values above 85% indicate high memory pressure."},
            "PERCENTAGE_HEAP_USED_MEMORY_d": {"type": "real", "description": "% of allocated heap that is actively in use. High = potential memory leak or load spike."},
            "sapsid_s": {"type": "string", "description": "SAP System ID. Use for filtering."},
            "PROVIDER_INSTANCE_s": {"type": "string", "description": "SAP Monitor provider instance name."},
        },
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
    },

}
