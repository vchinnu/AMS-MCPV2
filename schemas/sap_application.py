"""SAP Application layer schemas — ST22 Short Dumps, SM37 Batch Jobs, SM21 System Logs.

Add further SAP application tables here (e.g. SapNetweaver_GetSystemInstanceList_CL,
SapNetweaver_GetProcessList_CL) as schema CSVs become available.

HOW TO ADD A TABLE
──────────────────
1. Add a new entry to SCHEMAS below following the same structure.
2. Restart the MCP server — no re-registration needed if tool names haven't changed.
"""
from __future__ import annotations

SCHEMAS: dict[str, dict] = {

    # ──────────────────────────────────────────────────────────────────────────
    # Table 1 — SapNetweaver_ShortDumps_CL  (ST22 ABAP Short Dumps)
    # Schema source: SchemaforMCP-Details.csv
    # ──────────────────────────────────────────────────────────────────────────
    "SapNetweaver_ShortDumps_CL": {
        "table_name": "SapNetweaver_ShortDumps_CL",
        "domain": "sap_application",
        "description": (
            "ST22 ABAP Short Dumps — runtime error records extracted from SAP via "
            "RFC module /SDF/GET_DUMP_LOG. Each row represents one ABAP program crash."
        ),
        "usage_guidance": (
            "Use this table FIRST for short dump analysis. It provides one row per dump with "
            "the error type, program, user, host, and short text — ideal for counting errors, "
            "identifying patterns, and determining which error types dominate. "
            "After identifying the dominant error types here, query SapNetweaver_ShortDumps_SNAPFulldump_CL "
            "for section-level detail (call stack, source code, RFC context, variable values) "
            "to determine the precise root cause."
        ),
        "related_tables": [
            {
                "table": "SapNetweaver_ShortDumps_SNAPFulldump_CL",
                "relationship": "detail",
                "join_hint": (
                    "Correlate using Runtime_Error_s + time window + E2E_USER_s + E2E_HOST_s. "
                    "FULL_SNAP has correlation_id_g for grouping sections of a single dump."
                ),
            }
        ],
        "data_source": "SAP RFC /SDF/GET_DUMP_LOG",
        # ⚠ CONFIRM NEEDED: CSV says 'serverTimestamp_t'; agent documentation says 'timestamp_t'.
        # Both may exist in the table (serverTimestamp_t = collection time, timestamp_t = SAP event time).
        # Update this after confirming against your actual workspace.
        "time_column": "serverTimestamp_t",
        "sid_column": "SID_s",
        "key_columns": [
            "Runtime_Error_s",
            "Error_Short_Text_s",
            "Program_s",
            "E2E_USER_s",
            "E2E_HOST_s",
        ],
        "analysis_type": "short_dumps",
        "columns": {
            "Application_Componen_s": {
                "type": "string",
                "description": (
                    "High-level SAP functional area where the error occurred "
                    "(e.g., FI, MM, SD). Categorises the error by business domain. "
                    "Note: column name ends with '_s' and is intentionally truncated (no trailing 't')."
                ),
            },
            "Component_s": {
                "type": "string",
                "description": (
                    "SAP technical component in the official SAP component hierarchy "
                    "(e.g., LO-VCH, PPM-CF, BC-CST-EQ). More specific sub-classification "
                    "than Application_Componen_s. Used in OSS support notes."
                ),
            },
            "Development_Class_s": {
                "type": "string",
                "description": (
                    "ABAP package (development class) — technical grouping of the object "
                    "in the SAP repository (e.g., SENQ, INM_CPPM, VCH_HL_CORE). "
                    "Indicates code ownership and transport layer."
                ),
            },
            "E2E_DATE_s": {
                "type": "string",
                "description": (
                    "Date when the dump occurred in the SAP system (SAP date string format YYYYMMDD). "
                    "Pair with E2E_TIME_s to reconstruct the exact SAP system event time."
                ),
            },
            "E2E_HOST_s": {
                "type": "string",
                "description": (
                    "Server/host name where the ABAP dump was triggered. "
                    "Use to identify which application server is experiencing errors."
                ),
            },
            "E2E_SEVERITY_s": {
                "type": "string",
                "description": (
                    "Error severity indicator. Known values: "
                    "'1' = Very High Priority, '2' = High Priority."
                ),
            },
            "E2E_TIME_s": {
                "type": "string",
                "description": (
                    "Time when the dump occurred in the SAP system (string format HHMMSS). "
                    "Pair with E2E_DATE_s. Not a datetime — do not use for KQL time filters."
                ),
            },
            "E2E_USER_s": {
                "type": "string",
                "description": (
                    "SAP user ID that was active when the dump occurred. "
                    "For background jobs this is the job step user (technical/batch user). "
                    "Key for identifying whether a specific user or job is causing failures."
                ),
            },
            "Error_Short_Text_s": {
                "type": "string",
                "description": (
                    "Brief human-readable description of the error, as shown in ST22 transaction. "
                    "Provides immediate context on what failed. Key field for initial diagnosis."
                ),
            },
            "Exception_s": {
                "type": "string",
                "description": (
                    "ABAP exception class or name that was raised (for object-oriented exceptions). "
                    "E.g., CX_SY_NO_HANDLER, CX_BSEG_LOCKED. "
                    "Empty for classic runtime errors like TIME_OUT or RFC failures."
                ),
            },
            "Program_s": {
                "type": "string",
                "description": (
                    "ABAP program or report in which the dump occurred. "
                    "Examples: SAPLSENA, SAPLRPM_FICO_INT_DATA, CL_VCH_HL_ENGINE_FACTORY======CP. "
                    "Primary field for identifying which code is failing."
                ),
            },
            "Runtime_Error_s": {
                "type": "string",
                "description": (
                    "ABAP runtime error ID — matches the ST22 dump category exactly. "
                    "Examples: UNCAUGHT_EXCEPTION, TIME_OUT, CALL_FUNCTION_OPEN_ERROR, "
                    "TSV_TNEW_PAGE_ALLOC_FAILED, DBIF_RSQL_SQL_ERROR. "
                    "PRIMARY field for root cause classification — use this to determine error category."
                ),
            },
            "serverTimestamp_t": {
                "type": "datetime",
                "description": (
                    "UTC timestamp of the dump (as recorded by the SAP Monitor collection agent). "
                    "Use for KQL time range filters. "
                    "⚠ CONFIRM: CSV lists this as the time column. Agent docs reference 'timestamp_t' — "
                    "verify which is correct in your workspace."
                ),
            },
            "Transaction_ID_s": {
                "type": "string",
                "description": (
                    "Unique identifier (GUID-like or LUW ID) of the transaction/session "
                    "during which the error occurred. Technical correlation identifier "
                    "for cross-system tracing."
                ),
            },
            "SID_s": {
                "type": "string",
                "description": (
                    "SAP System ID (e.g., 'CHA', 'PRD', 'QAS'). "
                    "ALWAYS include this filter: | where SID_s == '<sid>'"
                ),
            },
            "hostname_s": {
                "type": "string",
                "description": (
                    "Application server hostname. "
                    "Cross-reference with SysLogs and OS metrics tables."
                ),
            },
            "instanceNr_s": {
                "type": "string",
                "description": (
                    "SAP instance number (e.g., '00', '01'). "
                    "Cross-reference with availability tables."
                ),
            },
            "client_s": {
                "type": "string",
                "description": "SAP client number (e.g., '100', '300').",
            },
        },
        "kql_hints": [
            "ALWAYS filter by the sid_column shown in this schema (SID_s for this table): | where SID_s == '<sid>'",
            "Use the time_column shown in this schema (serverTimestamp_t for this table): | where serverTimestamp_t > ago(4h)",
            "Summarize by Runtime_Error_s (dominant error category), Program_s (failing ABAP programs), E2E_USER_s (user/batch account), and E2E_HOST_s (app server) — run as a single summarize count() by these four columns to get the full failure breakdown in one query.",
            "Use bin(serverTimestamp_t, 5m) to detect when dumps started and if volume is increasing.",
            "Runtime_Error_s starting with 'MEMORY_' or 'SYSTEM_NO_' indicate resource pressure.",
            "Runtime_Error_s 'DBIF_*' or 'DBSQL_*' indicate database errors.",
            "Runtime_Error_s 'CALL_FUNCTION_*' indicate RFC communication failures.",
            "Correlate Program_s with batch job step programs when investigating job failures.",
        ],
    },

    # ──────────────────────────────────────────────────────────────────────────
    # Table 2 — SapNetweaver_BatchJobs_CL  (SM37 Batch Job Monitor)
    # Schema source: SchemaforMCP-Details.csv
    # ──────────────────────────────────────────────────────────────────────────
    "SapNetweaver_BatchJobs_CL": {
        "table_name": "SapNetweaver_BatchJobs_CL",
        "domain": "sap_application",
        "description": (
            "SM37 Batch Job Monitor — background job scheduling, status, and execution records. "
            "Each row represents one job instance. STATUS_s='A' (Cancelled) is the primary "
            "failure indicator for RCA."
        ),
        "data_source": "SAP RFC BAPI_XBP_JOB_SELECT",
        "time_column": "serverTimestamp_t",
        "sid_column": "SID_s",
        "key_columns": [
            "JOBNAME_s",
            "STATUS_s",
            "REAXSERVER_s",
            "SDLUNAME_s",
            "STRTDATE_s",
            "STRTTIME_s",
        ],
        "analysis_type": "batch_jobs",
        "columns": {
            "AUTHCKMAN_s": {
                "type": "string",
                "description": "Logical SAP system client where the background job is defined/executed.",
            },
            "ENDDATE_s": {
                "type": "string",
                "description": "Actual date when the job execution finished (format YYYYMMDD).",
            },
            "ENDTIME_s": {
                "type": "string",
                "description": (
                    "Actual time when job execution finished (format HHMMSS). "
                    "Job duration = ENDTIME_s minus STRTTIME_s."
                ),
            },
            "EVENTID_s": {
                "type": "string",
                "description": "Event name that can trigger job execution (event-driven scheduling).",
            },
            "EVENTPARM_s": {
                "type": "string",
                "description": "Additional parameter associated with the triggering event.",
            },
            "REAXSERVER_s": {
                "type": "string",
                "description": (
                    "Application server where the job step was actually executed "
                    "(also the requested target server). "
                    "Use to identify if failures are concentrated on a specific app server."
                ),
            },
            "JOBCLASS_s": {
                "type": "string",
                "description": "Job priority class: A = High, B = Medium, C = Low.",
            },
            "JOBCOUNT_s": {
                "type": "string",
                "description": "Unique technical identifier for this specific job run (job instance).",
            },
            "JOBNAME_s": {
                "type": "string",
                "description": "Name of the background job as defined in SM36. Primary grouping key.",
            },
            "LASTCHDATE_s": {
                "type": "string",
                "description": "Date when the job definition was last changed (YYYYMMDD).",
            },
            "LASTCHNAME_s": {
                "type": "string",
                "description": "User who last modified the job definition.",
            },
            "LASTCHTIME_s": {
                "type": "string",
                "description": "Time when the job definition was last changed (HHMMSS).",
            },
            "LASTSTRTDT_s": {
                "type": "string",
                "description": "Start date of the previous execution of this job (YYYYMMDD).",
            },
            "LASTSTRTTM_s": {
                "type": "string",
                "description": "Start time of the previous execution of this job (HHMMSS).",
            },
            "PERIODIC_s": {
                "type": "string",
                "description": "Indicator if the job is periodic/recurring. X = Yes, blank = one-time.",
            },
            "RELDATE_s": {
                "type": "string",
                "description": "Date when the job was released (made ready for execution, YYYYMMDD).",
            },
            "RELTIME_s": {
                "type": "string",
                "description": "Time when the job was released (HHMMSS).",
            },
            "RELUNAME_s": {
                "type": "string",
                "description": "User who released the job. Filter here to find jobs released by a specific user.",
            },
            "SDLDATE_s": {
                "type": "string",
                "description": "Date when the job was scheduled/defined (YYYYMMDD).",
            },
            "SDLSTRTDT_s": {
                "type": "string",
                "description": "Planned start date of the job (YYYYMMDD).",
            },
            "SDLSTRTTM_s": {
                "type": "string",
                "description": (
                    "Planned start time of the job (HHMMSS). "
                    "Start delay = STRTTIME_s minus SDLSTRTTM_s."
                ),
            },
            "SDLTIME_s": {
                "type": "string",
                "description": "Time when the job was scheduled (HHMMSS).",
            },
            "SDLUNAME_s": {
                "type": "string",
                "description": "User who scheduled the job. Use to filter jobs owned by a specific user.",
            },
            "STATUS_s": {
                "type": "string",
                "description": (
                    "Current job status. Primary RCA field. Values: "
                    "F=Finished (success), A=Cancelled (failure — use for RCA), "
                    "Z=Active (running), S=Released (waiting), "
                    "Y=Ready (waiting for WP), P=Scheduled (not yet released), "
                    "G=Released with restrictions."
                ),
            },
            "STEPCOUNT_d": {
                "type": "real",
                "description": "Number of steps or specific step number within the job.",
            },
            "STRTDATE_s": {
                "type": "string",
                "description": "Actual start date of job execution (YYYYMMDD).",
            },
            "STRTTIME_s": {
                "type": "string",
                "description": (
                    "Actual start time of job execution (HHMMSS). "
                    "Start delay = STRTTIME_s minus SDLSTRTTM_s."
                ),
            },
            "WPNUMBER_d": {
                "type": "real",
                "description": "Work process number that executed the job step.",
            },
            "WPPROCID_d": {
                "type": "real",
                "description": "Internal/OS-level process identifier of the executing work process.",
            },
            "SID_s": {
                "type": "string",
                "description": "SAP System ID. ALWAYS filter: | where SID_s == '<sid>'",
            },
            "sapsid_s": {
                "type": "string",
                "description": "Alternate SAP SID column (some workspaces use this instead of SID_s).",
            },
            "hostname_s": {
                "type": "string",
                "description": "Application server hostname.",
            },
            "instanceNr_s": {
                "type": "string",
                "description": "SAP instance number.",
            },
            "client_s": {
                "type": "string",
                "description": "SAP client number.",
            },
            "serverTimestamp_t": {
                "type": "datetime",
                "description": "UTC collection timestamp. Use for KQL time filters.",
            },
        },
        "kql_hints": [
            "ALWAYS filter by the sid_column shown in this schema (SID_s for this table): | where SID_s == '<sid>'",
            "Use the time_column shown in this schema (serverTimestamp_t for this table): | where serverTimestamp_t > ago(4h)",
            "CASE SENSITIVITY: KQL column names are case-sensitive. In THIS table use UPPERCASE columns: JOBNAME_s, STATUS_s, JOBCLASS_s, REAXSERVER_s, SDLUNAME_s, RELUNAME_s. Do NOT use lowercase (jobname_s is WRONG for this table — that belongs to SapNetweaver_BatchJobLog_CL).",
            "For failure analysis, filter STATUS_s == 'A' (Cancelled) — primary failure indicator.",
            "Summarize by JOBNAME_s and REAXSERVER_s — run as a single summarize count() by JOBNAME_s, REAXSERVER_s to find which jobs fail most and whether failures are concentrated on one app server.",
            "Compute start delay: STRTTIME_s minus SDLSTRTTM_s (both HHMMSS strings — convert before arithmetic). A large delay indicates resource crunch in batch/background work processes.",
            "Compute duration: ENDTIME_s minus STRTTIME_s. Longer duration than previous runs indicates investigation needed — OS resource pressure or large data volume in the job.",
            "Filter by SDLUNAME_s or RELUNAME_s to find jobs belonging to a specific user.",
            "JOBCLASS_s='A' jobs are high-priority — their failure has most business impact.",
            "Crossref JOBNAME_s with ST22 Program_s — map by name similarity and matching failure timestamp, not exact name match.",
            "Crossref SM21 logs for Msg_area_Msd_Id_s='EMF' (Job step logon failure) or 'EME' (Job detail) around the same time as job failures.",
            "Crossref SM21 logs for Description_s containing 'cancel', 'error', or 'shortdump' around the same time as job failures.",
            "Use bin(serverTimestamp_t, 5m) to detect sudden spikes in job cancellations.",
        ],
    },

    # ──────────────────────────────────────────────────────────────────────────
    # Table 3 — SapNetweaver_SysLogs_CL  (SM21 System Log)
    # Schema source: SchemaforMCP-Details.csv
    # ──────────────────────────────────────────────────────────────────────────
    "SapNetweaver_SysLogs_CL": {
        "table_name": "SapNetweaver_SysLogs_CL",
        "domain": "sap_application",
        "description": (
            "SM21 System Log — SAP system log entries extracted via RFC /SDF/GET_SYS_LOG. "
            "Contains errors, warnings, and informational events from the SAP kernel and ABAP runtime. "
            "Filter on E2E_SEVERITY_s '1' or '2' for critical events."
        ),
        "data_source": "SAP RFC /SDF/GET_SYS_LOG",
        "time_column": "TimeGenerated",
        "sid_column": "SID_s",
        "key_columns": [
            "E2E_SEVERITY_s",
            "Msg_area_Msd_Id_s",
            "Description_s",
            "E2E_USER_s",
            "E2E_HOST_s",
            "Program_s",
        ],
        "analysis_type": "system_logs",
        "columns": {
            "Application_Comp_s": {
                "type": "string",
                "description": "Business-friendly application component description (e.g., FI, MM, SD).",
            },
            "Component_s": {
                "type": "string",
                "description": "SAP technical component classification (e.g., BC-CST). Sub-area within the application component.",
            },
            "Description_s": {
                "type": "string",
                "description": (
                    "Detailed error/log message text. The actual system log message content. "
                    "Key for understanding what happened — search this for keywords like 'cancel', 'error', 'dump'."
                ),
            },
            "Development_Class_s": {
                "type": "string",
                "description": "ABAP package associated with the logged event (may be blank).",
            },
            "Development_Unit_s": {
                "type": "string",
                "description": "SAP software component (e.g., SAP_BASIS). Development unit that owns the code.",
            },
            "E2E_DATE_s": {
                "type": "string",
                "description": "Date when the log/event occurred in the SAP system (format YYYYMMDD).",
            },
            "E2E_HOST_s": {
                "type": "string",
                "description": "Application server/host where the event occurred. Use to isolate host-specific issues.",
            },
            "E2E_SEVERITY_s": {
                "type": "string",
                "description": (
                    "Severity indicator. Use ONLY these values for filtering: "
                    "'1' = Very High Priority (critical), '2' = High Priority. "
                    "Do NOT filter on text labels — only numeric strings are populated."
                ),
            },
            "E2E_TIME_s": {
                "type": "string",
                "description": "Time when log/event occurred in SAP system (format HHMMSS). Not a datetime — do not use for KQL time filters.",
            },
            "E2E_USER_s": {
                "type": "string",
                "description": "SAP user who triggered the event. Useful for correlating with dump users.",
            },
            "Msg_area_Msd_Id_s": {
                "type": "string",
                "description": (
                    "Message class and number identifier — SAP SM21 message area ID. "
                    "Key values: AB0=ABAP error reported, AB1=Short dump created, "
                    "EMF=Job step logon failed, D01=Transaction cancelled, "
                    "Q0I=OS call failed, Q04=User connection lost, EME=Job detail."
                ),
            },
            "Problem_Class_s": {
                "type": "string",
                "description": "Category of problem (e.g., SAP Web AS Problem, Database, Security, Performance).",
            },
            "Program_s": {
                "type": "string",
                "description": "ABAP program where the issue occurred. Correlate with ST22 Program_s.",
            },
            "SID_s": {
                "type": "string",
                "description": "SAP System ID. ALWAYS filter: | where SID_s == '<sid>'",
            },
            "Transaction_s": {
                "type": "string",
                "description": "SAP transaction code in context (if available).",
            },
            "TimeGenerated": {
                "type": "datetime",
                "description": (
                    "Log Analytics data ingestion timestamp (UTC). "
                    "USE THIS for KQL time filters: | where TimeGenerated > ago(4h). "
                    "Note: E2E_DATE_s + E2E_TIME_s hold the actual SAP system event time."
                ),
            },
        },
        "kql_hints": [
            "ALWAYS filter by the sid_column shown in this schema (SID_s for this table): | where SID_s == '<sid>'",
            "Use the time_column shown in this schema (TimeGenerated for this table): | where TimeGenerated > ago(4h)",
            "E2E_DATE_s + E2E_TIME_s are the actual SAP event times — use for display/correlation, not for KQL time filters.",
            "Filter E2E_SEVERITY_s in ('1', '2') to focus on critical and high priority entries only.",
            "Summarize by Msg_area_Msd_Id_s, E2E_HOST_s, and Description_s — run as a single summarize count() by these three columns to identify dominant message types, the most affected app server, and the most repeated error messages in one query.",
            "Search Description_s for keywords like 'cancel', 'dump', 'error' to find relevant logs.",
            "Correlate E2E_USER_s with dump ST22 users to identify if specific users/jobs are causing issues.",
            "AB0 and AB1 in Msg_area_Msd_Id_s confirm ABAP short dumps — cross-reference with ST22.",
            "EMF = 'Logon of Job Step User Failed' — indicates batch user authorization or lock issue.",
            "D01 = 'Transaction cancelled' — often paired with a dump; note the user and client.",
            "Q0I = OS call recv failed — indicates network disconnect or OS-level issue.",
            "bin(TimeGenerated, 5m) timeline reveals when errors started spiking.",
        ],
    },

    # ──────────────────────────────────────────────────────────────────────────
    # Table 4 — SapNetweaver_GetSystemInstanceList_CL  (SAP System Availability)
    # Schema source: SchemaforMCP-Details.csv
    # ──────────────────────────────────────────────────────────────────────────
    "SapNetweaver_GetSystemInstanceList_CL": {
        "table_name": "SapNetweaver_GetSystemInstanceList_CL",
        "domain": "sap_application",
        "description": (
            "SAP system availability — one row per SAP instance per collection cycle. "
            "Shows running/degraded/down status for every instance (ASCS, app servers, "
            "web dispatcher, enqueue replication). Primary table for checking whether the "
            "SAP system itself is up before investigating application errors."
        ),
        "data_source": "SAP SAPControl API (GetSystemInstanceList)",
        "time_column": "serverTimestamp_t",
        "sid_column": "SID_s",
        "analysis_type": "SAP_system_availability",
        "key_columns": ["SID_s", "hostname_s", "instanceNr_d", "features_s", "dispstatus_s", "serverTimestamp_t"],
        "columns": {
            "SID_s": {
                "type": "string",
                "description": "SAP System ID. ALWAYS filter: | where SID_s == '<sid>'",
            },
            "hostname_s": {
                "type": "string",
                "description": "SAP server hostname.",
            },
            "instanceNr_d": {
                "type": "real",
                "description": "SAP instance number (numeric).",
            },
            "features_s": {
                "type": "string",
                "description": (
                    "Instance role/features string. Examples: "
                    "'GATEWAY|MESSAGESERVER|ENQUE' = ASCS instance; "
                    "'ABAP|GATEWAY|ICMAN|IGS' = Application server; "
                    "'WEBDISP' = Web Dispatcher; "
                    "'ENQREP' = Enqueue Replication Server."
                ),
            },
            "dispstatus_s": {
                "type": "string",
                "description": (
                    "SAP instance status from SAPControl. "
                    "SAPControl-GREEN = healthy; SAPControl-RED = error/down; "
                    "SAPControl-YELLOW = degraded/warning; SAPControl-GRAY = offline/unreachable."
                ),
            },
            "startPriority_s": {
                "type": "string",
                "description": "Startup priority (lower number = started first).",
            },
            "httpPort_d": {"type": "real", "description": "HTTP port of the instance."},
            "httpsPort_d": {"type": "real", "description": "HTTPS port of the instance."},
            "serverTimestamp_t": {
                "type": "datetime",
                "description": "Collection timestamp — use for KQL time filters.",
            },
        },
        "kql_hints": [
            "ALWAYS filter by the sid_column shown in this schema (SID_s for this table): | where SID_s == '<sid>'",
            "Use the time_column shown in this schema (serverTimestamp_t for this table) for time filters.",
            "Filter dispstatus_s != 'SAPControl-GREEN' to find unhealthy instances.",
            "Use features_s to identify which instance type is affected — ASCS down is critical.",
            "Summarize count() by hostname_s, dispstatus_s to get a health overview.",
            "Check the most recent records per host: | summarize arg_max(serverTimestamp_t, *) by hostname_s",
        ],
    },

    # ──────────────────────────────────────────────────────────────────────────
    # Table 5 — SapNetweaver_GetProcessList_CL  (SAP Process Status)
    # Schema source: SchemaforMCP-Details.csv
    # ──────────────────────────────────────────────────────────────────────────
    "SapNetweaver_GetProcessList_CL": {
        "table_name": "SapNetweaver_GetProcessList_CL",
        "domain": "sap_application",
        "description": (
            "SAP process-level health — one row per OS process per collection cycle. "
            "Shows running/stopped status for each SAP process (Dispatcher, Gateway, ICM, etc.) "
            "per application server instance. Use to confirm whether a specific SAP process "
            "is up after an availability alarm."
        ),
        "data_source": "SAP SAPControl API (GetProcessList)",
        "time_column": "timestamp_t",
        "sid_column": "SID_s",
        "analysis_type": "SAP_Process_Availability",
        "key_columns": ["SID_s", "hostname_s", "name_s", "dispstatus_s", "textstatus_s"],
        "columns": {
            "SID_s": {
                "type": "string",
                "description": "SAP System ID. ALWAYS filter: | where SID_s == '<sid>'",
            },
            "hostname_s": {"type": "string", "description": "Application server hostname."},
            "instanceNr_d": {"type": "real", "description": "SAP instance number."},
            "name_s": {
                "type": "string",
                "description": "Technical OS-level process name (e.g. disp+work, gwrd, icman).",
            },
            "description_s": {
                "type": "string",
                "description": "Human-readable process name (e.g. Dispatcher, Gateway, ICM).",
            },
            "dispstatus_s": {
                "type": "string",
                "description": "SAPControl status: GREEN = healthy, YELLOW = warning, RED = critical.",
            },
            "textstatus_s": {
                "type": "string",
                "description": "Textual status of the process (e.g. Running, Stopped).",
            },
            "pid_d": {"type": "real", "description": "OS-level Process ID (PID)."},
            "elapsedtime_s": {
                "type": "string",
                "description": "Total runtime since process last started (hours:minutes:seconds).",
            },
            "starttime_s": {
                "type": "string",
                "description": "Timestamp when the process was last started.",
            },
            "sapsid_s": {"type": "string", "description": "SAP System ID (alternate field)."},
            "timestamp_t": {
                "type": "datetime",
                "description": "Collection timestamp in UTC — use for KQL time filters.",
            },
        },
        "kql_hints": [
            "ALWAYS filter by the sid_column shown in this schema (SID_s for this table): | where SID_s == '<sid>'",
            "Use the time_column shown in this schema (timestamp_t for this table) for time filters.",
            "Filter dispstatus_s != 'GREEN' or textstatus_s == 'Stopped' to find unhealthy processes.",
            "Summarize count() by hostname_s, name_s, textstatus_s to see process health per server.",
            "Check the most recent record per process per host: | summarize arg_max(timestamp_t, *) by hostname_s, name_s",
            "Cross-reference with GetSystemInstanceList_CL — a RED instance there will show stopped processes here.",
        ],
    },

    # ──────────────────────────────────────────────────────────────────────────
    # Table 6 — SapNetweaver_ABAPGetWPTable_CL  (SM66 Work Process Status)
    # Schema source: SchemaforMCP-Details.csv
    # ──────────────────────────────────────────────────────────────────────────
    "SapNetweaver_ABAPGetWPTable_CL": {
        "table_name": "SapNetweaver_ABAPGetWPTable_CL",
        "domain": "sap_application",
        "description": (
            "SM66 work process view — one row per ABAP work process per collection cycle. "
            "Shows the type (Dialog/Background/Update/Spool/Enqueue), current status "
            "(Run/Wait/Hold/Stop), and the program/user currently running. "
            "Use to detect work process exhaustion, stuck WPs, and high PRIV mode counts."
        ),
        "data_source": "SAP RFC (ABAPGetWPTable)",
        "time_column": "serverTimestamp_t",
        "sid_column": "SID_s",
        "analysis_type": "workprocess_status",
        "key_columns": ["SID_s", "hostname_s", "Typ_s", "Status_s", "Program_s", "User_s"],
        "columns": {
            "SID_s": {
                "type": "string",
                "description": "SAP System ID. ALWAYS filter: | where SID_s == '<sid>'",
            },
            "hostname_s": {"type": "string", "description": "Application server hostname."},
            "instanceNr_d": {"type": "real", "description": "SAP instance number."},
            "No_d": {"type": "real", "description": "Work process number."},
            "Typ_s": {
                "type": "string",
                "description": "Work process type: DIA=Dialog, BTC=Background, UPD=Update, SPO=Spool, ENQ=Enqueue.",
            },
            "Status_s": {
                "type": "string",
                "description": "Current WP status: Run, Wait, Hold, Stop, Ended, Semaphore.",
            },
            "Reason_s": {
                "type": "string",
                "description": "Reason for current status (e.g. PRIV=Private mode, ROLL=Rolling).",
            },
            "Program_s": {
                "type": "string",
                "description": "ABAP program currently running in this work process.",
            },
            "User_s": {
                "type": "string",
                "description": "SAP user running this work process.",
            },
            "Client_s": {"type": "string", "description": "SAP client number."},
            "Action_s": {"type": "string", "description": "Current action by the work process."},
            "Table_s": {"type": "string", "description": "Table being accessed by the work process."},
            "Cpu_s": {"type": "string", "description": "CPU time consumed by this work process."},
            "Err_s": {
                "type": "string",
                "description": "Error indicator — number of times the work process has been restarted.",
            },
            "Sem_s": {"type": "string", "description": "Semaphore number if the WP holds a lock."},
            "Pid_d": {"type": "real", "description": "OS-level process ID of the work process."},
            "serverTimestamp_t": {
                "type": "datetime",
                "description": "Collection timestamp — use for KQL time filters.",
            },
        },
        "kql_hints": [
            "ALWAYS filter by the sid_column shown in this schema (SID_s for this table): | where SID_s == '<sid>'",
            "Use the time_column shown in this schema (serverTimestamp_t for this table) for time filters.",
            "Filter Typ_s == 'BTC' and Status_s == 'Run' to see active batch work processes.",
            "Count WPs by Status_s per host: summarize count() by hostname_s, Typ_s, Status_s",
            "Reason_s == 'PRIV' means the WP is in private memory mode — too many PRIV WPs starves other users.",
            "Cross-reference Program_s with ST22 short dumps to confirm which program caused a WP crash.",
            "Err_s > 0 means the WP has been restarted — indicates instability on that app server.",
        ],
    },

    # ──────────────────────────────────────────────────────────────────────────
    # Table 7 — SapNetweaver_FailedUpdates_CL  (SM13 Update Monitoring)
    # Schema source: SchemaforMCP-Details.csv
    # ──────────────────────────────────────────────────────────────────────────
    "SapNetweaver_FailedUpdates_CL": {
        "table_name": "SapNetweaver_FailedUpdates_CL",
        "domain": "sap_application",
        "description": (
            "SM13 update monitoring — failed V1/V2 update records. "
            "Each row represents one update task that terminated with an error. "
            "VBSTATE_s='1' and VBRC_s='1' are the primary failure indicators. "
            "Failed updates leave business data in an inconsistent state — they are "
            "always high-priority investigation items."
        ),
        "data_source": "SAP RFC (SM13 update monitoring)",
        "time_column": "serverTimestamp_t",
        "sid_column": "SID_s",
        "analysis_type": "Failed_updates",
        "key_columns": ["SID_s", "VBSTATE_s", "VBRC_s", "VBREPORT_s", "VBUSR_s", "VBTCODE_s"],
        "columns": {
            "SID_s": {
                "type": "string",
                "description": "SAP System ID. ALWAYS filter: | where SID_s == '<sid>'",
            },
            "sapsid_s": {"type": "string", "description": "Alternate SAP SID field."},
            "hostname_s": {"type": "string", "description": "Application server hostname."},
            "instanceNr_s": {"type": "string", "description": "SAP instance number."},
            "serverTimestamp_t": {
                "type": "datetime",
                "description": "Collection timestamp — use for KQL time filters.",
            },
            "VBSTATE_s": {
                "type": "string",
                "description": (
                    "Update status. 0=Initial, 1=Error (failed), 2=Success, "
                    "3=In process, 4=Terminated, 5=Retry, 6=Restarted successfully. "
                    "Filter VBSTATE_s == '1' for failed updates."
                ),
            },
            "VBRC_s": {
                "type": "string",
                "description": "Return code. '1' = error. Primary failure indicator alongside VBSTATE_s.",
            },
            "VBREPORT_s": {
                "type": "string",
                "description": "ABAP report/program executed in the update task.",
            },
            "VBTCODE_s": {
                "type": "string",
                "description": "Transaction code that triggered the update.",
            },
            "VBUSR_s": {
                "type": "string",
                "description": "SAP user who triggered the update.",
            },
            "VBCONTEXT_s": {
                "type": "string",
                "description": (
                    "Update context. *E*=Error context (failed); *V*=V1 update (sync); "
                    "*W*=V2 update (async); *B*=Background; *L*=Local update; *R*=Restarted."
                ),
            },
            "VBKEY_g": {"type": "string", "description": "Unique update record identifier (GUID)."},
            "VBTRANSID_g": {"type": "string", "description": "Internal SAP transaction ID (GUID)."},
            "VBDATE_s": {"type": "string", "description": "Timestamp of update request (YYYYMMDDHHMMSS)."},
            "VBMANDT_s": {"type": "string", "description": "SAP client number."},
            "VBNAME_s": {
                "type": "string",
                "description": "Application server on which the update is/was running.",
            },
            "VBENQKEY_s": {
                "type": "string",
                "description": "Enqueue (lock) key held during the update.",
            },
            "VBCLINAME_s": {
                "type": "string",
                "description": "Application server name with instance number where update originated.",
            },
            "VBACCNT_s": {"type": "string", "description": "Account number related to the update (if financial)."},
            "VBLANG_s": {"type": "string", "description": "Language key."},
            "VBTIMOFF_s": {"type": "string", "description": "Time offset from UTC."},
            "VBZONLO_s": {"type": "string", "description": "Application server time zone."},
            "MEMORY_EXEMPTION_s": {"type": "string", "description": "Internal memory handling indicator."},
            "TEMPERATURE_s": {"type": "string", "description": "Internal status/bitmask field used in update processing."},
            "VBCLIINFO_s": {"type": "string", "description": "Technical client info indicator."},
            "VBETRANSID_s": {"type": "string", "description": "External transaction identifier."},
            "VBETRANSLN_s": {"type": "string", "description": "External transaction line number."},
            "VBDATFM_s": {"type": "string", "description": "Date format indicator."},
            "VBDCPFM_s": {"type": "string", "description": "Decimal format indicator."},
        },
        "kql_hints": [
            "ALWAYS filter by the sid_column shown in this schema (SID_s for this table): | where SID_s == '<sid>'",
            "Use the time_column shown in this schema (serverTimestamp_t for this table) for time filters.",
            "Primary failure filter: | where VBSTATE_s == '1' or VBRC_s == '1'",
            "Summarize by VBREPORT_s, VBUSR_s, VBTCODE_s to find which programs/users/transactions are failing.",
            "Cross-reference VBUSR_s and VBTCODE_s with SM21 system logs for the same time window.",
            "VBCONTEXT_s == '*E*' confirms error context — always investigate these.",
            "VBENQKEY_s present means a lock was held during the failed update — check for orphaned locks.",
        ],
    },

    # ──────────────────────────────────────────────────────────────────────────
    # Table 8 — SapNetweaver_ShortDumps_SNAPFulldump_CL  (ST22 Full SNAP Dump Detail)
    # Schema source: SchemaforMCP-Details.csv
    # ──────────────────────────────────────────────────────────────────────────
    "SapNetweaver_ShortDumps_SNAPFulldump_CL": {
        "table_name": "SapNetweaver_ShortDumps_SNAPFulldump_CL",
        "domain": "sap_application",
        "description": (
            "ST22 Full dump details to help understand the issue of the dump occurance. "
            "One row per dump-section combination. Each dump (identified by correlation_id_g + "
            "Runtime_Error_s) is split into multiple rows, one per section. The section_text_s "
            "field contains key=value pairs for that section, and section_key_name_s provides "
            "the SNAP field-code mapping."
        ),
        "usage_guidance": (
            "Use this table AFTER querying SapNetweaver_ShortDumps_CL to identify the dominant errors. "
            "NOTE: The actual Log Analytics table name is SapNetweaver_ShortDumps_SNAPFulldump_CL — "
            "always use this exact name in KQL queries. "
            "This table provides the full section-level detail needed for precise root cause determination: "
            "call stack (CALL_STACK), source code location (SOURCE_CODE), RFC/SQL context (RFC_SQL_CONTEXT), "
            "variable values (SELECTED_VARS), system fields (SYSTEM_FIELDS), and error narrative (WHAT_HAPPENED). "
            "Each dump produces ~10-12 rows (one per section) — filter by Runtime_Error_s and optionally "
            "E2E_USER_s/E2E_HOST_s to limit volume. Do NOT query this table without filters — it is large."
        ),
        "related_tables": [
            {
                "table": "SapNetweaver_ShortDumps_CL",
                "relationship": "summary",
                "join_hint": (
                    "Use ShortDumps_CL first for pattern identification (counts, top errors, affected users). "
                    "Then drill into FULL_SNAP for the specific error types that need root cause detail."
                ),
            }
        ],
        "data_source": "SAP SNAP table (full dump sections)",
        "time_column": "TimeGenerated",
        "sid_column": "sapsid_s",
        "key_columns": [
            "correlation_id_g",
            "Runtime_Error_s",
            "section_s",
            "E2E_USER_s",
            "E2E_HOST_s",
        ],
        "analysis_type": "short_dumps",
        "columns": {
            "TimeGenerated": {
                "type": "datetime",
                "description": (
                    "Ingestion timestamp in Log Analytics (UTC). "
                    "Use for KQL time range filters: | where TimeGenerated > ago(4h)"
                ),
            },
            "correlation_id_g": {
                "type": "string",
                "description": (
                    "Unique GUID identifying a single dump instance. All section rows for the "
                    "same dump share this value — use it to JOIN/correlate sections."
                ),
            },
            "Runtime_Error_s": {
                "type": "string",
                "description": (
                    "ABAP runtime error ID (e.g. CALL_FUNCTION_OPEN_ERROR, UNCAUGHT_EXCEPTION, "
                    "TIME_OUT, DBSQL_SQL_ERROR). Matches ST22 dump category. "
                    "Key field for root cause analysis."
                ),
            },
            "section_s": {
                "type": "string",
                "description": (
                    "Section name identifying which part of the dump this row represents. "
                    "Possible values: IDENTITY, JOB_CONTEXT, SOURCE_CODE, SYSTEM_FIELDS, "
                    "SELECTED_VARS, CALL_STACK, ACTIVE_DATA, ENVIRONMENT, WHAT_HAPPENED, "
                    "SHORT_TEXT, ERROR_ANALYSIS, RFC_SQL_CONTEXT, RAW_ALL."
                ),
            },
            "section_text_s": {
                "type": "string",
                "description": (
                    "Pipe-delimited key=value pairs containing the actual dump data for this section. "
                    "Format: Key1=Value1 | Key2=Value2 | ... "
                    "Parse by splitting on ' | ' then on '='."
                ),
            },
            "section_key_name_s": {
                "type": "string",
                "description": (
                    "SNAP field-code to human-readable key mapping for this section. "
                    "Format: CODE=KeyName, CODE=KeyName, ... "
                    "Empty for unstructured sections like CALL_STACK, ACTIVE_DATA, RAW_ALL."
                ),
            },
            "E2E_DATE_s": {
                "type": "string",
                "description": "Date when the dump occurred in SAP (YYYYMMDD format).",
            },
            "E2E_TIME_s": {
                "type": "string",
                "description": (
                    "Time when the dump occurred in SAP (numeric, may need formatting — "
                    "e.g. 121 means 00:01:21)."
                ),
            },
            "E2E_HOST_s": {
                "type": "string",
                "description": (
                    "Application server host with SID and instance number "
                    "(e.g. vchaa01l0c_CHA_02). Parse to extract hostname, SID, and instanceNr."
                ),
            },
            "E2E_USER_s": {
                "type": "string",
                "description": "SAP user ID under which the program was running when the dump occurred.",
            },
            "hostname_s": {
                "type": "string",
                "description": "Application server hostname (e.g. vchaa01l0c).",
            },
            "sapsid_s": {
                "type": "string",
                "description": "SAP System ID (e.g. CHA, S4H). ALWAYS filter: | where sapsid_s == '<sid>'",
            },
            "instanceNr_s": {
                "type": "string",
                "description": "SAP instance number (e.g. 02).",
            },
            "client_s": {
                "type": "string",
                "description": "SAP client number (e.g. 100, 400).",
            },
            "serverTimestamp_t": {
                "type": "datetime",
                "description": "Timestamp of the dump event from the SAP server (UTC).",
            },
            "timestamp_t": {
                "type": "datetime",
                "description": "Timestamp when this record was collected/ingested by the monitoring provider (UTC).",
            },
        },
        "kql_hints": [
            "ALWAYS filter by the sid_column shown in this schema (sapsid_s for this table): | where sapsid_s == '<sid>'",
            "Use the time_column shown in this schema (TimeGenerated for this table): | where TimeGenerated > ago(4h)",
            "Each dump has multiple rows (one per section) — use correlation_id_g to group all sections of one dump.",
            "Filter section_s == 'IDENTITY' for dump identity (Runtime_Error, Program, Transaction).",
            "Filter section_s == 'CALL_STACK' for the ABAP call stack trace.",
            "Filter section_s == 'SOURCE_CODE' for the exact function/program/line that failed.",
            "Filter section_s == 'WHAT_HAPPENED' for error circumstances and context.",
            "Filter section_s == 'ERROR_ANALYSIS' for exception class details (OO exceptions).",
            "Filter section_s == 'RFC_SQL_CONTEXT' for RFC destination or SQL details.",
            "Filter section_s == 'JOB_CONTEXT' for background job info (if dump occurred in batch).",
            "Parse section_text_s by splitting on ' | ' then on '=' to extract key-value pairs.",
            "Correlate with SapNetweaver_ShortDumps_CL using Runtime_Error_s and time window for summary + detail analysis.",
            "Summarize dcount(correlation_id_g) by Runtime_Error_s to count unique dumps by error type.",
        ],
    },

    # ──────────────────────────────────────────────────────────────────────────
    # Table 9 — SapNetweaver_BatchJobLog_CL  (SM37 Batch Job Log — Aborted Jobs)
    # Schema source: SchemaforMCP-Details.csv
    # ──────────────────────────────────────────────────────────────────────────
    "SapNetweaver_BatchJobLog_CL": {
        "table_name": "SapNetweaver_BatchJobLog_CL",
        "domain": "sap_application",
        "description": (
            "SM37 Batch Job job Log with details of aborted (STATUS=A) job step, program. "
            "One row per aborted job. Enriches basic job metadata from JOB_SELECT with step "
            "details from JOB_READ and log entries from JOBLOG_READ. Only jobs with status A "
            "(canceled/aborted) appear here. Key fields: runtime_error_s for RCA correlation "
            "with ST22, job_log_text_s for full job log narrative, failed_step_program_s for "
            "identifying the failing ABAP program."
        ),
        "data_source": "SAP RFC (BAPI_XBP_JOB_SELECT + JOB_READ + JOBLOG_READ)",
        "time_column": "TimeGenerated",
        "sid_column": "SID_s",
        "key_columns": [
            "jobname_s",
            "jobcount_s",
            "runtime_error_s",
            "failed_step_program_s",
            "failed_step_user_s",
            "hostname_s",
        ],
        "analysis_type": "batch_jobs",
        "columns": {
            "TimeGenerated": {
                "type": "datetime",
                "description": (
                    "Ingestion timestamp in Log Analytics (UTC). "
                    "Use for KQL time range filters: | where TimeGenerated > ago(4h)"
                ),
            },
            "PROVIDER_INSTANCE_s": {
                "type": "string",
                "description": "Provider instance name configured in AMS (e.g. cha-nw).",
            },
            "SAPMON_VERSION_s": {
                "type": "string",
                "description": "Version of the SAP monitoring provider that collected this record.",
            },
            "SID_s": {
                "type": "string",
                "description": "SAP System ID (e.g. CHA). ALWAYS filter: | where SID_s == '<sid>'",
            },
            "Time_Generated_t": {
                "type": "datetime",
                "description": "Provider-side timestamp when this record was generated (UTC).",
            },
            "client_s": {
                "type": "string",
                "description": "SAP client number (e.g. 100, 400).",
            },
            "error_message_s": {
                "type": "string",
                "description": (
                    "Additional diagnostic error text from the job log — any line that is NOT "
                    "a standard marker (Job started/canceled, Step started) and NOT the runtime "
                    "error line. Contains application-specific error details. Empty when the log "
                    "only has standard marker lines."
                ),
            },
            "failed_step_number_d": {
                "type": "real",
                "description": (
                    "Step number (1-based) where the job failed. If a step has STATUS=A, that "
                    "step number. Otherwise the last step number. 0 if no steps were returned."
                ),
            },
            "failed_step_program_s": {
                "type": "string",
                "description": (
                    "ABAP program name of the failed step (e.g. /RPM/FICO_INT_PLANNING, "
                    "PLM_VC_AFL_SESSION_CLEANUP). Cross-reference with ST22 Program_s."
                ),
            },
            "failed_step_user_s": {
                "type": "string",
                "description": "User ID (AUTHCKNAM) under which the failed step was authorized to run.",
            },
            "failed_step_variant_s": {
                "type": "string",
                "description": "Program variant/parameter of the failed step (e.g. Z_VAR, Z_CAPEX).",
            },
            "hostname_s": {
                "type": "string",
                "description": "Application server hostname where the job ran (parsed from REAXSERVER).",
            },
            "instanceNr_s": {
                "type": "string",
                "description": "SAP instance number (parsed from REAXSERVER).",
            },
            "is_periodic_s": {
                "type": "string",
                "description": "Whether the job is periodic/recurring (X = Yes, empty = No).",
            },
            "job_end_date_s": {
                "type": "string",
                "description": "Date when the job ended (DD-MM-YYYY format).",
            },
            "job_end_time_s": {
                "type": "string",
                "description": "Time when the job ended (HH:MM:SS).",
            },
            "job_log_text_s": {
                "type": "string",
                "description": (
                    "Full job log text — all log entries from JOBLOG_READ concatenated with "
                    "newlines. Contains the complete job execution narrative: job start, each "
                    "step start, error lines, and job cancellation. Plain text format."
                ),
            },
            "job_start_date_s": {
                "type": "string",
                "description": "Date when the job started (DD-MM-YYYY format).",
            },
            "job_start_time_s": {
                "type": "string",
                "description": "Time when the job started (HH:MM:SS).",
            },
            "job_status_s": {
                "type": "string",
                "description": "Job status — always 'A' (Aborted/Canceled) since only failed jobs are collected.",
            },
            "jobcount_s": {
                "type": "string",
                "description": (
                    "Unique technical job run identifier (e.g. 18562301). "
                    "Combined with jobname_s uniquely identifies a job execution."
                ),
            },
            "jobname_s": {
                "type": "string",
                "description": "Background job name (e.g. PPM_SERVICE, Y_AVC_SESSION_CLE, ESH100IX_*).",
            },
            "last_changed_by_s": {
                "type": "string",
                "description": "User who last modified the job definition.",
            },
            "last_changed_date_s": {
                "type": "string",
                "description": "Date when the job definition was last changed.",
            },
            "last_changed_time_s": {
                "type": "string",
                "description": "Time when the job definition was last changed.",
            },
            "released_by_user_s": {
                "type": "string",
                "description": "User who released the job for execution (e.g. SAPSYS).",
            },
            "released_date_s": {
                "type": "string",
                "description": "Date when the job was released.",
            },
            "released_time_s": {
                "type": "string",
                "description": "Time when the job was released.",
            },
            "runtime_error_s": {
                "type": "string",
                "description": (
                    "ABAP runtime error name extracted from the job log text (e.g. "
                    "CALL_FUNCTION_OPEN_ERROR, UNCAUGHT_EXCEPTION, TIME_OUT). "
                    "Key field for RCA — correlates with ST22 dump Runtime_Error_s."
                ),
            },
            "sapsid_s": {
                "type": "string",
                "description": "SAP System ID (same as SID_s, repeated for compatibility).",
            },
            "scheduled_by_user_s": {
                "type": "string",
                "description": "User who originally scheduled/created the job.",
            },
            "scheduled_date_s": {
                "type": "string",
                "description": "Date when the job was scheduled.",
            },
            "scheduled_time_s": {
                "type": "string",
                "description": "Time when the job was scheduled.",
            },
            "serverTimestamp_t": {
                "type": "datetime",
                "description": (
                    "Timestamp derived from job start date/time (UTC). "
                    "Use for time-based correlation with other SAP tables."
                ),
            },
            "timestamp_t": {
                "type": "datetime",
                "description": "Collection timestamp when this record was ingested (UTC).",
            },
            "total_steps_d": {
                "type": "real",
                "description": (
                    "Total number of steps in the job (from JOB_READ STEPS table). "
                    "0 if step retrieval failed or returned empty."
                ),
            },
        },
        "kql_hints": [
            "ALWAYS filter by the sid_column shown in this schema (SID_s for this table): | where SID_s == '<sid>'",
            "Use the time_column shown in this schema (TimeGenerated for this table): | where TimeGenerated > ago(4h)",
            "CASE SENSITIVITY: KQL column names are case-sensitive. In THIS table use lowercase columns: jobname_s, jobcount_s, runtime_error_s, failed_step_program_s, failed_step_user_s, job_status_s. Do NOT use UPPERCASE (JOBNAME_s is WRONG for this table — that belongs to SapNetweaver_BatchJobs_CL).",
            "All rows have job_status_s == 'A' (aborted) — no need to filter on status.",
            "Summarize by jobname_s, runtime_error_s to find which jobs fail with which error types.",
            "Summarize by failed_step_program_s to identify which ABAP programs cause the most failures.",
            "runtime_error_s correlates directly with SapNetweaver_ShortDumps_CL.Runtime_Error_s — JOIN on this + time window.",
            "Cross-reference failed_step_program_s with SapNetweaver_ShortDumps_CL.Program_s for full dump details.",
            "Search job_log_text_s for keywords like 'error', 'exception', 'timeout' for additional context.",
            "error_message_s contains application-specific diagnostic text beyond the runtime error.",
            "Use is_periodic_s == 'X' to focus on recurring jobs that keep failing.",
            "Correlate hostname_s + time window with OS metrics and system logs for infrastructure root cause.",
            "bin(TimeGenerated, 1h) to detect patterns of job failures across time.",
        ],
    },
}
