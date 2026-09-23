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
            "sapsid_s": {
                "type": "string",
                "description": "Alternate SAP SID column (same value as SID_s).",
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
            "AUTHCKNAM_s": {
                "type": "string",
                "description": "Authorization check user name — the user authorized to run the job step.",
            },
            "JOBNAME_g": {
                "type": "string",
                "description": "GUID version of the job name (internal unique identifier).",
            },
            "PREDNUM_d": {
                "type": "real",
                "description": "Predecessor job count — number of predecessor job links.",
            },
            "SUCCNUM_d": {
                "type": "real",
                "description": "Successor/success count — number of successor job links.",
            },
            "BTCSYSTEM_s": {
                "type": "string",
                "description": "Batch system identifier (e.g. target system for distributed scheduling).",
            },
            "EXECSERVER_s": {
                "type": "string",
                "description": (
                    "Actual execution server — where the job step ran. "
                    "Distinct from REAXSERVER_s (requested server). Compare to detect scheduling overrides."
                ),
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
            "hostname_s": {
                "type": "string",
                "description": "Application server hostname where the event occurred.",
            },
            "instanceNr_s": {
                "type": "string",
                "description": "SAP instance number.",
            },
            "client_s": {
                "type": "string",
                "description": "SAP client number.",
            },
            "Transaction_s": {
                "type": "string",
                "description": "SAP transaction code in context (if available).",
            },
            "sapsid_s": {
                "type": "string",
                "description": "Alternate SAP SID column (same value as SID_s).",
            },
            "serverTimestamp_t": {
                "type": "datetime",
                "description": "SAP AMS collection timestamp (UTC). Alternate time reference.",
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
            "sapsid_s": {"type": "string", "description": "Alternate SAP SID column (same value as SID_s)."},
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
            "serverTimestamp_t": {
                "type": "datetime",
                "description": "SAP AMS collection timestamp (UTC). Alternate time reference.",
            },
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
            "Cpu_s": {
                "type": "string",
                "description": "Cumulative CPU time since work process start (format H:MM:SS). Sum of CPU system time + CPU user time. Use delta between snapshots for per-program CPU attribution.",
            },
            "Time_s": {
                "type": "string",
                "description": "Elapsed runtime of the current request in seconds. High values indicate long-running requests. Use with Cpu_s delta to compute CPU efficiency (CPU-bound vs I/O-bound).",
            },
            "Start_s": {
                "type": "string",
                "description": "Auto-restart flag (yes/no) — whether the WP restarts automatically after failure.",
            },
            "Err_s": {
                "type": "string",
                "description": "Error indicator — number of times the work process has been restarted.",
            },
            "Sem_s": {"type": "string", "description": "Semaphore number if the WP holds a lock."},
            "Pid_d": {"type": "real", "description": "OS-level process ID of the work process."},
            "sapsid_s": {"type": "string", "description": "Alternate SAP SID column (same value as SID_s)."},
            "instanceNr_s": {"type": "string", "description": "SAP instance number as string (alternate to instanceNr_d)."},
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
            "Time_s contains the elapsed runtime (seconds) of the current request — use to detect long-running requests and compute CPU efficiency.",
            "For CPU attribution: pass CPU core count in context. Query SMON_CL for AVAILCPUS_d first (preferred), fall back to Prometheus_OSExporter_CL if SMON has no data.",
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
            "VBKEY_s": {"type": "string", "description": "Update record key (string). Alternate to VBKEY_g GUID."},
            "VBTRANSID_s": {"type": "string", "description": "Internal SAP transaction ID (string). Alternate to VBTRANSID_g GUID."},
            "client_s": {"type": "string", "description": "SAP client number."},
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
            "jobname_g": {
                "type": "string",
                "description": "GUID version of the job name (internal unique identifier).",
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

    # ──────────────────────────────────────────────────────────────────────────
    # Table 10 — SapNetweaver_SMON_CL  (System Monitor — OS/App performance snapshot)
    # Schema source: LA workspace getschema + take 1
    # ──────────────────────────────────────────────────────────────────────────
    "SapNetweaver_SMON_CL": {
        "table_name": "SapNetweaver_SMON_CL",
        "domain": "sap_application",
        "description": (
            "SAP System Monitor (SMON) — periodic snapshots of application server performance "
            "including CPU usage, memory, work process utilization, queue lengths, and session counts. "
            "Collected every 2 minutes per app server. Use to detect resource exhaustion patterns "
            "(CPU, memory, WP starvation) correlating with application errors."
        ),
        "data_source": "SAP Monitor NetWeaver provider — SMON data",
        "time_column": "serverTimestamp_t",
        "sid_column": "SID_s",
        "analysis_type": "system_performance",
        "key_columns": ["SID_s", "hostname_s", "CPU_CONS_d", "FREE_MEM_PERC_d", "ACT_WPS_d", "PRIVWPNO_d"],
        "columns": {
            "SID_s": {"type": "string", "description": "SAP System ID. ALWAYS filter: | where SID_s == '<sid>'"},
            "sapsid_s": {"type": "string", "description": "Alternate SAP SID column."},
            "hostname_s": {"type": "string", "description": "Application server hostname."},
            "instanceNr_s": {"type": "string", "description": "SAP instance number (e.g. '01')."},
            "client_s": {"type": "string", "description": "SAP client number."},
            "SERVER_s": {"type": "string", "description": "Server identifier in format hostname_SID_instanceNr."},
            "DATUM_s": {"type": "string", "description": "Date of the SMON snapshot (YYYYMMDD format)."},
            "TIME_s": {"type": "string", "description": "Time of the SMON snapshot (HHMMSS format)."},
            "ACT_DIA_d": {"type": "real", "description": "Number of active dialog work processes at snapshot time."},
            "ACT_WPS_d": {"type": "real", "description": "Total active work processes (all types) at snapshot time."},
            "AVAILCPUS_d": {"type": "real", "description": "Number of available CPU cores on this app server."},
            "CPU_CONS_d": {"type": "real", "description": "CPU consumption % at snapshot time. Values >80% indicate CPU contention."},
            "DELTATIMEMS_d": {"type": "real", "description": "Time delta in ms between this and prior snapshot (should be ~60000 for 1min interval)."},
            "DIAAVG20_d": {"type": "real", "description": "Average dialog response time over last 20 seconds (ms)."},
            "DIAAVG60_d": {"type": "real", "description": "Average dialog response time over last 60 seconds (ms)."},
            "DIAQ_d": {"type": "real", "description": "Dialog queue length — number of requests waiting for a dialog WP. >0 sustained = WP exhaustion."},
            "EMALLOC_d": {"type": "real", "description": "Extended memory allocated (MB). High values indicate memory pressure."},
            "EMATTACH_d": {"type": "real", "description": "Extended memory attached/in-use (sessions holding EM)."},
            "ENQQ_d": {"type": "real", "description": "Enqueue queue length — pending lock requests. >0 = enqueue server bottleneck."},
            "FREE_MEM_MB_d": {"type": "real", "description": "Free physical memory on the server (MB)."},
            "FREE_MEM_MB_INC_FS_d": {"type": "real", "description": "Free memory including filesystem cache (MB)."},
            "FREE_MEM_PERC_d": {"type": "real", "description": "Free memory percentage. <20% indicates memory pressure."},
            "HEAPSUMKB_d": {"type": "real", "description": "Total heap memory in use by work processes (KB). High = PRIV mode risk."},
            "IDLE_TOTAL_d": {"type": "real", "description": "CPU idle % (all cores). Low idle = high CPU usage."},
            "PAGE_IN_PERC_d": {"type": "real", "description": "Paging in rate %. >0 indicates memory thrashing."},
            "PAGE_OUT_PERC_d": {"type": "real", "description": "Paging out rate %. >0 indicates memory thrashing."},
            "PRIVWPNO_d": {"type": "real", "description": "Number of work processes in PRIV (private) mode. >2-3 = risk of WP exhaustion."},
            "QINLENGTH_d": {"type": "real", "description": "Inbound qRFC queue length."},
            "QOUTLENGTH_d": {"type": "real", "description": "Outbound qRFC queue length."},
            "READY_TIME_d": {"type": "real", "description": "Dispatcher ready time — time requests waited in dispatcher queue (ms)."},
            "SESSIONS_d": {"type": "real", "description": "Number of active user sessions on this app server."},
            "SM12_CNT_d": {"type": "real", "description": "Number of SM12 lock entries. High count may indicate orphan locks."},
            "STEAL_TIME_d": {"type": "real", "description": "CPU steal time %. >0 on VMs indicates hypervisor contention."},
            "SYS_TOTAL_d": {"type": "real", "description": "System (kernel) CPU %. High = OS overhead."},
            "TRFC_FREE_d": {"type": "real", "description": "Free tRFC worker threads. Low = tRFC processing bottleneck."},
            "UPDQ_d": {"type": "real", "description": "Update queue length — pending V1/V2 updates. >0 sustained = update WP shortage."},
            "USERS_d": {"type": "real", "description": "Number of logged-in users on this app server."},
            "USR_TOTAL_d": {"type": "real", "description": "User (application) CPU %. High = application workload."},
            "QUEUE_FLAG_s": {"type": "string", "description": "Flag indicating if queue statistics are included in this record."},
            "SM50_FLAG_s": {"type": "string", "description": "Flag indicating if SM50 WP data is included."},
            "ST02_FLAG_s": {"type": "string", "description": "Flag indicating if ST02 buffer data is included."},
            "GUID_s": {"type": "string", "description": "Unique identifier for this SMON record."},
            "serverTimestamp_t": {"type": "datetime", "description": "Collection timestamp — use for KQL time filters."},
            "TimeGenerated": {"type": "datetime", "description": "LA ingestion timestamp (UTC)."},
            "Time_Generated_t": {"type": "datetime", "description": "Provider-side timestamp."},
            "timestamp_t": {"type": "datetime", "description": "Record creation timestamp."},
        },
        "kql_hints": [
            "ALWAYS filter by SID_s: | where SID_s == '<sid>'",
            "Use serverTimestamp_t for time filters.",
            "CPU_CONS_d > 80 sustained = CPU bottleneck. Correlate with ACT_WPS_d to see if WP load is driving CPU.",
            "FREE_MEM_PERC_d < 20 = memory pressure. Check PAGE_IN_PERC_d and PAGE_OUT_PERC_d for swapping.",
            "PRIVWPNO_d > 3 = risk of work process exhaustion. Correlate with HEAPSUMKB_d.",
            "DIAQ_d > 0 sustained = dialog WP starvation — users are waiting.",
            "UPDQ_d > 0 sustained = update work process shortage — SM13 failures may follow.",
            "STEAL_TIME_d > 5 on VMs = hypervisor/co-tenant interference.",
            "Summarize avg(CPU_CONS_d), avg(FREE_MEM_PERC_d), max(PRIVWPNO_d), max(DIAQ_d) by bin(serverTimestamp_t, 5m), hostname_s for trending.",
            "Cross-reference high CPU/memory periods with ST22 dump spikes and SM37 job failures.",
            "AVAILCPUS_d provides the CPU core count per host — use this for WP CPU attribution (pass as 'AVAILCPUS_d=N' in context when querying ABAPGetWPTable_CL).",
            "CPU_CONS_d + USR_TOTAL_d can cross-validate WP-derived CPU calculations (pass as 'CPU_CONS_d=N' in context).",
        ],
    },

    # ──────────────────────────────────────────────────────────────────────────
    # Table 11 — SapNetweaver_EnqueueRead_CL  (SM12 Enqueue Lock Monitor)
    # Schema source: LA workspace take 1
    # ──────────────────────────────────────────────────────────────────────────
    "SapNetweaver_EnqueueRead_CL": {
        "table_name": "SapNetweaver_EnqueueRead_CL",
        "domain": "sap_application",
        "description": (
            "SM12 lock table entries — currently held SAP enqueue locks. "
            "Each row is one active lock entry. Use to identify lock contention, "
            "orphaned locks, or users/jobs holding critical locks that block others."
        ),
        "data_source": "SAP Monitor NetWeaver provider — Enqueue Read Lock Metrics",
        "time_column": "serverTimestamp_t",
        "sid_column": "SID_s",
        "analysis_type": "enqueue_locks",
        "key_columns": ["SID_s", "GNAME_s", "GOBJ_s", "GUNAME_s", "GMODE_s", "GTHOST_s"],
        "columns": {
            "SID_s": {"type": "string", "description": "SAP System ID. ALWAYS filter."},
            "sapsid_s": {"type": "string", "description": "Alternate SAP SID column."},
            "hostname_s": {"type": "string", "description": "Application server hostname where the lock was acquired."},
            "instanceNr_s": {"type": "string", "description": "SAP instance number."},
            "client_s": {"type": "string", "description": "SAP client number."},
            "GNAME_s": {"type": "string", "description": "Lock object name (SAP enqueue object, e.g. FARR_S_KEYPP_BUKRS_ENQ, EMFJS_JOBID)."},
            "GOBJ_s": {"type": "string", "description": "Lock object table/argument name (underlying DB table, e.g. EFARR_KEYPPBUKRS)."},
            "GARG_s": {"type": "string", "description": "Lock argument — the specific key value locked (client + key fields concatenated)."},
            "GTARG_s": {"type": "string", "description": "Transaction lock argument (same or similar to GARG_s in most cases)."},
            "GMODE_s": {"type": "string", "description": "Lock mode: E=Exclusive, S=Shared, X=Exclusive non-cumulative, O=Optimistic."},
            "GUNAME_s": {"type": "string", "description": "User holding the lock. Key for identifying who is blocking."},
            "GCLIENT_s": {"type": "string", "description": "Client number for the lock entry."},
            "GTHOST_s": {"type": "string", "description": "Host_SID_InstanceNr of the transaction holding the lock."},
            "GTSYSNR_s": {"type": "string", "description": "System number of the lock holder."},
            "GTDATE_s": {"type": "string", "description": "Date when lock was acquired (YYYY-MM-DD)."},
            "GTTIME_s": {"type": "string", "description": "Time when lock was acquired (HH:MM:SS)."},
            "GTUSEC_s": {"type": "string", "description": "Microsecond precision of lock acquisition time."},
            "GTWP_s": {"type": "string", "description": "Work process number holding the lock."},
            "GUSE_d": {"type": "real", "description": "Lock use count."},
            "GUSETXT_s": {"type": "string", "description": "Lock use text counter."},
            "GUSEVB_d": {"type": "real", "description": "Lock use in update (VB) context count."},
            "GUSEVBT_s": {"type": "string", "description": "Lock use text counter for update context."},
            "GUSR_s": {"type": "string", "description": "User session identifier (timestamp + WP + host encoded)."},
            "GUSRVB_s": {"type": "string", "description": "Update session identifier (timestamp + WP + host encoded)."},
            "GBCKTYPE_s": {"type": "string", "description": "Lock backup type indicator."},
            "GTCODE_s": {"type": "string", "description": "Transaction code that acquired the lock. Key for identifying which transaction holds blocking locks."},
            "hostname_g": {"type": "string", "description": "GUID hostname identifier."},
            "GARG_g": {"type": "string", "description": "GUID lock argument (alternate to GARG_s)."},
            "GTARG_g": {"type": "string", "description": "GUID transaction argument (alternate to GTARG_s)."},
            "serverTimestamp_t": {"type": "datetime", "description": "Collection timestamp — use for KQL time filters."},
            "TimeGenerated": {"type": "datetime", "description": "LA ingestion timestamp."},
            "Time_Generated_t": {"type": "datetime", "description": "Provider-side timestamp."},
            "timeStamp_t": {"type": "datetime", "description": "Record timestamp."},
        },
        "kql_hints": [
            "ALWAYS filter by SID_s: | where SID_s == '<sid>'",
            "Use serverTimestamp_t for time filters.",
            "GMODE_s == 'E' (Exclusive) locks block other users — focus on these for contention analysis.",
            "Summarize count() by GNAME_s, GUNAME_s to find who holds the most locks and on which objects.",
            "Long-held locks: compare GTDATE_s/GTTIME_s with current time — locks older than the collection interval may be orphaned.",
            "Cross-reference GUNAME_s with SM37 batch job users to identify if background jobs hold locks.",
            "High lock count on a single object may cause SM13 update failures (lock collision).",
        ],
    },

    # ──────────────────────────────────────────────────────────────────────────
    # Table 12 — SapNetweaver_OutboundQueues_CL  (SMQ1 Outbound qRFC Queues)
    # Schema source: LA workspace take 1
    # ──────────────────────────────────────────────────────────────────────────
    "SapNetweaver_OutboundQueues_CL": {
        "table_name": "SapNetweaver_OutboundQueues_CL",
        "domain": "sap_application",
        "description": (
            "SMQ1 outbound qRFC queue monitoring. Each row is one outbound queue with its "
            "current depth and destination. Use to identify stuck queues that prevent data "
            "from being sent to downstream systems (e.g. BW, GTS, SCM)."
        ),
        "data_source": "SAP Monitor NetWeaver provider — Outbound Queues",
        "time_column": "serverTimestamp_t",
        "sid_column": "SID_s",
        "analysis_type": "queue_monitoring",
        "key_columns": ["SID_s", "QNAME_s", "DEST_s", "QDEEP_d"],
        "columns": {
            "SID_s": {"type": "string", "description": "SAP System ID. ALWAYS filter."},
            "sapsid_s": {"type": "string", "description": "Alternate SAP SID column."},
            "client_s": {"type": "string", "description": "SAP client number."},
            "instanceNr_s": {"type": "string", "description": "SAP instance number."},
            "QNAME_s": {"type": "string", "description": "Queue name — identifies the data flow (e.g. BW3000ASSET_ATTR_TEXT). Contains destination + data type info."},
            "DEST_s": {"type": "string", "description": "RFC destination the queue sends to (e.g. BIPPRD300). Empty if destination is embedded in QNAME_s."},
            "QDEEP_d": {"type": "real", "description": "Queue depth — number of entries waiting to be sent. >0 means queue has pending items. Very high = stuck queue."},
            "MANDT_s": {"type": "string", "description": "SAP client (mandant) number for the queue entry."},
            "FDATE_s": {"type": "string", "description": "First entry date in queue (YYYY-MM-DD). 0000-00-00 if never processed."},
            "FTIME_s": {"type": "string", "description": "First entry time in queue (HH:MM:SS)."},
            "FQCOUNT_s": {"type": "string", "description": "First entry queue counter."},
            "LDATE_s": {"type": "string", "description": "Last entry date in queue (YYYY-MM-DD)."},
            "LTIME_s": {"type": "string", "description": "Last entry time in queue (HH:MM:SS)."},
            "LQCOUNT_s": {"type": "string", "description": "Last entry queue counter."},
            "serverTimestamp_t": {"type": "datetime", "description": "Collection timestamp — use for KQL time filters."},
            "TimeGenerated": {"type": "datetime", "description": "LA ingestion timestamp."},
            "Time_Generated_t": {"type": "datetime", "description": "Provider-side timestamp."},
            "timestamp_t": {"type": "datetime", "description": "Record timestamp."},
        },
        "kql_hints": [
            "ALWAYS filter by SID_s: | where SID_s == '<sid>'",
            "Use serverTimestamp_t for time filters.",
            "QDEEP_d > 0 indicates pending queue entries — large values mean the queue is stuck or slow.",
            "Summarize max(QDEEP_d) by QNAME_s, DEST_s to find the most backlogged queues.",
            "Growing QDEEP_d over time (use bin + max) indicates the destination system is unreachable or slow.",
            "Cross-reference DEST_s with SapNetweaver_TransactionalRfc_CL for RFC connection failures.",
        ],
    },

    # ──────────────────────────────────────────────────────────────────────────
    # Table 13 — SapNetweaver_InboundQueues_CL  (SMQ2 Inbound qRFC Queues)
    # Schema source: LA workspace take 1
    # ──────────────────────────────────────────────────────────────────────────
    "SapNetweaver_InboundQueues_CL": {
        "table_name": "SapNetweaver_InboundQueues_CL",
        "domain": "sap_application",
        "description": (
            "SMQ2 inbound qRFC queue monitoring. Each row is one inbound queue with its "
            "current depth. Use to identify stuck inbound queues that prevent incoming "
            "data from being processed (e.g. IDocs, master data replication)."
        ),
        "data_source": "SAP Monitor NetWeaver provider — Inbound Queues",
        "time_column": "serverTimestamp_t",
        "sid_column": "SID_s",
        "analysis_type": "queue_monitoring",
        "key_columns": ["SID_s", "QNAME_s", "QDEEP_d"],
        "columns": {
            "SID_s": {"type": "string", "description": "SAP System ID. ALWAYS filter."},
            "sapsid_s": {"type": "string", "description": "Alternate SAP SID column."},
            "client_s": {"type": "string", "description": "SAP client number."},
            "instanceNr_s": {"type": "string", "description": "SAP instance number."},
            "QNAME_s": {"type": "string", "description": "Queue name — identifies the inbound data flow (e.g. MDS_BUPA_CUST00001)."},
            "QDEEP_d": {"type": "real", "description": "Queue depth — number of entries waiting to be processed. >0 = pending items."},
            "MANDT_s": {"type": "string", "description": "SAP client (mandant) number."},
            "FDATE_s": {"type": "string", "description": "First entry date (YYYY-MM-DD)."},
            "FTIME_s": {"type": "string", "description": "First entry time (HH:MM:SS)."},
            "FQCOUNT_s": {"type": "string", "description": "First entry queue counter."},
            "LDATE_s": {"type": "string", "description": "Last entry date (YYYY-MM-DD)."},
            "LTIME_s": {"type": "string", "description": "Last entry time (HH:MM:SS)."},
            "LQCOUNT_s": {"type": "string", "description": "Last entry queue counter."},
            "serverTimestamp_t": {"type": "datetime", "description": "Collection timestamp — use for KQL time filters."},
            "TimeGenerated": {"type": "datetime", "description": "LA ingestion timestamp."},
            "Time_Generated_t": {"type": "datetime", "description": "Provider-side timestamp."},
            "timestamp_t": {"type": "datetime", "description": "Record timestamp."},
        },
        "kql_hints": [
            "ALWAYS filter by SID_s: | where SID_s == '<sid>'",
            "Use serverTimestamp_t for time filters.",
            "QDEEP_d > 0 indicates pending inbound items — large values mean processing is blocked.",
            "Summarize max(QDEEP_d) by QNAME_s to find the most backlogged inbound queues.",
            "Growing queue depth over time indicates the receiving system cannot keep up.",
            "Check SapNetweaver_BatchJobs_CL for queue processing jobs (RBDAPP01, TRFC_QIN_DEST) that may have failed.",
        ],
    },

    # ──────────────────────────────────────────────────────────────────────────
    # Table 14 — SapNetweaver_TransactionalRfc_CL  (SM58 tRFC/aRFC Monitor)
    # Schema source: LA workspace take 1
    # ──────────────────────────────────────────────────────────────────────────
    "SapNetweaver_TransactionalRfc_CL": {
        "table_name": "SapNetweaver_TransactionalRfc_CL",
        "domain": "sap_application",
        "description": (
            "SM58 transactional RFC (tRFC) monitoring — failed or pending tRFC/aRFC calls. "
            "Each row is one tRFC LUW (logical unit of work) that is in error or pending state. "
            "Use to identify RFC communication failures between SAP systems."
        ),
        "data_source": "SAP Monitor NetWeaver provider — Transactional RFC",
        "time_column": "serverTimestamp_t",
        "sid_column": "SID_s",
        "analysis_type": "transactional_rfc",
        "key_columns": ["SID_s", "ARFCDEST_s", "ARFCSTATE_s", "ARFCFNAM_s", "ARFCMSG_s", "ARFCUSER_s"],
        "columns": {
            "SID_s": {"type": "string", "description": "SAP System ID. ALWAYS filter."},
            "sapsid_s": {"type": "string", "description": "Alternate SAP SID column."},
            "hostname_s": {"type": "string", "description": "Application server hostname."},
            "instanceNr_s": {"type": "string", "description": "SAP instance number."},
            "client_s": {"type": "string", "description": "SAP client number."},
            "ARFCDEST_s": {"type": "string", "description": "RFC destination name (e.g. GTPE4H300). Identifies the target system."},
            "ARFCFNAM_s": {"type": "string", "description": "Function module name being called via tRFC (e.g. /SAPSLL/API_6800_CIBD_SYNCH)."},
            "ARFCSTATE_s": {"type": "string", "description": "tRFC status: SYSFAIL=system failure, CPICERR=CPIC error, RECORDED=pending, EXECUTED=success."},
            "ARFCMSG_s": {"type": "string", "description": "Error message text. Key for root cause (e.g. 'Incorrect callup of function module...')."},
            "ARFCUSER_s": {"type": "string", "description": "User under whose authorization the tRFC was triggered."},
            "ARFCRHOST_s": {"type": "string", "description": "Remote host (sending application server)."},
            "ARFCDATUM_s": {"type": "string", "description": "Date when the tRFC was created (YYYYMMDD)."},
            "ARFCUZEIT_s": {"type": "string", "description": "Time when the tRFC was created (HHMMSS)."},
            "ARFCRETRYS_s": {"type": "string", "description": "Number of retry attempts. High count = persistent failure."},
            "ARFCLUWCNT_s": {"type": "string", "description": "LUW (logical unit of work) counter for this tRFC entry."},
            "ARFCPID_s": {"type": "string", "description": "Process/program ID that initiated the tRFC."},
            "ARFCRESERV_s": {"type": "string", "description": "Calling program (report name, e.g. RBDAPP01)."},
            "ARFCIPID_s": {"type": "string", "description": "Internal process identifier."},
            "ARFCTIDCNT_s": {"type": "string", "description": "Transaction ID counter."},
            "ARFCTIME_s": {"type": "string", "description": "Internal time identifier."},
            "HASH_s": {"type": "string", "description": "Hash value for deduplication/identification of the tRFC entry."},
            "ARFCRETURN_s": {"type": "string", "description": "RFC return code. Key for diagnosing the specific failure reason."},
            "ARFCTCODE_s": {"type": "string", "description": "Transaction code that triggered the tRFC call. Use for business-context correlation."},
            "serverTimestamp_t": {"type": "datetime", "description": "Collection timestamp — use for KQL time filters."},
            "TimeGenerated": {"type": "datetime", "description": "LA ingestion timestamp."},
            "Time_Generated_t": {"type": "datetime", "description": "Provider-side timestamp."},
            "timestamp_t": {"type": "datetime", "description": "Record timestamp."},
        },
        "kql_hints": [
            "ALWAYS filter by SID_s: | where SID_s == '<sid>'",
            "Use serverTimestamp_t for time filters.",
            "Filter ARFCSTATE_s == 'SYSFAIL' or ARFCSTATE_s == 'CPICERR' for failed RFC calls.",
            "Summarize count() by ARFCDEST_s, ARFCSTATE_s, ARFCMSG_s to find which destinations are failing and why.",
            "ARFCRETRYS_s > 0 indicates persistent failures — the system keeps retrying without success.",
            "Cross-reference ARFCDEST_s with SMQ1 (OutboundQueues) — same destinations may show queue buildup.",
            "ARFCMSG_s contains the actual error reason — search for 'connection', 'timeout', 'authorization' keywords.",
            "Cross-reference ARFCFNAM_s with ST22 dumps — CALL_FUNCTION_OPEN_ERROR dumps relate to RFC failures.",
        ],
    },

    # ──────────────────────────────────────────────────────────────────────────
    # Table 15 — SapNetweaver_SWNC_CL  (ST03N Workload Statistics)
    # Schema source: LA workspace take 1
    # ──────────────────────────────────────────────────────────────────────────
    "SapNetweaver_SWNC_CL": {
        "table_name": "SapNetweaver_SWNC_CL",
        "domain": "sap_application",
        "description": (
            "ST03N workload statistics — aggregated performance metrics per task type "
            "(Dialog, Background, Update, RFC, etc.) per collection interval (10 minutes). "
            "Provides response time breakdown (CPU, DB, queue, roll-wait, processing) "
            "and throughput counts. Use for performance trend analysis and SLA monitoring."
        ),
        "data_source": "SAP Monitor NetWeaver provider — SWNC workload data",
        "time_column": "serverTimestamp_t",
        "sid_column": "SID_s",
        "analysis_type": "workload_statistics",
        "key_columns": ["SID_s", "Task_Type_Name_s", "ST03_Avg_Resp_Time_d", "Total_Steps_d", "ST03_DB_Time_d"],
        "columns": {
            "SID_s": {"type": "string", "description": "SAP System ID. ALWAYS filter."},
            "sapsid_s": {"type": "string", "description": "Alternate SAP SID column."},
            "client_s": {"type": "string", "description": "SAP client number."},
            "Task_Type_s": {"type": "string", "description": "Task type code (hex-encoded, e.g. 0x{01}=Dialog)."},
            "Task_Type_Name_s": {"type": "string", "description": "Human-readable task type: DIALOG, BACKGROUND, UPDATE, RFC, SPOOL, BUFFER_SYNC."},
            "Total_Steps_d": {"type": "real", "description": "Total dialog steps (transactions) in this interval. Throughput indicator."},
            "Total_Response_Time_d": {"type": "real", "description": "Sum of response times across all steps (ms). Divide by Total_Steps_d for average."},
            "Total_CPU_Time_d": {"type": "real", "description": "Total CPU time consumed (ms)."},
            "Total_DB_Time_d": {"type": "real", "description": "Total database time (ms). Dominant portion often."},
            "Total_DB_Dir_Read_Time_d": {"type": "real", "description": "Total DB direct read time (ms)."},
            "Total_DB_Dir_Read_Steps_d": {"type": "real", "description": "Total DB direct read operations (individual SQL calls)."},
            "Total_DB_Seq_Read_Time_d": {"type": "real", "description": "Total DB sequential read time (ms). High = expensive table scans."},
            "Total_DB_Seq_Read_Steps_d": {"type": "real", "description": "Total DB sequential read operations."},
            "Total_DB_Chg_Time_d": {"type": "real", "description": "Total DB change (insert/update/delete) time (ms)."},
            "Total_DB_Change_Steps_d": {"type": "real", "description": "Total DB change operations."},
            "Total_DB_Proc_Time_d": {"type": "real", "description": "Total DB procedure call time (ms)."},
            "Total_DB_Proc_Steps_d": {"type": "real", "description": "Total DB procedure call count."},
            "Total_Processing_Time_d": {"type": "real", "description": "Total ABAP processing time (ms)."},
            "Total_Roll_Wait_Time_d": {"type": "real", "description": "Total roll-wait time (ms) — time spent waiting for RFC responses or GUI roundtrips."},
            "Total_Queue_Time_d": {"type": "real", "description": "Total dispatcher queue wait time (ms). High = WP shortage."},
            "Total_GUI_Time_d": {"type": "real", "description": "Total GUI rendering/transfer time (ms)."},
            "Total_GUI_Net_Time_d": {"type": "real", "description": "Total GUI network time (ms)."},
            "Total_GUI_Steps_d": {"type": "real", "description": "Total GUI roundtrip steps."},
            "PHYCALLS_d": {"type": "real", "description": "Total physical DB calls."},
            "PHYREADCNT_d": {"type": "real", "description": "Total physical DB read operations."},
            "PHYCHNGREC_d": {"type": "real", "description": "Total physical DB change records."},
            "ST03_Avg_Resp_Time_d": {"type": "real", "description": "Average response time per step (ms). Primary SLA metric."},
            "ST03_CPU_Time_d": {"type": "real", "description": "CPU time as fraction of response time (0-1)."},
            "ST03_DB_Time_d": {"type": "real", "description": "DB time as fraction of response time (0-1). >0.5 = DB-bound."},
            "ST03_Processing_Time_d": {"type": "real", "description": "Processing time fraction (0-1)."},
            "ST03_Queue_Time_d": {"type": "real", "description": "Queue time fraction (0-1). >0.01 = dispatcher contention."},
            "ST03_RollWait_Time_d": {"type": "real", "description": "Roll-wait fraction (0-1). High = waiting for external responses."},
            "ST03_Avg_DB_Dir_Time_d": {"type": "real", "description": "Average DB direct read time per step (ms)."},
            "ST03_Avg_DB_Seq_Time_d": {"type": "real", "description": "Average DB sequential read time per step (ms)."},
            "ST03_Avg_DB_Change_Time_d": {"type": "real", "description": "Average DB change time per step (ms)."},
            "ST03_Avg_DB_Procedure_Time_d": {"type": "real", "description": "Average DB procedure time per step (ms)."},
            "serverTimestamp_t": {"type": "datetime", "description": "Collection timestamp — use for KQL time filters."},
            "TimeGenerated": {"type": "datetime", "description": "LA ingestion timestamp."},
            "Time_Generated_t": {"type": "datetime", "description": "Provider-side timestamp."},
            "timestamp_t": {"type": "datetime", "description": "Record timestamp."},
        },
        "kql_hints": [
            "ALWAYS filter by SID_s: | where SID_s == '<sid>'",
            "Use serverTimestamp_t for time filters.",
            "Filter Task_Type_Name_s == 'DIALOG' for end-user interactive performance.",
            "Filter Task_Type_Name_s == 'BACKGROUND' for batch processing performance.",
            "ST03_Avg_Resp_Time_d > 1000ms for dialog = poor user experience.",
            "ST03_DB_Time_d > 0.6 means the workload is heavily DB-bound — investigate HANA load.",
            "ST03_Queue_Time_d > 0.01 indicates dispatcher/WP shortage — correlate with SMON DIAQ_d.",
            "Summarize avg(ST03_Avg_Resp_Time_d), sum(Total_Steps_d) by bin(serverTimestamp_t, 10m), Task_Type_Name_s for performance trending.",
            "Compare Total_DB_Seq_Read_Time_d vs Total_DB_Dir_Read_Time_d — high sequential = missing indexes or full table scans.",
        ],
    },

    # ──────────────────────────────────────────────────────────────────────────
    # Table 16 — SapNetweaver_STMS_CL  (STMS Transport Requests)
    # Schema source: LA workspace take 1
    # ──────────────────────────────────────────────────────────────────────────
    "SapNetweaver_STMS_CL": {
        "table_name": "SapNetweaver_STMS_CL",
        "domain": "sap_application",
        "description": (
            "STMS Change & Transport System — transport request headers. "
            "Each row is one transport request with its status and metadata. "
            "Use to track code/config changes deployed to the system that may correlate with new errors."
        ),
        "data_source": "SAP Monitor NetWeaver provider — STMS Metrics",
        "time_column": "serverTimestamp_t",
        "sid_column": "SID_s",
        "analysis_type": "transport_management",
        "key_columns": ["SID_s", "TRKORR_s", "TRSTATUS_s", "TRFUNCTION_s", "AS4USER_s"],
        "columns": {
            "SID_s": {"type": "string", "description": "SAP System ID. ALWAYS filter."},
            "sapsid_s": {"type": "string", "description": "Alternate SAP SID column."},
            "hostname_s": {"type": "string", "description": "Application server hostname."},
            "instanceNr_s": {"type": "string", "description": "SAP instance number."},
            "client_s": {"type": "string", "description": "SAP client number."},
            "TRKORR_s": {"type": "string", "description": "Transport request number (e.g. MS2K9A2VDY, SAPK-10013INASANWEE)."},
            "TRSTATUS_s": {"type": "string", "description": "Transport status: R=Released, D=Modifiable, L=Not released, O=Release started, N=Not importable."},
            "TRFUNCTION_s": {"type": "string", "description": "Transport type: K=Workbench, W=Customizing, T=TOC (transport of copies), D=Delivery (SAP patches)."},
            "KORRDEV_s": {"type": "string", "description": "Transport layer (e.g. SYST=system layer, Z*=customer layer)."},
            "TARSYSTEM_s": {"type": "string", "description": "Target system for this transport."},
            "AS4USER_s": {"type": "string", "description": "User who last changed/released the transport."},
            "AS4DATE_s": {"type": "string", "description": "Date of last change/release (YYYYMMDD)."},
            "AS4TIME_s": {"type": "string", "description": "Time of last change/release (HHMMSS)."},
            "STRKORR_s": {"type": "string", "description": "Superior transport request number (parent request for task-level transports)."},
            "serverTimestamp_t": {"type": "datetime", "description": "Collection timestamp — use for KQL time filters."},
            "TimeGenerated": {"type": "datetime", "description": "LA ingestion timestamp."},
            "Time_Generated_t": {"type": "datetime", "description": "Provider-side timestamp."},
            "timestamp_t": {"type": "datetime", "description": "Record timestamp."},
        },
        "kql_hints": [
            "ALWAYS filter by SID_s: | where SID_s == '<sid>'",
            "Use serverTimestamp_t for time filters.",
            "TRSTATUS_s == 'R' means released/imported — these are the transports that changed the system.",
            "Correlate AS4DATE_s/AS4TIME_s with the onset of new errors in ST22/SM21 to identify change-related failures.",
            "TRFUNCTION_s == 'K' = workbench (code changes), 'W' = customizing (config changes).",
            "Filter by AS4USER_s to track who imported changes before an incident.",
        ],
    },

    # ──────────────────────────────────────────────────────────────────────────
    # Table 17 — SapNetweaver_STMS_ObjectEntries_CL  (STMS Transport Object Details)
    # Schema source: LA workspace take 1
    # ──────────────────────────────────────────────────────────────────────────
    "SapNetweaver_STMS_ObjectEntries_CL": {
        "table_name": "SapNetweaver_STMS_ObjectEntries_CL",
        "domain": "sap_application",
        "description": (
            "STMS transport object entries — individual objects within transport requests. "
            "Each row is one object (class, program, table entry, etc.) in a transport. "
            "Use to identify exactly which code/config objects were deployed."
        ),
        "data_source": "SAP Monitor NetWeaver provider — STMS Object Entries",
        "time_column": "serverTimestamp_t",
        "sid_column": "SID_s",
        "analysis_type": "transport_management",
        "key_columns": ["SID_s", "TRKORR_s", "OBJECT_s", "OBJ_NAME_s", "AS4USER_s"],
        "columns": {
            "SID_s": {"type": "string", "description": "SAP System ID. ALWAYS filter."},
            "sapsid_s": {"type": "string", "description": "Alternate SAP SID column."},
            "hostname_s": {"type": "string", "description": "Application server hostname."},
            "instanceNr_s": {"type": "string", "description": "SAP instance number."},
            "client_s": {"type": "string", "description": "SAP client number."},
            "TRKORR_s": {"type": "string", "description": "Transport request number this object belongs to."},
            "TRSTATUS_s": {"type": "string", "description": "Transport status: R=Released."},
            "OBJECT_s": {"type": "string", "description": "Object type: CLAS=Class, PROG=Program, FUNC=Function Module, TABD=Table Definition, DOMA=Domain, DTEL=Data Element."},
            "OBJ_NAME_s": {"type": "string", "description": "Object name (e.g. ZCL_ZP2P_GET_PO_DETAIL_DPC). Cross-reference with ST22 Program_s."},
            "AS4TEXT_s": {"type": "string", "description": "Transport description text (e.g. ticket number + change description)."},
            "AS4USER_s": {"type": "string", "description": "User who last modified this object in the transport."},
            "AS4DATE_s": {"type": "string", "description": "Date of last modification (YYYYMMDD)."},
            "AS4TIME_s": {"type": "string", "description": "Time of last modification (HHMMSS)."},
            "AS4POS_s": {"type": "string", "description": "Position/sequence number of this object in the transport."},
            "CLIENT_s": {"type": "string", "description": "Source client where the object was recorded."},
            "TARCLIENT_s": {"type": "string", "description": "Target client for import."},
            "LANGU_s": {"type": "string", "description": "Language key (E=English)."},
            "TRANSPORT_CLIENT_s": {"type": "string", "description": "Client used for the transport import."},
            "OBJ_NAME_g": {"type": "string", "description": "GUID object name (alternate to OBJ_NAME_s)."},
            "serverTimestamp_t": {"type": "datetime", "description": "Collection timestamp — use for KQL time filters."},
            "TimeGenerated": {"type": "datetime", "description": "LA ingestion timestamp."},
            "Time_Generated_t": {"type": "datetime", "description": "Provider-side timestamp."},
            "timestamp_t": {"type": "datetime", "description": "Record timestamp."},
        },
        "kql_hints": [
            "ALWAYS filter by SID_s: | where SID_s == '<sid>'",
            "Use serverTimestamp_t for time filters.",
            "Cross-reference OBJ_NAME_s with ST22 Program_s — if a newly transported class/program starts dumping, the transport is the root cause.",
            "Filter OBJECT_s == 'CLAS' or OBJECT_s == 'PROG' for code changes.",
            "Join with SapNetweaver_STMS_CL on TRKORR_s for transport metadata (user, status, description).",
            "AS4TEXT_s often contains ticket/CR numbers — useful for linking to change management.",
        ],
    },

    # ──────────────────────────────────────────────────────────────────────────
    # Table 18 — SapNetweaver_GetQueueStatistic_CL  (Dispatcher Queue Statistics)
    # Schema source: LA workspace take 1 (BPP system, 2026-08-10)
    # ──────────────────────────────────────────────────────────────────────────
    "SapNetweaver_GetQueueStatistic_CL": {
        "table_name": "SapNetweaver_GetQueueStatistic_CL",
        "domain": "sap_application",
        "description": (
            "SAP dispatcher queue statistics — one row per queue type per app server per collection. "
            "Shows current depth, high watermark, and max capacity for each dispatcher queue "
            "(ABAP/DIA, ABAP/UPD, ABAP/BTC, ABAP/NOWP, ICM/HTTP, etc.). "
            "Use to detect dispatcher bottlenecks where requests queue up waiting for work processes."
        ),
        "data_source": "SAP SAPControl API (GetQueueStatistic)",
        "time_column": "serverTimestamp_t",
        "sid_column": "SID_s",
        "analysis_type": "queue_monitoring",
        "key_columns": ["SID_s", "hostname_s", "Typ_s", "Now_d", "High_d", "Max_d"],
        "columns": {
            "SID_s": {"type": "string", "description": "SAP System ID. ALWAYS filter."},
            "sapsid_s": {"type": "string", "description": "Alternate SAP SID column."},
            "hostname_s": {"type": "string", "description": "Application server hostname."},
            "instanceNr_d": {"type": "real", "description": "SAP instance number."},
            "Typ_s": {
                "type": "string",
                "description": (
                    "Queue type. Values: 'ABAP/DIA' (dialog), 'ABAP/UPD' (update), "
                    "'ABAP/BTC' (background), 'ABAP/SPO' (spool), 'ABAP/NOWP' (no-WP tasks), "
                    "'ICM/HTTP' (web requests), 'ICM/HTTPS' (secure web)."
                ),
            },
            "Now_d": {"type": "real", "description": "Current queue depth. >0 means requests are waiting. Sustained >0 = bottleneck."},
            "High_d": {"type": "real", "description": "High watermark — peak queue depth since last reset. Indicates worst-case queueing."},
            "Max_d": {"type": "real", "description": "Maximum queue capacity. If Now_d approaches Max_d, requests will be rejected."},
            "Reads_d": {"type": "real", "description": "Total number of read (dequeue) operations — requests that were processed."},
            "Writes_d": {"type": "real", "description": "Total number of write (enqueue) operations — requests that arrived."},
            "serverTimestamp_t": {"type": "datetime", "description": "Collection timestamp — use for KQL time filters."},
            "TimeGenerated": {"type": "datetime", "description": "LA ingestion timestamp."},
            "Time_Generated_t": {"type": "datetime", "description": "Provider-side timestamp."},
            "timestamp_t": {"type": "datetime", "description": "Record timestamp."},
        },
        "kql_hints": [
            "ALWAYS filter by SID_s: | where SID_s == '<sid>'",
            "Use serverTimestamp_t for time filters.",
            "Now_d > 0 on ABAP/DIA = dialog requests waiting for work processes — users experience delays.",
            "Now_d > 0 on ABAP/BTC = batch requests queued — batch jobs delayed.",
            "High_d / Max_d > 0.5 = queue reached half capacity at peak — capacity risk.",
            "Summarize max(Now_d), max(High_d) by hostname_s, Typ_s, bin(serverTimestamp_t, 5m) for trending.",
            "Cross-reference with SMON DIAQ_d which also tracks dialog queue depth.",
            "Writes_d - Reads_d over time = net queue growth rate.",
        ],
    },

    # ──────────────────────────────────────────────────────────────────────────
    # Table 19 — SapNetweaver_EnqGetStatistic_CL  (Enqueue Server Statistics)
    # Schema source: LA workspace take 1 (BPP system, 2026-08-11)
    # ──────────────────────────────────────────────────────────────────────────
    "SapNetweaver_EnqGetStatistic_CL": {
        "table_name": "SapNetweaver_EnqGetStatistic_CL",
        "domain": "sap_application",
        "description": (
            "SAP enqueue server statistics — lock server performance and capacity metrics. "
            "Each row is one snapshot of the enqueue server showing lock counts, capacity, "
            "request counts, and replication state. Use to detect enqueue server exhaustion "
            "(lock table full), high reject rates, or replication failures that impact HA."
        ),
        "data_source": "SAP SAPControl API (EnqGetStatistic)",
        "time_column": "serverTimestamp_t",
        "sid_column": "SID_s",
        "analysis_type": "enqueue_statistics",
        "key_columns": ["SID_s", "hostname_s", "locks_now_d", "locks_high_d", "enqueue_rejects_d", "replication_state_s"],
        "columns": {
            "SID_s": {"type": "string", "description": "SAP System ID. ALWAYS filter."},
            "sapsid_s": {"type": "string", "description": "Alternate SAP SID column."},
            "hostname_s": {"type": "string", "description": "Enqueue server hostname (typically ASCS instance)."},
            "instanceNr_d": {"type": "real", "description": "SAP instance number (ASCS instance number)."},
            "locks_now_d": {"type": "real", "description": "Current number of lock entries. Compare with locks_max_d for capacity."},
            "locks_high_d": {"type": "real", "description": "Peak lock entry count (high watermark)."},
            "locks_max_d": {"type": "real", "description": "Maximum lock table capacity. If locks_now_d approaches this, system will reject new locks."},
            "locks_state_s": {"type": "string", "description": "Lock table state: SAPControl-GREEN=healthy, YELLOW=warning, RED=critical (near full)."},
            "arguments_now_d": {"type": "real", "description": "Current number of lock arguments stored."},
            "arguments_high_d": {"type": "real", "description": "Peak lock argument count."},
            "arguments_max_d": {"type": "real", "description": "Maximum lock argument capacity."},
            "arguments_state_s": {"type": "string", "description": "Arguments state: GREEN/YELLOW/RED."},
            "owner_now_d": {"type": "real", "description": "Current number of lock owners (unique sessions holding locks)."},
            "owner_high_d": {"type": "real", "description": "Peak lock owner count."},
            "owner_max_d": {"type": "real", "description": "Maximum owner capacity."},
            "owner_state_s": {"type": "string", "description": "Owner state: GREEN/YELLOW/RED."},
            "replication_state_s": {"type": "string", "description": "Enqueue replication state: SAPControl-GREEN=in-sync. RED/YELLOW=replication broken (HA risk)."},
            "enqueue_requests_d": {"type": "real", "description": "Total enqueue (lock) requests since server start."},
            "enqueue_rejects_d": {"type": "real", "description": "Total rejected lock requests (lock collisions). High rate = contention."},
            "enqueue_errors_d": {"type": "real", "description": "Total enqueue errors. >0 = enqueue server issue."},
            "dequeue_requests_d": {"type": "real", "description": "Total dequeue (unlock) requests."},
            "dequeue_all_requests_d": {"type": "real", "description": "Total dequeue-all (bulk unlock) requests."},
            "dequeue_errors_d": {"type": "real", "description": "Total dequeue errors."},
            "cleanup_requests_d": {"type": "real", "description": "Lock cleanup requests (orphan lock removal)."},
            "backup_requests_d": {"type": "real", "description": "Enqueue replication backup requests."},
            "reporting_requests_d": {"type": "real", "description": "Enqueue monitoring/reporting requests."},
            "compress_requests_d": {"type": "real", "description": "Lock table compression requests."},
            "verify_requests_d": {"type": "real", "description": "Lock table verification requests."},
            "lock_time_d": {"type": "real", "description": "Total lock processing time (seconds). High = enqueue server overloaded."},
            "lock_wait_time_d": {"type": "real", "description": "Total time spent waiting for locks (seconds). High = lock contention."},
            "server_time_d": {"type": "real", "description": "Enqueue server processing time."},
            "serverTimestamp_t": {"type": "datetime", "description": "Collection timestamp — use for KQL time filters."},
            "TimeGenerated": {"type": "datetime", "description": "LA ingestion timestamp."},
            "Time_Generated_t": {"type": "datetime", "description": "Provider-side timestamp."},
            "timestamp_t": {"type": "datetime", "description": "Record timestamp."},
        },
        "kql_hints": [
            "ALWAYS filter by SID_s: | where SID_s == '<sid>'",
            "Use serverTimestamp_t for time filters.",
            "locks_state_s != 'SAPControl-GREEN' indicates lock table capacity warning or critical.",
            "locks_now_d / locks_max_d > 0.7 = lock table is filling up — risk of lock table overflow.",
            "enqueue_rejects_d growing over time = lock collision rate increasing — contention issue.",
            "replication_state_s != 'SAPControl-GREEN' = enqueue replication broken — HA failover will lose locks.",
            "lock_wait_time_d / lock_time_d ratio indicates how much time is spent waiting vs processing.",
            "Cross-reference with SapNetweaver_EnqueueRead_CL for the actual lock entries being held.",
            "Summarize max(locks_now_d), max(locks_high_d), sum(enqueue_rejects_d) by bin(serverTimestamp_t, 5m) for trending.",
        ],
    },
}
