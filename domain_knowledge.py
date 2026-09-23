"""SAP domain knowledge for RCA classification.

Contains:
  RUNTIME_ERROR_CATEGORIES  : runtime error code → category / subcategory / meaning / investigation_hints
  JOB_STATUS_LABELS         : SM37 status code → label / is_failure / description / meaning / investigation_hints
  SM21_MSG_GROUPS           : SM21 message group prefix → category / meaning / investigation_hints
  NW_INSTANCE_RULES         : (inst_type + status bucket) → category / meaning / investigation_hints
  FULL_SNAP_SECTION_GUIDE   : section_s value → what to extract and how to use it in RCA
  classify_runtime_error()  : look up a runtime error code
  decode_job_status()       : decode an SM37 status code
  get_msg_group()           : look up an SM21 message group by message ID prefix
  classify_nw_instance()    : classify a SAP instance by type and dispstatus
  get_section_guide()       : get RCA interpretation guide for a FULL_SNAP section
"""
from __future__ import annotations

# ── FULL_SNAP Section Guide ───────────────────────────────────────────────────
# Tells the agent how to parse and use each section from SapNetweaver_ShortDumps_SNAPFulldump_CL.
# section_text_s format: pipe-delimited key=value pairs (split on ' | ' then on first '=').
# section_key_name_s format: mixed — some entries use "CODE=KeyName" (e.g. FC=Runtime_Errors),
#   some use just "KeyName" without a code prefix, some are empty (CALL_STACK, ACTIVE_DATA).
#   Not all sections populate section_key_name_s — always rely on section_text_s for actual data.

FULL_SNAP_SECTION_GUIDE: dict[str, dict] = {
    "IDENTITY": {
        "purpose": "Core dump identity — the starting point for any RCA.",
        "key_fields": [
            "Runtime_Errors — the error type (matches ST22 category and Runtime_Error_s column)",
            "ABAP_Program — failing program name",
            "ABAP_Include — specific include within the program",
            "ABAP_Line — source line number where the error occurred",
            "Transaction_ID — SAP transaction/LUW identifier",
            "SAP_Note — SAP note number or SID/host identifier (may contain system context like 'CHA/vchaa01l0c_CHA_02')",
            "Roll_Area_Start_Time — when the failing program started execution (format: YYYYMMDDHHMMSS)",
        ],
        "rca_usage": (
            "Use ABAP_Program + ABAP_Include + ABAP_Line to identify the exact code location. "
            "If SAP_Note contains a numeric note number, reference it — SAP has documented this specific error. "
            "If SAP_Note contains SID/hostname, it identifies the system instance. "
            "Cross-reference ABAP_Program with ST22 summary table Program_s and SM37 failed_step_program_s."
        ),
    },
    "SOURCE_CODE": {
        "purpose": "Exact source code location where the dump occurred.",
        "key_fields": [
            "Function_Module — the function module (if inside a function group, e.g. /RPM/FICO_INT_PLANNING)",
            "Function_Group — the function group name (e.g. RPM_G)",
            "Program — the ABAP program (e.g. SAPLRPM_FICO_INT_DATA)",
            "Include — the specific include (e.g. LRPM_FICO_INT_DATAU01)",
            "Line — source line number (may be concatenated with next field, e.g. '87FUNCTION')",
            "Type — the routine/function name being executed (e.g. RPM_GET_FICO_DATA)",
        ],
        "note": (
            "For UNCAUGHT_EXCEPTION: may contain only Program + Include (without Function_Module/Group). "
            "Field availability depends on whether the error is in a function module, class method, or main program."
        ),
        "rca_usage": (
            "Pinpoints the exact function/method and line. "
            "For RFC errors: Function_Module identifies which RFC function was being called. "
            "For OO exceptions: Program will be the class pool (SAPL* or CL_*======CP). "
            "Use this to determine if it's standard SAP code (SAPL*, CL_*) or custom (Z*, Y*)."
        ),
    },
    "CALL_STACK": {
        "purpose": "Full ABAP call stack at the time of the dump.",
        "key_fields": ["Pipe-delimited SNAP stack frames in internal format"],
        "note": (
            "section_key_name_s is empty for this section. "
            "Format: '<line#> <type> <opcode> <flags> <spaces> <line_in_include> <include_name>' per frame. "
            "Operation codes: STCK=stack entry, BREL=function call boundary, FUNC=function module call, "
            "PAR2=parameter passing, EXCP=exception propagation. "
            "The include name at the end of each frame identifies the code unit."
        ),
        "rca_usage": (
            "Read the include names (last element per frame) to trace the call chain. "
            "For RFC errors: look for frames with BREL/FUNC in LRFC* or CL_RFC* includes. "
            "For batch jobs: look for the job step program include near earlier frames. "
            "Identify whether the failing code is standard SAP or custom (Z/Y prefix in include names)."
        ),
    },
    "WHAT_HAPPENED": {
        "purpose": "Error circumstances — the 'story' of what went wrong.",
        "key_fields": [
            "Calling_Program — the program that triggered the error path (may be program name or hex LUW ID)",
            "Dialog_Step — which dialog step the user was in (numeric)",
            "Error_ID — internal error identifier (e.g. RFC_IO5 for RFC I/O error)",
            "Error_Context — technical error context (e.g. 'IO HANDLE=1 DRV=R/3 LINE=2812 CODE=5')",
            "Error_Summary — error codes and return values (e.g. 'CODE=CM_PRODUCT_SPECIFIC_ERROR -1 -1 SAPCODE=236')",
        ],
        "note": (
            "For UNCAUGHT_EXCEPTION: this section is often minimal — may contain only Calling_Program with a hex ID. "
            "The richest data appears for communication errors (CALL_FUNCTION_*) and database errors (DBIF_*). "
            "If minimal, rely on ERROR_ANALYSIS and SHORT_TEXT sections instead."
        ),
        "rca_usage": (
            "Provides the human-readable explanation of the error. "
            "Error_ID identifies the specific failure type (RFC_IO5 = RFC I/O error code 5). "
            "Error_Context often contains the RFC destination name for communication errors, "
            "the table name for database errors, or the memory area for resource errors. "
            "Error_Summary contains the CM error code for RFC failures — cross-reference with SAP Note 63347. "
            "This is the section that most closely matches what a BASIS admin reads in ST22."
        ),
    },
    "ERROR_ANALYSIS": {
        "purpose": "Exception class details for OO (class-based) exceptions.",
        "key_fields": [
            "Exception_Class — the CX_* class that was raised (e.g. CX_SY_OPEN_SQL_DB)",
        ],
        "rca_usage": (
            "Only populated for UNCAUGHT_EXCEPTION and similar OO error types. "
            "The Exception_Class name directly identifies the failure type. "
            "CX_SY_* = ABAP runtime system exception (zero divide, type mismatch, SQL). "
            "CX_* custom = application-specific exception with documented meaning."
        ),
    },
    "RFC_SQL_CONTEXT": {
        "purpose": "RFC destination or SQL statement context when applicable.",
        "key_fields": [
            "RFC_Destination — the SM59 destination that failed (for RFC errors)",
            "Called_Function — the RFC function module that was called",
            "SQL statement details — for DBIF/DBSQL errors, the failing SQL",
        ],
        "rca_usage": (
            "Critical for Communication errors: RFC_Destination tells you which target system is involved. "
            "Critical for Database errors: the SQL statement identifies the table and operation. "
            "Cross-reference RFC_Destination with system availability and network connectivity. "
            "For DB errors: check if the table exists, if the SQL is valid, and if the DB server was healthy."
        ),
    },
    "JOB_CONTEXT": {
        "purpose": "Background job info if the dump occurred inside a batch job.",
        "key_fields": [
            "Job_Name — SM37 job name (e.g. PPM_SERVICE)",
            "Job_Number — unique job run identifier / JOBCOUNT (e.g. 11512400)",
            "Scheduled_By — user who scheduled the job",
            "Client — SAP client number (e.g. 100)",
            "User — user under which the job step runs",
            "Language — logon language (e.g. E)",
        ],
        "note": (
            "For dialog sessions or UNCAUGHT_EXCEPTION in non-batch context: "
            "this section may contain only 'ABAP_CONT_Offset=<number>' (a memory offset, not job info). "
            "If only ABAP_CONT_Offset is present, the dump did NOT occur in a batch job."
        ),
        "rca_usage": (
            "Links the dump to a specific batch job run when Job_Name is present. "
            "Cross-reference Job_Name + Job_Number with SapNetweaver_BatchJobs_CL (JOBNAME_s, JOBCOUNT_s) "
            "and SapNetweaver_BatchJobLog_CL (jobname_s, jobcount_s) for full job execution context. "
            "If only ABAP_CONT_Offset is present: the dump occurred in a dialog session, not a batch job."
        ),
    },
    "SYSTEM_FIELDS": {
        "purpose": "SY-* system variable values at the moment of the dump.",
        "key_fields": [
            "SY-SUBRC — return code of the last ABAP statement (0=success, others=error)",
            "SY-INDEX — current loop counter",
            "SY-TABIX — current internal table line index",
            "SY-DBCNT — number of DB records affected by the last SQL",
            "SY-FDPOS — position of a found substring",
            "SY-UZEIT — time of the dump (HHMMSS format)",
            "SY-XPROG — external calling program name",
            "SY-LSIND — list index for report output",
            "SY-PAGNO — page number in list output",
        ],
        "note": (
            "Available fields vary by error type. Communication errors typically show the full set "
            "(SY-SUBRC, SY-INDEX, SY-TABIX, SY-DBCNT, SY-FDPOS, SY-LSIND, SY-PAGNO). "
            "OO exceptions (UNCAUGHT_EXCEPTION) may show only SY-UZEIT and SY-XPROG."
        ),
        "rca_usage": (
            "SY-SUBRC != 0 before the dump indicates the preceding statement failed. "
            "SY-DBCNT shows how many records the last DB operation processed. "
            "SY-TABIX = 0 with a READ TABLE error means the record was not found. "
            "SY-XPROG identifies the external program that was running (useful for batch job context). "
            "These values give precise state context for data-dependent errors."
        ),
    },
    "SELECTED_VARS": {
        "purpose": "Selected ABAP variable values captured at dump time.",
        "key_fields": ["Program-specific variables and their contents at the moment of failure"],
        "rca_usage": (
            "Contains the actual data values that the program was working with when it crashed. "
            "For data-dependent errors (CONVT_NO_NUMBER, COMPUTE_INT_ZERODIVIDE): "
            "the offending data value is visible here. "
            "For RFC errors: may contain the RFC destination name or parameters being sent."
        ),
    },
    "ENVIRONMENT": {
        "purpose": "SAP system environment info.",
        "key_fields": [
            "SAP_Release — SAP kernel/basis release version (e.g. 758)",
            "OS — operating system (e.g. Linux)",
            "Hardware — platform (e.g. x86_64)",
            "App_Server — application server hostname (e.g. vchaa01l0c)",
            "DB_Type — database type (HDB=HANA, ORA=Oracle, MSS=SQL Server)",
            "SID — SAP System ID (e.g. CHA)",
            "DB_Server — database server hostname (e.g. vchadcha01l10c)",
            "DB_User — database schema user (e.g. SAPHANADB)",
            "Details — OS kernel/patch version string (e.g. '41035.14.21-150500.55.14C')",
        ],
        "rca_usage": (
            "Use to confirm the SAP release level (needed for SAP note applicability). "
            "App_Server identifies the host — cross-reference with OS metrics and HA cluster data. "
            "DB_Server identifies the database host — cross-reference with HANA metrics if available. "
            "Details provides the OS patch level — relevant for kernel crash and system error investigation."
        ),
    },
    "SHORT_TEXT": {
        "purpose": "One-liner description of the error (same as ST22 short text).",
        "key_fields": ["Short_Text — the error message text (e.g. \"CPIC-CALL: 'ThSAP...\")"],
        "note": (
            "Can be EMPTY for some error types (e.g. UNCAUGHT_EXCEPTION may not populate this). "
            "When empty, use ERROR_ANALYSIS (Exception_Class) or WHAT_HAPPENED for the error description."
        ),
        "rca_usage": (
            "The most concise description of what happened — include in RCA output when populated. "
            "For MESSAGE_TYPE_X: contains the business logic reason for forced termination. "
            "For CALL_FUNCTION_* errors: contains the CPIC error message. "
            "If empty: fall back to ERROR_ANALYSIS.Exception_Class or WHAT_HAPPENED.Error_Summary."
        ),
    },
    "ACTIVE_DATA": {
        "purpose": "Active internal table contents and buffer data at dump time.",
        "key_fields": [
            "V0= entries — object reference variables (e.g. 'V0={O:20*\\CLASS=CX_VCH_HL_AFL_SETUP_E')",
            "TH= entries — internal table header metadata (Table name, dimensions, memory layout)",
        ],
        "note": (
            "section_key_name_s is empty for this section. "
            "V0= shows ABAP object references — \\CLASS= identifies the instantiated class. "
            "TH= shows internal table structure info — \\PROGRAM= and Table lines show which tables were active. "
            "Can be very large — focus on V0= entries for object state and first TH=Table lines for data context."
        ),
        "rca_usage": (
            "For OO exceptions: V0= entries with \\CLASS=CX_* identify the active exception objects. "
            "For data-dependent errors: TH=Table entries show which internal tables were populated. "
            "May contain large volumes of raw memory data — focus on class names and table names for RCA, "
            "not on hex memory dumps."
        ),
    },
}


# ── Runtime Error → Category / Meaning / Investigation Hints ─────────────────
RUNTIME_ERROR_CATEGORIES: dict[str, dict] = {

    # ── Resource Bottlenecks ──────────────────────────────────────────────────
    "MEMORY_NO_MORE_PAGING": {
        "category":    "Resource Bottleneck",
        "subcategory": "Extended Memory",
        "meaning": (
            "SAP extended memory (EM) and the paging area are both exhausted. "
            "The work process cannot allocate more memory for the user context. "
            "SAP uses a layered memory model: roll area → extended memory → paging area → heap. "
            "This error means the system hit the last layer and still had no space."
        ),
        "investigation_hints": [
            "Check whether multiple users hit this error simultaneously on the same host — simultaneous failures indicate system-wide memory pressure, not a single program defect.",
            "Identify which programs and users are consuming the most memory — the top_programs and top_users aggregates from the dump data are the starting point.",
            "Check OS-level memory and swap/paging utilisation on the affected hosts at the time of the dumps.",
            "Check SAP extended memory configuration parameters (em/address_space_MB, em/initial_size_MB) against the current workload.",
            "Check if batch jobs with large internal table selections were running concurrently with the dialog failures.",
        ],
    },
    "SYSTEM_NO_ROLL": {
        "category":    "Resource Bottleneck",
        "subcategory": "Roll Area",
        "meaning": (
            "The SAP roll area is exhausted. The roll area stores user session context "
            "(local variables, call stack) between dialog steps when a work process is released. "
            "Exhaustion means too many sessions are holding roll memory simultaneously."
        ),
        "investigation_hints": [
            "Check how many active sessions were open on the affected host at the time of the error.",
            "Check if any sessions are holding unusually large amounts of roll memory — large data objects passed between dialog steps are the typical cause.",
            "Check OS memory availability on the affected host — roll area is allocated from OS memory.",
            "Check if the number of active work processes is near the configured maximum (rdisp/wp_no_dia).",
        ],
    },
    "SYSTEM_NO_TASK_STORAGE": {
        "category":    "Resource Bottleneck",
        "subcategory": "User Context Memory",
        "meaning": (
            "Memory for a single user work context (task storage) could not be allocated. "
            "This is per-user memory for the current dialog step — the request exceeded the per-user memory limit "
            "or OS memory was insufficient to satisfy the allocation."
        ),
        "investigation_hints": [
            "Identify which program is consuming excessive task storage — it is likely selecting or building large data structures in a single dialog step.",
            "Check OS memory availability on the affected host.",
            "Check if this error is isolated to one user and one program, or if it affects multiple users — widespread failures indicate OS-level memory exhaustion.",
        ],
    },
    "TSV_TNEW_PAGE_ALLOC_FAILED": {
        "category":    "Resource Bottleneck",
        "subcategory": "Internal Table Memory",
        "meaning": (
            "An ABAP internal table (or work area) tried to grow beyond available memory. "
            "SAP could not allocate a new memory page for the internal table. "
            "This typically happens when a program SELECTs a very large result set into an internal table without filtering."
        ),
        "investigation_hints": [
            "Identify which program triggered the dump — it is almost certainly performing a large data selection into an internal table.",
            "Check if the program has WHERE clause filtering or if it is doing full table reads.",
            "Check OS memory on the affected host — if multiple programs hit this simultaneously, it is system-wide memory pressure.",
            "Check if the data volume has grown recently (table growth can cause a previously working program to exceed memory limits).",
        ],
    },
    "RESOURCE_FAILURE": {
        "category":    "Resource Bottleneck",
        "subcategory": "General Resource",
        "meaning": (
            "A general SAP resource allocation failed. This is a catch-all error when SAP cannot obtain "
            "a required system resource — could be memory, work processes, shared memory segments, or other OS resources."
        ),
        "investigation_hints": [
            "Check OS memory, paging, CPU, and disk on the affected host at the time of the failure.",
            "Check the number of available work processes (SM50 equivalent) — if all work processes were busy, new requests fail.",
            "Check if other resource-specific errors (MEMORY_NO_MORE_PAGING, SYSTEM_NO_ROLL) also occurred at the same time on the same host.",
            "Check if this is isolated to one host or affects multiple hosts — multi-host failures suggest a shared resource issue.",
        ],
    },
    "TIME_OUT": {
        "category":    "Resource Bottleneck",
        "subcategory": "Long Running Process",
        "meaning": (
            "The ABAP program exceeded the maximum allowed runtime for a dialog work process "
            "(controlled by rdisp/max_wprun_time, default 600 seconds). "
            "SAP terminated the work process to prevent it from blocking for too long. "
            "This does not necessarily mean the program has a bug — it may be processing more data than expected."
        ),
        "investigation_hints": [
            "Check the program name — determine whether it is a standard SAP report or a custom program.",
            "Check if the same program runs successfully in background (background jobs have no time limit).",
            "Check OS CPU and I/O metrics on the host — hardware resource pressure can cause legitimate programs to time out.",
            "Check if the data volume processed by this program has grown recently (more records = longer runtime).",
            "Check if multiple users ran the same program simultaneously, causing resource contention.",
        ],
    },

    # ── Database Errors ───────────────────────────────────────────────────────
    "DBIF_RSQL_SQL_ERROR": {
        "category":    "Database Error",
        "subcategory": "SQL Runtime Error",
        "meaning": (
            "A database error occurred while the SAP work process was executing an SQL statement. "
            "The database engine returned an error code that SAP could not handle gracefully. "
            "This can be caused by DB connectivity issues, DB server errors, or invalid SQL generated by ABAP."
        ),
        "investigation_hints": [
            "Check database server error logs for the specific SQL error code and the failing statement.",
            "Check whether the error is consistent (always fails on the same data) or intermittent (connection or resource issue).",
            "Check network connectivity and latency between the SAP application server and the database server.",
            "Check if other database errors (BY0, BY1 message IDs in SM21) were recorded at the same time.",
            "Check DB server OS metrics (CPU, memory, disk I/O) — DB errors can be caused by resource exhaustion on the database host.",
        ],
    },
    "DBIF_RSQL_INVALID_REQUEST": {
        "category":    "Database Error",
        "subcategory": "Invalid SQL",
        "meaning": (
            "The ABAP program generated an SQL statement that the database rejected as structurally invalid. "
            "Typical causes: a field referenced in a SELECT does not exist in the physical table, "
            "a data type mismatch, or an incomplete transport left the ABAP dictionary out of sync with the actual DB table."
        ),
        "investigation_hints": [
            "Check if a recent transport changed the ABAP data dictionary definition of the table being accessed.",
            "Check if the physical database table structure matches the ABAP dictionary definition (table activation may have failed).",
            "Check whether this error affects all users who run this transaction or only specific ones — universal failure confirms a schema/transport issue.",
        ],
    },
    "DBSQL_DUPLICATE_KEY_ERROR": {
        "category":    "Database Error",
        "subcategory": "Constraint Violation",
        "meaning": (
            "An INSERT or UPDATE attempted to write a record with a primary key that already exists in the table. "
            "The unique key constraint was violated. "
            "Typical causes: concurrent processes inserting the same record, exhausted number ranges, or a data migration re-inserting existing records."
        ),
        "investigation_hints": [
            "Identify which table and which program triggered the constraint violation.",
            "Check if multiple concurrent batch jobs or users are writing to the same table simultaneously.",
            "Check if a number range object for the affected business object is exhausted — exhausted number ranges can cause duplicate key generation.",
            "Check if a data migration, system copy, or initial load job was running at the time.",
        ],
    },
    "DBSQL_TABLE_UNKNOWN": {
        "category":    "Database Error",
        "subcategory": "Missing Table",
        "meaning": (
            "The ABAP program tried to access a database table that does not exist in the physical database. "
            "The ABAP dictionary may know the table but it was never activated or created at the DB level."
        ),
        "investigation_hints": [
            "Check whether the table exists in the ABAP dictionary and whether it is active.",
            "Check if a transport created the ABAP dictionary entry but the database table activation step failed.",
            "Check if this is a new table introduced by a recent transport — the transport may have applied partially.",
            "Check if a system copy or database restore was performed recently that may have missed this table.",
        ],
    },
    "DBSQL_SQL_ERROR": {
        "category":    "Database Error",
        "subcategory": "Generic SQL Error",
        "meaning": (
            "The database returned a generic SQL error. Similar to DBIF_RSQL_SQL_ERROR but raised at a lower DB interface level. "
            "The error code and message from the database are the primary source of information."
        ),
        "investigation_hints": [
            "Check database server error logs for the specific error code and SQL statement.",
            "Check DB server availability and connectivity from the SAP application server.",
            "Check if other dump types (DBIF_RSQL_SQL_ERROR) or SM21 database message IDs (BY0, BY1) occurred at the same time.",
        ],
    },
    "SQL_CAUGHT_RABAX": {
        "category":    "Database Error",
        "subcategory": "SQL Short Dump",
        "meaning": (
            "An SQL exception was raised inside an ABAP program and propagated up as a short dump "
            "rather than being caught by an exception handler. "
            "The program accessed the database, received an SQL error, and had no handler to process it gracefully."
        ),
        "investigation_hints": [
            "Check Error_Short_Text_s for the specific SQL error message embedded in the dump.",
            "Check database server error logs for the corresponding SQL error.",
            "Determine if the ABAP program has exception handling around its database accesses — the dump means it does not.",
        ],
    },

    # ── Communication / RFC Errors ────────────────────────────────────────────
    "CALL_FUNCTION_REMOTE_ERROR": {
        "category":    "Communication Error",
        "subcategory": "RFC Failure",
        "meaning": (
            "An RFC (Remote Function Call) to another SAP system or service was processed by the target, "
            "but the target function module returned a system-level error back to the caller. "
            "The connection was established and the call was received — but something failed on the target side."
        ),
        "investigation_hints": [
            "Check whether the target RFC destination system was available, healthy, and responding at the time of the error.",
            "Check if the target function module exists and is active in the destination system.",
            "Check whether other users experienced RFC errors to the same destination at the same time — widespread failures indicate a target system issue.",
            "Check if the target system was undergoing maintenance, a restart, or a failover.",
        ],
    },
    "CALL_FUNCTION_RECEIVE_ERROR": {
        "category":    "Communication Error",
        "subcategory": "RFC Receive",
        "meaning": (
            "The calling system established an RFC connection and sent the request, "
            "but failed to receive the response — the connection dropped during the call, timed out, or the target crashed mid-execution."
        ),
        "investigation_hints": [
            "Check network stability between the calling host and the RFC target host.",
            "Check if the target system experienced a crash or restart during the time the RFC call was in progress.",
            "Check RFC timeout configuration — if the target function takes longer than the configured timeout, the caller abandons and raises this error.",
            "Check if the error is consistent (always times out) or intermittent (occasional network flap).",
        ],
    },
    "CALL_FUNCTION_SEND_ERROR": {
        "category":    "Communication Error",
        "subcategory": "RFC Send",
        "meaning": (
            "The RFC request could not be sent from the calling system to the target — "
            "the connection was partially established but failed during the send phase. "
            "Network issues or target system unresponsiveness at connection time are the typical causes."
        ),
        "investigation_hints": [
            "Check network connectivity from the calling application server host to the RFC target.",
            "Check if the RFC target system is running and accepting connections.",
            "Check OS network metrics (connection errors, packet loss) on the calling host.",
            "Check if this is isolated to one RFC destination or affects multiple — widespread failures point to network infrastructure.",
        ],
    },
    "CALL_FUNCTION_OPEN_ERROR": {
        "category":    "Communication Error",
        "subcategory": "RFC Connect",
        "meaning": (
            "The RFC connection to the target system could not be opened at all. "
            "The target was unreachable, refused the connection, or the RFC logon failed. "
            "No part of the call was processed by the target."
        ),
        "investigation_hints": [
            "Check if the RFC destination system is running and reachable from the calling host.",
            "Check RFC destination logon credentials — expired passwords or locked RFC users cause connection open failures.",
            "Check firewall rules and network routing between the two systems.",
            "Check if the target system message server and dispatcher are running.",
        ],
    },

    # ── ABAP Programming Errors ───────────────────────────────────────────────
    "MESSAGE_TYPE_X": {
        "category":    "ABAP Programming Error",
        "subcategory": "Forced Termination",
        "meaning": (
            "The ABAP program explicitly called MESSAGE ... TYPE 'X', which is a developer-coded forced termination. "
            "This is never accidental — it is always an intentional program abort triggered when a specific condition is detected. "
            "The Error_Short_Text_s contains the message that explains exactly what condition caused it."
        ),
        "investigation_hints": [
            "Read Error_Short_Text_s carefully — it contains the business logic reason for the forced termination.",
            "Check whether the same message text appears across multiple users or just one — single-user failures suggest data-dependent input.",
            "Check if a recent transport changed the program or the configuration that drives the condition check.",
            "Determine whether this is a standard SAP program or a custom (Z/Y) program — the fix approach differs.",
        ],
    },
    "RAISE_EXCEPTION": {
        "category":    "ABAP Programming Error",
        "subcategory": "Unhandled Exception",
        "meaning": (
            "An ABAP exception was raised (RAISE or RAISE EXCEPTION) somewhere in the call stack "
            "but no CATCH block existed to handle it. The unhandled exception propagated to the top and caused a dump. "
            "This is a programming error in either the raising program or the calling program."
        ),
        "investigation_hints": [
            "Check Error_Short_Text_s for the exception name and the program/include where it was raised.",
            "Determine whether the exception is data-dependent — check if it only occurs with specific input values.",
            "Check if a recent transport changed either the program that raises the exception or the calling program that should catch it.",
            "Check if the same exception affects multiple users running the same program — if so, it is a code defect, not a data issue.",
        ],
    },
    "UNCAUGHT_EXCEPTION": {
        "category":    "ABAP Programming Error",
        "subcategory": "Unhandled Exception",
        "meaning": (
            "An ABAP OO exception class (CX_*) was instantiated and thrown but no CATCH block caught it anywhere in the call stack. "
            "The exception propagated to the ABAP runtime and caused a dump. "
            "Similar to RAISE_EXCEPTION but specifically for class-based exceptions."
        ),
        "investigation_hints": [
            "Check Error_Short_Text_s for the exception class name (CX_*) — the class name identifies the type of failure.",
            "Check whether the exception is data-dependent or always occurs for the same program.",
            "Check if a recent transport changed the call chain between the raising and the calling program.",
        ],
    },
    "CX_SY_NO_HANDLER": {
        "category":    "ABAP Programming Error",
        "subcategory": "Missing Handler",
        "meaning": (
            "A specific CX_SY_* system exception class was raised (e.g. CX_SY_ZERODIVIDE, CX_SY_OPEN_SQL_DB) "
            "and no CATCH block was present. CX_SY_* exceptions are raised by the ABAP runtime itself "
            "for arithmetic errors, SQL errors, and similar runtime conditions."
        ),
        "investigation_hints": [
            "Identify the specific CX_SY_* class from Error_Short_Text_s — each subclass indicates a different root cause (division by zero, SQL error, type conversion, etc.).",
            "Check whether this is a standard SAP program or a custom program — standard programs raising CX_SY_* unexpectedly may require an SAP note.",
            "Check if a recent change removed exception handling from the program.",
        ],
    },
    "GETWA_NOT_ASSIGNED": {
        "category":    "ABAP Programming Error",
        "subcategory": "Field Symbol Error",
        "meaning": (
            "An ABAP field symbol (a type-independent pointer variable) was used (dereferenced) "
            "without first being assigned to a memory area. "
            "Using an unassigned field symbol always causes a dump — it is equivalent to dereferencing a null pointer."
        ),
        "investigation_hints": [
            "Check whether this dump is data-dependent — it may only occur when a specific record or condition causes an assignment step to be skipped.",
            "Check if a recent transport changed the ABAP code that handles the field symbol assignment.",
            "Check if the same program runs successfully with other data — if it does, the input data is driving the unassigned path.",
        ],
    },
    "MOVE_CAST_ERROR": {
        "category":    "ABAP Programming Error",
        "subcategory": "Type Conflict",
        "meaning": (
            "An ABAP CAST or MOVE operation tried to convert data between incompatible types at runtime. "
            "This can happen when an object reference is cast to an incompatible class, "
            "or when a data value does not conform to the target type."
        ),
        "investigation_hints": [
            "Check whether the error is data-dependent — specific input values may trigger the incompatible cast.",
            "Check if a recent transport changed data type definitions or class hierarchies used in the program.",
            "Check if the source data comes from an external interface or RFC call that may be sending unexpected type values.",
        ],
    },
    "COMPUTE_INT_ZERODIVIDE": {
        "category":    "ABAP Programming Error",
        "subcategory": "Arithmetic Error",
        "meaning": (
            "An arithmetic division in the ABAP program used a zero value as the divisor. "
            "The program did not check for zero before performing the division. "
            "This is almost always data-dependent — specific records cause a zero divisor."
        ),
        "investigation_hints": [
            "Identify which record or data combination causes the zero divisor — check the program context in Error_Short_Text_s.",
            "Check if the same program processes other records successfully — confirms the error is data-dependent.",
            "Check if the source of the zero value is a configuration field, a database record, or a computed result.",
        ],
    },
    "CONVT_NO_NUMBER": {
        "category":    "ABAP Programming Error",
        "subcategory": "Conversion Error",
        "meaning": (
            "ABAP tried to move a character string into a numeric field but the string contains non-numeric characters. "
            "This is a data quality issue — the source data does not match the expected format of the target field."
        ),
        "investigation_hints": [
            "Identify the source field and record that contains the non-numeric value — check Error_Short_Text_s for context.",
            "Check if the data comes from user input, an RFC/IDoc interface, a file import, or a database field.",
            "Check if the same error occurs for all users of this program or only specific users/transactions — data-specific failures indicate a data quality problem.",
        ],
    },

    # ── Dynpro / GUI Errors ───────────────────────────────────────────────────
    "DYNPRO_SEND_IN_BACKGROUND": {
        "category":    "Dynpro Programming Error",
        "subcategory": "Screen in Background",
        "meaning": (
            "A background (batch) job executed a program that called a DYNPRO screen. "
            "Background programs must not call dialog screens — there is no user to interact with them. "
            "This is always a programming error or a misconfigured execution mode."
        ),
        "investigation_hints": [
            "Check whether the program was recently changed to run in background mode without removing the screen calls.",
            "Check if a new job variant or configuration routes this program to background execution that previously ran interactively.",
            "Check if a recent transport added new code paths that call screens conditionally — the background path may now reach a screen call.",
        ],
    },
    "DYNPRO_NOT_FOUND": {
        "category":    "Dynpro Programming Error",
        "subcategory": "Missing Screen",
        "meaning": (
            "The ABAP program referenced a screen (dynpro) number that does not exist in the system. "
            "The screen definition is missing from the program's screen pool."
        ),
        "investigation_hints": [
            "Check if a transport applied the ABAP program code but the screen activation failed — partial transport application is the most common cause.",
            "Check if the program and the missing screen belong to the same transport request.",
            "Check whether this affects all users of the transaction or only specific ones — universal failure confirms a missing object, not a user-specific issue.",
        ],
    },
    "CNTL_ERROR": {
        "category":    "GUI / Dynpro Error",
        "subcategory": "Control Framework",
        "meaning": (
            "The SAP GUI control framework raised an error. Custom controls (ALV grids, tree controls, HTML viewer) "
            "communicate between the frontend SAP GUI and the backend ABAP server. "
            "A mismatch between the GUI version and the SAP backend patch level is the most common cause."
        ),
        "investigation_hints": [
            "Check whether the error is specific to certain frontend hosts or affects all users — host-specific failures suggest a GUI version issue on those machines.",
            "Check the SAP GUI patch level on the affected frontend machines against the SAP backend support package level.",
            "Check if a recent backend transport or support package changed the control framework version.",
        ],
    },

    # ── Concurrency / Lock Errors ─────────────────────────────────────────────
    "LOCKED_BY_OURSELVES": {
        "category":    "Concurrency / Lock Error",
        "subcategory": "Self Deadlock",
        "meaning": (
            "The same SAP session or program tried to set a SAP enqueue lock on an object it already holds a lock on. "
            "SAP enqueue locks are not re-entrant — requesting a lock you already own causes a self-deadlock."
        ),
        "investigation_hints": [
            "Check if the same user has the same transaction open multiple times in parallel sessions.",
            "Check the lock table state — are there accumulated locks from this user that were not released?",
            "Check if the program loops and re-requests the same lock without releasing it between iterations.",
        ],
    },
    "ENQUEUE_FAIL": {
        "category":    "Concurrency / Lock Error",
        "subcategory": "Lock Failure",
        "meaning": (
            "The SAP enqueue server rejected a lock request. "
            "Possible causes: the lock table is full, the enqueue server is not responding, "
            "or another session holds a conflicting lock and the program did not implement a wait/retry."
        ),
        "investigation_hints": [
            "Check enqueue server health and lock table fill level — a full lock table causes all new lock requests to fail.",
            "Check how many locks are currently held in the system — accumulated unreleased locks fill the lock table.",
            "Check if multiple users are competing for the same business object lock simultaneously.",
            "Check if the enqueue server is on a separate host and whether that host is healthy.",
        ],
    },
    "DEADLOCK_DETECTED": {
        "category":    "Concurrency / Lock Error",
        "subcategory": "DB Deadlock",
        "meaning": (
            "The database detected a deadlock between two or more sessions that were waiting for each other's locks. "
            "The database resolved the deadlock by aborting one of the transactions. "
            "This is distinct from SAP-level enqueue locks — it is a physical database row lock deadlock."
        ),
        "investigation_hints": [
            "Check database error logs for the deadlock details — which tables and which sessions were involved.",
            "Check if concurrent batch jobs or parallel dialog users write to the same tables in conflicting lock orders.",
            "Check if the deadlock is recurring — repeated deadlocks on the same tables indicate a structural concurrency issue in the application.",
        ],
    },

    # ── Authorization Errors ──────────────────────────────────────────────────
    "NO_AUTHORITY": {
        "category":    "Authorization Error",
        "subcategory": "Missing Authorization",
        "meaning": (
            "The SAP authority check (AUTHORITY-CHECK) for a specific authorization object failed. "
            "The user lacks the required object, activity, or field value in their assigned roles/profiles."
        ),
        "investigation_hints": [
            "Check whether this affects only one user or multiple users — single-user failure suggests a missing role assignment, multi-user failure suggests a recent role or authorization object change.",
            "Check Error_Short_Text_s for the specific authorization object that failed.",
            "Check if a recent transport changed authorization object definitions or removed an authorization from a role.",
            "Check if the user's role assignments were recently changed.",
        ],
    },
    "NOT_AUTHORIZED": {
        "category":    "Authorization Error",
        "subcategory": "Security Failure",
        "meaning": (
            "An authorization check failed — similar to NO_AUTHORITY but may be raised programmatically "
            "by custom authorization logic rather than the standard AUTHORITY-CHECK statement."
        ),
        "investigation_hints": [
            "Check Error_Short_Text_s for the specific object or check that failed.",
            "Check if this affects one user or many — widespread failures suggest a systemic authorization change.",
            "Check if a recent transport changed custom authorization logic in the program.",
        ],
    },

    # ── System / Kernel Errors ────────────────────────────────────────────────
    "LOAD_PROGRAM_NOT_FOUND": {
        "category":    "Installation / System Error",
        "subcategory": "Missing Program",
        "meaning": (
            "The ABAP runtime tried to load a program that does not exist in the program library. "
            "The ABAP dictionary may have an entry but the compiled load (binary) is missing."
        ),
        "investigation_hints": [
            "Check if a transport created the ABAP source and dictionary entry but load generation failed.",
            "Check if the program was deleted — either intentionally or as part of a rollback.",
            "Check whether this is a standard SAP program or a custom program — missing standard programs suggest an incomplete installation or upgrade.",
            "Check if this is intermittent (program buffer issue) or always failing (truly missing program).",
        ],
    },
    "GENERATE_SUBPOOL_DIR_FULL": {
        "category":    "System Error",
        "subcategory": "Program Buffer",
        "meaning": (
            "The SAP program buffer's subpool directory is full. "
            "The program buffer caches compiled ABAP loads in memory for fast execution. "
            "When the directory (the index of cached programs) is full, no new programs can be loaded."
        ),
        "investigation_hints": [
            "Check program buffer fill level and hit rate (ST02 equivalent metrics).",
            "Check if a large number of programs were recently transported or activated — mass transports can flood the buffer directory.",
            "Check if this is affecting all application servers or a specific one — per-instance buffers can fill independently.",
            "Check whether the SAP instance has been running for a long time without a buffer refresh.",
        ],
    },
    "PROGRAM_BUFFER_NOT_FOUND": {
        "category":    "System Error",
        "subcategory": "Buffer Issue",
        "meaning": (
            "The compiled ABAP load for a program was not found in the program buffer and could not be loaded from the database. "
            "This can be a transient buffer miss or indicate a genuinely missing compiled load."
        ),
        "investigation_hints": [
            "Check if the program exists and is activated in the ABAP dictionary.",
            "Check if the ABAP load was inadvertently deleted or corrupted.",
            "Check if this error is transient — the ABAP load may regenerate automatically on the next access attempt.",
            "Check program buffer fill level — a completely full buffer can cause cache misses.",
        ],
    },
    "SYSTEM_CORE_DUMPED": {
        "category":    "Internal Kernel Error",
        "subcategory": "Kernel Crash",
        "meaning": (
            "The SAP kernel — a work process, gateway, or message server process — crashed and generated a core dump. "
            "This is a kernel-level crash, not an ABAP-level error. "
            "It may be caused by OS memory pressure, kernel bugs, or hardware issues."
        ),
        "investigation_hints": [
            "Check OS memory, CPU, and I/O metrics on the affected host at and before the time of the crash — resource exhaustion is the most common trigger.",
            "Check HA cluster state — kernel crashes often coincide with or immediately trigger a cluster failover or resource move.",
            "Check system logs for work process stop (Q02) and restart (Q0Q) events on the same host around the same time.",
            "Check if multiple work processes crashed simultaneously — mass WP crashes indicate a host-level issue rather than a single process bug.",
        ],
    },
    "KERNEL_PANIC": {
        "category":    "Internal Kernel Error",
        "subcategory": "Critical Kernel",
        "meaning": (
            "A kernel panic occurred — this is the most severe SAP kernel failure. "
            "The SAP instance kernel process (or the OS kernel itself) encountered an unrecoverable error. "
            "The SAP instance will typically stop responding and require a restart."
        ),
        "investigation_hints": [
            "Check OS-level kernel logs and system event logs on the affected host for the panic reason.",
            "Check HA cluster state immediately — a kernel panic almost always triggers an automatic cluster failover.",
            "Check OS memory, CPU, and hardware health metrics leading up to the panic.",
            "Check if other SAP instances or services on the same host also became unavailable at the same time.",
        ],
    },

    # ── Intentional Terminations ──────────────────────────────────────────────
    "SYSTEM_CANCELED": {
        "category":    "Intentional Termination",
        "subcategory": "User/Admin Cancel",
        "meaning": (
            "The ABAP session was cancelled — either by the user pressing Cancel/Stop, "
            "by an administrator using SM04/SM50 to cancel the work process, "
            "or by an automatic system timeout for inactive sessions."
        ),
        "investigation_hints": [
            "Check whether the cancellation was expected — dialog session timeouts are normal and not always an error.",
            "Check if a background job or a long-running dialog step was manually cancelled by an operator.",
            "Check if other error dumps (ABAP runtime errors) occurred just before the cancellation — cancellations can follow a failed recovery attempt.",
        ],
    },
    "JOB_CANCELLED": {
        "category":    "Intentional Termination",
        "subcategory": "Background Job Cancel",
        "meaning": (
            "A background job was explicitly cancelled — either by an operator in the job monitor, "
            "by a job control step in a job chain, or by the system because the job exceeded resource limits."
        ),
        "investigation_hints": [
            "Check the job log for the specific cancellation reason — operator cancellation, step failure, or resource limit.",
            "Check if other jobs in the same job chain or job group were also cancelled around the same time.",
            "Check if resource errors (memory exhaustion, timeouts) in the dump data or system logs preceded the cancellation.",
            "Determine whether this job cancellation was planned (e.g. a maintenance window) or unexpected.",
        ],
    },
}

# ── SM37 Batch Job status codes ───────────────────────────────────────────────
JOB_STATUS_LABELS: dict[str, dict] = {
    "F": {
        "label": "Finished",
        "is_failure": False,
        "description": "Job completed successfully.",
        "meaning": "All steps of the job ran to completion without error. No further investigation is required for this job.",
    },
    "S": {
        "label": "Released",
        "is_failure": False,
        "description": "Job released, waiting for scheduled start time or a free batch WP.",
        "meaning": (
            "The job has been released and is queued to start at its scheduled time or when a batch work process is available. "
            "This is a normal transitional state. If a job remains in Released state significantly past its scheduled start time, "
            "it may indicate that no batch WP is free or that the scheduled start conditions have not been met."
        ),
    },
    "P": {
        "label": "Scheduled",
        "is_failure": False,
        "description": "Job defined but not yet released.",
        "meaning": "The job has been created and scheduled but has not yet been released to run. It will not execute until it is released manually, by an event trigger, or by a predecessor job.",
    },
    "A": {
        "label": "Cancelled",
        "is_failure": True,
        "description": "Job terminated abnormally — primary failure indicator for RCA.",
        "meaning": (
            "The job was cancelled abnormally. This happens when a job step encounters a runtime error "
            "(ABAP short dump), when the system terminates the job due to resource exhaustion, "
            "or when an operator cancels it manually via SM37. "
            "In RCA context this is always the primary signal — at least one job step failed."
        ),
        "investigation_hints": [
            "Check the job spool log for the specific error message or exception that caused cancellation — it identifies the failing step and program.",
            "Look for an accompanying short dump (ST22) for the same user, program, and timestamp — ABAP runtime errors in batch always produce a dump.",
            "Identify which step within the job failed — a multi-step job may have completed several steps successfully before failing.",
            "Check whether the same job fails on repeated runs or only once — recurring failures indicate a code, data, or configuration defect; single failures may be transient.",
            "Check whether multiple jobs were cancelled in the same time window — concurrent cancellations point to a system-wide issue (resource exhaustion, DB outage) rather than a job-specific defect.",
            "Check whether the job was cancelled by an operator (manual) or by the system — SM37 job log shows who or what initiated the cancellation.",
        ],
    },
    "Z": {
        "label": "Active",
        "is_failure": False,
        "description": "Job is currently running.",
        "meaning": (
            "The job is currently executing in a batch work process. "
            "Active status is normal during execution, but a job stuck in Active state for longer than expected "
            "indicates a hang, a database lock wait, or a work process failure that left the status unreset."
        ),
        "investigation_hints": [
            "Check how long the job has been in Active state — if significantly longer than its normal runtime, it is likely hanging.",
            "Check batch work process status on the host — the WP assigned to this job may have crashed without resetting the job status.",
            "Look for database lock waits — a job stuck in Active is often blocked on an enqueue lock or a database row lock held by another session.",
            "Check OS CPU and memory metrics on the host — resource starvation can cause a batch job to appear active while making no progress.",
            "Check if other batch jobs on the same host are also stuck in Active — multi-job hangs indicate a host-level or DB-level issue.",
        ],
    },
    "Y": {
        "label": "Ready",
        "is_failure": False,
        "description": "Job is ready, waiting for a free batch work process.",
        "meaning": (
            "The job has been released and is eligible to run but cannot start because all batch work processes "
            "on the target host are currently occupied. "
            "In RCA context, a job stuck in Ready state may indicate batch WP exhaustion or that long-running jobs are blocking others."
        ),
        "investigation_hints": [
            "Check batch work process availability and count on the target host — all batch WPs may be occupied by long-running or stuck jobs.",
            "Check whether any jobs on the same host are stuck in Active state — stuck Active jobs consume a WP and prevent Ready jobs from starting.",
            "Check if the number of configured batch work processes on the host is sufficient for the workload volume.",
            "Check whether the job has a target host restriction in its scheduling definition — if the target host is overloaded, reassigning to another host may unblock it.",
        ],
    },
    "G": {
        "label": "Released (restricted)",
        "is_failure": False,
        "description": "Released with additional restrictions.",
        "meaning": (
            "The job has been released but with additional execution restrictions — for example, it is waiting for a predecessor job to finish, "
            "a specific server group to become available, or an event-based trigger condition to be met. "
            "This is a normal state; it only warrants investigation if the job is stuck in this state longer than expected."
        ),
    },
}

# ── SM21 Message Group prefixes ───────────────────────────────────────────────
# SM21 message IDs are 3 characters (e.g. AB0, BY1, D01, Q02, XI3).
# Dict keys are variable-length prefixes:
#   2-character prefixes: "AB" covers AB0, AB1, ...  |  "BY" covers BY0, BY1, ...  |  "XI" covers XI0, XI1, ...
#   1-character prefixes: "D" covers D01, D02, ...   |  "E" covers E01, E02, ...
#                         "I" covers I01, I02, ...   |  "Q" covers Q02, Q0I, Q0Q, ...
#                         "R" covers R01, R02, ...   |  "S" covers S01, S02, ...
#                         "W" covers W01, W02, ...
# Lookup uses startswith() (not a fixed character slice) so both 1- and 2-character
# prefixes are resolved correctly without listing every individual message ID.
SM21_MSG_GROUPS: dict[str, dict] = {

    "AB": {
        "category": "ABAP runtime / dumps",
        "meaning": (
            "ABAP program runtime errors leading to short dumps (ST22). "
            "AB* messages are written to SM21 whenever the ABAP runtime detects a program termination. "
            "AB0 = runtime error reported; AB1 = short dump record created in ST22."
        ),
        "investigation_hints": [
            "Look for short dump records for the same user, host, and timestamp — AB* messages always pair with a dump entry.",
            "Identify the runtime error code and the failing program from the dump record.",
            "Check whether the same program fails for multiple users or only one — multi-user failures indicate a code defect or recent transport.",
            "Check whether a transport was applied to the failing program shortly before the first AB* entry appeared.",
        ],
    },

    "BY": {
        "category": "Database",
        "meaning": (
            "Database connectivity, SQL errors, and DB failures recorded in the system log. "
            "BY0 = database error during SQL execution; BY1 = database connection could not be established."
        ),
        "investigation_hints": [
            "Check database server error logs for the specific SQL error code and the failing statement.",
            "Check OS metrics (CPU, memory, disk I/O) on the database host at the time of the error — resource exhaustion on the DB host causes SQL failures.",
            "Check network connectivity between the SAP application server host and the database host.",
            "Look for short dump records with database-category runtime errors (e.g. DBIF_*, DBSQL_*) from the same host and time window.",
            "Check whether DB errors affect all application servers or a specific one — single-server failures suggest a connectivity or routing issue.",
        ],
    },

    "D": {
        "category": "Dispatcher",
        "meaning": (
            "Dispatcher queue, work process dispatching, and request handling events. "
            "D* messages cover transaction cancellations (D01), dispatcher queue overflows, "
            "and work process assignment failures."
        ),
        "investigation_hints": [
            "Check work process availability on the affected host — dispatcher errors often follow work process exhaustion.",
            "Look for short dump records and cancelled batch jobs for the same user and time window — transaction cancellations (D01) almost always pair with a dump.",
            "Check OS CPU and memory metrics on the affected host — dispatcher queue overflows are triggered by resource pressure.",
            "Check if dispatcher errors are isolated to one host or affect multiple — multi-host failures indicate a system-wide load issue.",
        ],
    },

    "E": {
        "category": "Enqueue / update",
        "meaning": (
            "Lock table, enqueue server, and update task failures. "
            "E* messages cover enqueue server communication errors, lock table overflows, "
            "and update task terminations."
        ),
        "investigation_hints": [
            "Check enqueue server health and lock table fill level — a full lock table causes all new lock requests to fail.",
            "Check update task work process status — update failures leave data in an inconsistent state.",
            "Look for short dump records with concurrency/lock runtime errors (ENQUEUE_FAIL, DEADLOCK_DETECTED) from the same time window.",
            "Check if the enqueue server is on a dedicated host and whether that host is healthy.",
        ],
    },

    "I": {
        "category": "Info",
        "meaning": (
            "Informational system messages — not errors. "
            "I* messages record normal system events such as instance starts, stops, and configuration changes."
        ),
        "investigation_hints": [
            "I* messages are informational and do not indicate a failure by themselves.",
            "Check whether I* messages (e.g. instance start/stop) coincide with other error entries — a restart may explain why errors stopped or started.",
        ],
    },

    "R": {
        "category": "RFC / communication",
        "meaning": (
            "RFC calls, network communication, and gateway issues recorded in the system log. "
            "R* messages cover RFC connection failures, gateway errors, and remote call timeouts."
        ),
        "investigation_hints": [
            "Check whether the RFC target system or service was available and responding at the time of the R* entries.",
            "Check network stability between the calling application server host and the RFC target.",
            "Check gateway process health on the host — R* gateway errors may indicate the gateway process itself is failing.",
            "Look for short dump records with communication-category runtime errors (CALL_FUNCTION_*) from the same host and time window.",
            "Check if R* errors affect all RFC destinations or a specific one — destination-specific failures point to the target system.",
        ],
    },

    "Q": {
        "category": "Queue / qRFC",
        "meaning": (
            "Work process execution and failure events, queued RFC (qRFC) processing issues, "
            "and OS-level system call failures. "
            "Q02 = work process stopped abnormally; Q0I = OS socket/network call failed; "
            "Q0Q = work process restarted by dispatcher; Q04 = user session/network connection lost."
        ),
        "investigation_hints": [
            "Check OS memory, CPU, and network metrics on the affected host — Q* errors are frequently caused by OS-level resource pressure or network instability.",
            "Check HA cluster state at the time of Q* entries — work process crashes (Q02) often coincide with or trigger a cluster failover.",
            "Look for short dump records with kernel-category runtime errors (SYSTEM_CORE_DUMPED, KERNEL_PANIC) from the same host and time window.",
            "Check if Q* errors are isolated to one host or affect multiple — multi-host Q* failures indicate infrastructure-level issues.",
            "For Q0I (OS socket failure): check network interface errors and connectivity between hosts.",
            "For Q02/Q0Q (WP stop/restart): check whether work process crashes are recurring — repeated restarts indicate an unstable WP or kernel issue.",
        ],
    },

    "S": {
        "category": "System",
        "meaning": (
            "General system-level events including message server activity, "
            "system profile parameter changes, and CCMS monitoring threshold alerts."
        ),
        "investigation_hints": [
            "Check whether S* entries coincide with other error categories in the same time window — system events often precede or follow application failures.",
            "For message server events (MS*): check whether application servers joined or left the group, which may indicate a failover or restart.",
            "For CCMS threshold alerts (SM*): check OS resource metrics on the affected host to identify which threshold was breached.",
            "Check HA cluster state if message server topology changes are present.",
        ],
    },

    "W": {
        "category": "Work process",
        "meaning": (
            "Work process execution and failure events not covered by the Q* group. "
            "W* messages record work process state transitions, abnormal terminations, "
            "and resource exhaustion at the work process level."
        ),
        "investigation_hints": [
            "Check work process availability on the affected host at the time of W* entries.",
            "Check OS memory and CPU metrics on the host — work process failures are frequently resource-induced.",
            "Look for short dump records from the same host and time window — WP failures often produce accompanying dumps.",
            "Check if W* errors affect a single work process type (dialog, batch, update) or all types — type-specific failures narrow the root cause.",
        ],
    },

    "XI": {
        "category": "Integration (PI/XI)",
        "meaning": (
            "SAP PI/XI (Process Integration / Exchange Infrastructure) messaging and adapter issues. "
            "XI* messages cover integration engine errors, adapter communication failures, "
            "and message processing pipeline issues."
        ),
        "investigation_hints": [
            "Check the PI/XI integration engine status and message monitoring for failed or stuck messages.",
            "Check adapter connectivity to the external systems involved in the failed integration scenario.",
            "Look for RFC/communication errors (R* entries) in the same time window — PI/XI failures often involve RFC calls to backend systems.",
            "Check whether the integration failure affects a specific interface or all interfaces — scope determines whether the issue is in the adapter, the mapping, or the backend system.",
        ],
    },
}

# ── SAP NetWeaver Instance Availability ───────────────────────────────────────
# Key format: "<InstType>_<StatusBucket>"
#   InstType      : ASCS | AppServer | ERS | WebDispatcher | Unknown
#   StatusBucket  : DOWN  (covers SAPControl-RED and SAPControl-GRAY)
#                   YELLOW (covers SAPControl-YELLOW)
#                   INTERMITTENT (GREEN→non-GREEN transitions within the query window)
#
# Each entry provides:
#   category            : human-readable grouping shown in the finding
#   meaning             : short description of what this state implies for the SAP system
#   investigation_hints : ordered list of next-step actions for the SRE / BASIS team

NW_INSTANCE_RULES: dict[str, dict] = {

    # ── ASCS (Message Server + Enqueue) ─────────────────────────────────────
    "ASCS_DOWN": {
        "category": "SAP Instance Availability",
        "meaning": (
            "Message Server and Enqueue Server are unreachable. "
            "No user can log in to the SAP system and no new enqueue locks can be acquired. "
            "This is a total system outage until ASCS is recovered."
        ),
        "investigation_hints": [
            "Check whether the ASCS OS processes (enserver, msserver) are running on the host.",
            "Check OS metrics for the ASCS host — disk full or memory exhaustion can crash ASCS.",
            "If this is an HA system, check HA cluster state for the ASCS resource state — it may be failing over.",
            "Review SAP system logs at the time of the status change for kernel and Message Server messages.",
            "Check whether the ASCS instance was recently patched or restarted — planned downtime may explain the outage.",
        ],
    },
    "ASCS_YELLOW": {
        "category": "SAP Instance Availability",
        "meaning": (
            "ASCS is in a degraded state. Message Server or Enqueue may be partially functional. "
            "YELLOW often precedes a RED/GRAY transition — treat as an early-warning signal requiring immediate attention."
        ),
        "investigation_hints": [
            "Check the ASCS instance process list for stopped sub-processes.",
            "YELLOW ASCS often precedes a RED/GRAY transition — escalate investigation if it persists for more than one or two collection intervals.",
            "Check SAP system logs for any Enqueue or Message Server warnings in this time window.",
        ],
    },

    # ── Application Server (ABAP Dispatcher / ICM) ───────────────────────────
    "AppServer_DOWN": {
        "category": "SAP Instance Availability",
        "meaning": (
            "All ABAP work processes and ICM on this application server are unavailable. "
            "Dialog users logged into this server are disconnected and background jobs scheduled here cannot run. "
            "This reduces overall system capacity but does not prevent logins if other app servers are up."
        ),
        "investigation_hints": [
            "Check the instance process list for this hostname — identify which process stopped (Dispatcher, ICM, Gateway).",
            "A stopped Dispatcher disconnects all dialog users logged into this server.",
            "Check OS metrics for this host — CPU/memory/disk pressure can crash the Dispatcher.",
            "Check SAP system logs around the time of the status change for dispatcher restart events.",
            "Check HA cluster state if this is an HA-managed app server — a Pacemaker action may have stopped the instance.",
        ],
    },
    "AppServer_YELLOW": {
        "category": "SAP Instance Availability",
        "meaning": (
            "Application server is in a degraded state. "
            "If the Dispatcher process is not running, this instance is effectively down for dialog users "
            "even though SAPControl reports YELLOW rather than RED/GRAY."
        ),
        "investigation_hints": [
            "Check the instance process list for this hostname — confirm whether disp+work (Dispatcher) is Running or Stopped.",
            "YELLOW with Dispatcher running = minor degradation (e.g. ICM restart). YELLOW with Dispatcher stopped = capacity loss equivalent to RED.",
            "Check for recurring YELLOW events on this host — intermittent YELLOW can indicate OS resource contention.",
        ],
    },

    # ── Enqueue Replication Server ────────────────────────────────────────────
    "ERS_DOWN": {
        "category": "SAP Instance Availability",
        "meaning": (
            "The Enqueue Replication Server (ERS) is not running. "
            "ASCS enqueue locks are no longer being replicated to the standby node. "
            "If ASCS fails or is failed-over now, all active transaction locks will be lost, "
            "which requires users to re-start their transactions."
        ),
        "investigation_hints": [
            "ERS GRAY after a recent cluster failover is expected — check if ASCS moved to a different node and ERS has not yet restarted on the new standby host.",
            "Check HA cluster state for the ERS resource state in Pacemaker.",
            "Persistent ERS GRAY without a recent failover indicates a configuration or Pacemaker resource problem — run 'crm status' on the cluster nodes.",
            "ERS DOWN combined with ASCS also unhealthy is a high-risk state — prioritise ASCS recovery first.",
        ],
    },

    # ── Web Dispatcher ────────────────────────────────────────────────────────
    "WebDispatcher_DOWN": {
        "category": "SAP Instance Availability",
        "meaning": (
            "The SAP Web Dispatcher is not running. "
            "All HTTP/HTTPS-based access to SAP (SAP Fiori, Web GUI, portal) is unavailable. "
            "RFC-based and SAP GUI (DIAG protocol) connections bypass the Web Dispatcher and usually still work."
        ),
        "investigation_hints": [
            "Check whether the wdispmon process is running on the Web Dispatcher host.",
            "Check OS metrics for the Web Dispatcher host — resource exhaustion or a disk-full condition can crash the Web Dispatcher.",
            "Review the Web Dispatcher trace file (dev_webdisp) on the host for error messages.",
            "Check whether a load balancer or reverse proxy in front of the Web Dispatcher is also affected.",
        ],
    },

    # ── Intermittent (any instance type) ─────────────────────────────────────
    "INTERMITTENT": {
        "category": "SAP Instance Availability",
        "meaning": (
            "The instance transitioned between GREEN and a non-GREEN status more than once "
            "within the queried time window. This indicates a flapping or unstable instance "
            "rather than a persistent outage."
        ),
        "investigation_hints": [
            "Multiple GREEN↔non-GREEN transitions indicate a flapping instance — check for OS resource contention (CPU spikes, memory pressure, disk I/O saturation) at the exact transition timestamps.",
            "Correlate with SAP system log entries at the exact timestamps of each status change.",
            "Check HA cluster state — instance restarts during an HA cluster failover appear as intermittent availability changes.",
            "If the transitions correlate with batch job peaks, the instance may be resource-starved during high-load periods.",
        ],
    },


    # ── ASCS not present in query results ────────────────────────────────────
    "ASCS_NOT_SEEN": {
        "category": "SAP Instance Availability — Data Quality",
        "meaning": (
            "No ASCS instance (MessageServer + Enqueue) was found in the availability data. "
            "Possible causes: (a) the SAP system is fully down and no telemetry is being sent, "
            "(b) monitoring collection for the ASCS host is not running, "
            "(c) the KQL query used summarize or make_set aggregation — "
            "availability analysis requires one raw row per instance per collection interval "
            "with individual columns such as hostname_s, instanceNr_s, features_s, and dispstatus_s."
        ),
        "investigation_hints": [
            "Verify the KQL query returns raw rows with no aggregation (no summarize, no make_set) — availability analysis expects one row per instance per collection interval with individual columns including hostname_s, instanceNr_s, features_s, and dispstatus_s.",
            "If raw rows are present but no ASCS is found: the ASCS host may be down and not sending monitoring data — verify the ASCS VM is running.",
            "Check HA cluster state to see whether the ASCS Pacemaker resource is offline — a resource failure stops telemetry too.",
            "ASCS hosts are often on a separately named VM (e.g. a hostname containing 'scs') — confirm this host is included in the monitored scope.",
            "Check SAP system logs — if any part of the system is alive, shutdown or crash messages will indicate what happened.",
        ],
    },

    # ── Application servers not present in query results ──────────────────────
    "AppServer_NOT_SEEN": {
        "category": "SAP Instance Availability — Data Quality",
        "meaning": (
            "No application server instance was found in the availability data. "
            "Either no app server is sending monitoring data, "
            "or the KQL query used aggregation instead of returning raw per-instance rows."
        ),
        "investigation_hints": [
            "Verify the KQL query returns raw rows with no aggregation — application server rows must include a features_s column containing 'ICMAN' or 'ABAP' to be classified correctly.",
            "If ASCS is also missing: this is a complete data absence — the system may be fully down or monitoring is broadly broken across all hosts.",
            "If ASCS IS present but no app servers appear: verify that app server hostnames are included in the monitored scope.",
            "Check SAP system logs for shutdown or crash evidence if the system was recently running.",
        ],
    },

    # ── All application servers down while ASCS is healthy ────────────────────
    "AppServer_ALL_DOWN": {
        "category": "SAP Instance Availability",
        "meaning": (
            "All application server instances are offline while ASCS is still healthy. "
            "No ABAP work processes are available — dialog users cannot log on and background jobs cannot run. "
            "The SAP system is effectively offline for all business users despite ASCS being up."
        ),
        "investigation_hints": [
            "Check the instance process list for each app server hostname to identify which process stopped (Dispatcher, ICM, or Gateway).",
            "Check SAP system logs for shutdown or crash messages across all app server hosts — simultaneous failure of all app servers suggests a coordinated event.",
            "Check OS metrics for all app server hosts — a shared infrastructure problem such as storage loss or network failure can take down all instances at once.",
            "Check HA cluster state — a cluster-wide maintenance window, mass fencing, or Pacemaker action can stop all app server resources simultaneously.",
            "Check database availability — if the database is down or unreachable, SAP application servers cannot start or will crash on startup. Check HANA availability data for the same time window to confirm whether the database was up and accepting connections.",
        ],
    },

    # ── Some application servers down, system partially available ─────────────
    "AppServer_PARTIAL_DOWN": {
        "category": "SAP Instance Availability",
        "meaning": (
            "One or more application server instances are offline while others remain healthy. "
            "The SAP system is partially available — users and jobs on the affected server(s) are disconnected. "
            "The Message Server will route new logons to remaining healthy servers, "
            "but overall system capacity is reduced."
        ),
        "investigation_hints": [
            "Check the instance process list for each affected app server hostname to identify which process stopped (Dispatcher, ICM, or Gateway).",
            "Check whether the affected servers share a common characteristic — same physical host, same mount point, or same network segment — to narrow the root cause.",
            "Check SAP system logs for the affected hosts at the time of the status change.",
            "Check OS metrics for the affected hosts — CPU, memory, or disk saturation can crash the Dispatcher on specific servers.",
            "Check HA cluster state — a Pacemaker action on a specific node may explain why only certain app servers are affected.",
            "Check short dump records for the affected app server hostnames — ABAP runtime errors on the instance itself (e.g. memory exhaustion, kernel crash) can cause the Dispatcher to stop, and the dump records will identify the exact program and error that preceded the outage.",
            "Check for recent SAP kernel upgrades or OS kernel patches applied to the affected app servers — a kernel change can introduce Dispatcher instability or break the SAP-to-database network layer, causing connectivity failures specific to those servers.",
        ],
    },

    # ── Generic fallback ──────────────────────────────────────────────────────
    "Unknown_DOWN": {
        "category": "SAP Instance Availability",
        "meaning": "An SAP instance with an unrecognised features_s string is offline or in error.",
        "investigation_hints": [
            "Inspect features_s for this instance to determine its role — unknown roles may indicate a misconfigured or non-standard SAP component.",
            "Check the instance host process list and OS metrics to identify which processes stopped and whether resource exhaustion preceded the failure.",
            "Common features_s patterns to help identify the role: a value containing 'ENQREP' indicates an Enqueue Replication Server (ERS); 'WEBDISP' indicates a Web Dispatcher; 'MESSAGESERVER' or 'ENQUEUE' indicates ASCS; 'ABAP' or 'ICMAN' indicates an application server — use this to determine which known instance type this actually is.",
            "Check whether other known instances on the same host (ASCS, AppServer, ERS) also appear in the availability data as DOWN — if the same host has multiple instances failing simultaneously, an OS-level or infrastructure event on that host is the likely cause.",
            "Check SAP system logs and HA cluster state for this host at the time of the status change — shutdown, fencing, or resource stop events will identify whether this was a planned action or an unexpected failure.",
        ],
    },
}


# ── Convenience functions ──────────────────────────────────────────────────────

# SM21 group prefix registry — used internally by get_msg_group() for startswith() matching.
# The list order does not imply investigation priority; groups are independent categories.
MSG_GROUP_PREFIXES: list[str] = ["AB", "BY", "XI", "D", "Q", "E", "R", "W", "S", "I"]


def classify_runtime_error(runtime_error: str) -> dict:
    """Return category, subcategory, meaning, and investigation_hints for a runtime error code."""
    entry = RUNTIME_ERROR_CATEGORIES.get(runtime_error)
    if entry:
        return entry
    return {
        "category": "Unknown",
        "subcategory": "Not classified",
        "meaning": f"Runtime error '{runtime_error}' is not in the local SAP knowledge base.",
        "investigation_hints": [
            f"Search SAP OSS notes and documentation for runtime error '{runtime_error}'.",
            "Check Error_Short_Text_s in the dump record for a description of what triggered the termination.",
        ],
    }


def decode_job_status(status_code: str) -> dict:
    """Return full label and failure flag for an SM37 status code."""
    return JOB_STATUS_LABELS.get(status_code, {
        "label": f"Unknown ({status_code})",
        "is_failure": False,
        "description": "Status code not recognised.",
    })


def get_msg_group(msg_id: str) -> dict:
    """Return the SM21_MSG_GROUPS entry that covers this message ID.

    Matches by startswith() so both 1- and 2-character prefixes resolve correctly.
    The returned dict always includes a 'group_key' field with the matched prefix.
    Returns a safe fallback dict for unknown message IDs — never returns None.
    """
    for prefix in MSG_GROUP_PREFIXES:
        if msg_id.startswith(prefix):
            entry = dict(SM21_MSG_GROUPS[prefix])
            entry["group_key"] = prefix
            return entry
    # Unknown group — return minimal fallback
    fallback_key = msg_id[:2]
    return {
        "group_key":           fallback_key,
        "category":            "Unknown",
        "meaning":             f"SM21 message group '{fallback_key}' is not in the local knowledge base.",
        "investigation_hints": [
            f"Research message ID '{msg_id}' in SAP OSS notes or SM21 documentation.",
            "Check Description_s in the log rows for context on what this message indicates.",
        ],
    }


def classify_nw_instance(inst_type: str, status_bucket: str) -> dict:
    """Return category, meaning, and investigation_hints for an SAP instance state.

    Args:
        inst_type     : instance type string — one of ASCS, AppServer, ERS,
                        WebDispatcher, TREX, Unknown (from _instance_type()).
        status_bucket : DOWN | YELLOW | INTERMITTENT
                        The caller maps dispstatus_s to a bucket:
                          SAPControl-RED  → DOWN
                          SAPControl-GRAY → DOWN
                          SAPControl-YELLOW → YELLOW
                        Pass "INTERMITTENT" for the flapping-instance finding.

    Returns a dict with keys: category, meaning, investigation_hints.
    Never returns None.
    """
    # INTERMITTENT applies to any instance type — resolve directly
    if status_bucket == "INTERMITTENT":
        return NW_INSTANCE_RULES["INTERMITTENT"]
    key = f"{inst_type}_{status_bucket}"
    entry = NW_INSTANCE_RULES.get(key)
    if entry:
        return entry
    # Fallback for unrecognised combinations
    fallback_key = f"Unknown_{status_bucket}"
    fallback = NW_INSTANCE_RULES.get(fallback_key)
    if fallback:
        return fallback
    return {
        "category": "SAP Instance Availability",
        "meaning": f"Instance type '{inst_type}' with status bucket '{status_bucket}' is not in the local knowledge base.",
        "investigation_hints": [
            "Check features_s for this instance to determine its role.",
            "Check the instance process list for this hostname to identify the affected processes.",
        ],
    }


# ── Section-level helpers for FULL_SNAP analysis ─────────────────────────────

# Priority sections per error category — tells the handler which sections to emphasise
# when presenting results for a given RUNTIME_ERROR_CATEGORIES category.
SECTION_PRIORITY_BY_CATEGORY: dict[str, list[str]] = {
    "Resource Bottleneck":       ["IDENTITY", "SYSTEM_FIELDS", "ENVIRONMENT", "WHAT_HAPPENED"],
    "Database Error":            ["RFC_SQL_CONTEXT", "IDENTITY", "WHAT_HAPPENED", "CALL_STACK"],
    "Communication Error":       ["RFC_SQL_CONTEXT", "IDENTITY", "WHAT_HAPPENED", "ENVIRONMENT"],
    "ABAP Programming Error":    ["SOURCE_CODE", "CALL_STACK", "SELECTED_VARS", "SYSTEM_FIELDS"],
    "Dynpro Programming Error":  ["IDENTITY", "CALL_STACK", "JOB_CONTEXT", "WHAT_HAPPENED"],
    "GUI / Dynpro Error":        ["ENVIRONMENT", "IDENTITY", "WHAT_HAPPENED"],
    "Concurrency / Lock Error":  ["IDENTITY", "WHAT_HAPPENED", "SYSTEM_FIELDS", "SELECTED_VARS"],
    "Authorization Error":       ["IDENTITY", "WHAT_HAPPENED", "SELECTED_VARS"],
    "Installation / System Error": ["IDENTITY", "ENVIRONMENT", "CALL_STACK"],
    "Internal Kernel Error":     ["IDENTITY", "ENVIRONMENT", "WHAT_HAPPENED"],
    "System Error":              ["IDENTITY", "ENVIRONMENT", "WHAT_HAPPENED", "CALL_STACK"],
    "Intentional Termination":   ["JOB_CONTEXT", "IDENTITY", "WHAT_HAPPENED"],
}


def get_section_guide(section_name: str) -> dict:
    """Return purpose, key_fields, and rca_usage for a FULL_SNAP section name."""
    entry = FULL_SNAP_SECTION_GUIDE.get(section_name)
    if entry:
        return entry
    return {
        "purpose": f"Section '{section_name}' is not in the local knowledge base.",
        "key_fields": [],
        "rca_usage": "Inspect the section_text_s content directly for relevant key=value pairs.",
    }


def get_priority_sections(error_category: str) -> list[str]:
    """Return ordered list of section names most relevant for an error category.

    Falls back to a generic ordering if the category is not in SECTION_PRIORITY_BY_CATEGORY.
    """
    return SECTION_PRIORITY_BY_CATEGORY.get(
        error_category,
        ["IDENTITY", "WHAT_HAPPENED", "CALL_STACK", "SOURCE_CODE"],
    )


# ══════════════════════════════════════════════════════════════════════════════
# NEW DOMAIN KNOWLEDGE — Work Processes, SMON, Failed Updates, SWNC,
#                         tRFC/Queues, Transports
# ══════════════════════════════════════════════════════════════════════════════

# ── Work Process Type Labels (SM50 / SM66) ────────────────────────────────────
# Maps Typ_s values from ABAPGetWPTable_CL to their meaning.

WP_TYPE_LABELS: dict[str, dict] = {
    "DIA": {"label": "Dialog", "description": "Handles interactive user requests. Exhaustion = users can't work."},
    "BTC": {"label": "Background", "description": "Executes batch jobs. Exhaustion = jobs queue up."},
    "UPD": {"label": "Update V1", "description": "Synchronous database updates. Exhaustion = data loss risk."},
    "UPD2": {"label": "Update V2", "description": "Async statistical updates. Less critical than V1."},
    "SPO": {"label": "Spool", "description": "Print/spool output processing."},
    "ENQ": {"label": "Enqueue", "description": "Lock management. Usually just 1 per instance."},
}

WP_STATUS_LABELS: dict[str, dict] = {
    "Run":       {"label": "Running",   "is_busy": True,  "meaning": "Actively executing a request."},
    "Wait":      {"label": "Waiting",   "is_busy": False, "meaning": "Idle, available for new requests."},
    "Hold":      {"label": "On Hold",   "is_busy": True,  "meaning": "Paused mid-execution (e.g. waiting for RFC or GUI)."},
    "Stop":      {"label": "Stopped",   "is_busy": False, "meaning": "WP is stopped — not processing, not available."},
    "Ended":     {"label": "Ended",     "is_busy": False, "meaning": "WP terminated — will be restarted by dispatcher."},
    "Semaphore": {"label": "Semaphore", "is_busy": True,  "meaning": "Waiting on a semaphore (internal lock)."},
}

WP_REASON_FLAGS: dict[str, dict] = {
    "PRIV": {
        "severity": "warning",
        "meaning": "Private mode — WP holding extended memory exclusively. Other users can't use this WP.",
        "investigation_hints": [
            "Identify Program_s and User_s consuming the WP — they hold a large memory context.",
            "If multiple WPs are in PRIV, the system is at risk of WP exhaustion.",
            "Check SMON HEAPSUMKB_d for total heap usage at the same time.",
        ],
    },
}

WP_THRESHOLDS: dict[str, int] = {
    "PRIV_WARNING": 2,        # more than 2 PRIV WPs = warning
    "PRIV_CRITICAL": 5,       # more than 5 = critical
    "ERR_RESTART_WARNING": 1, # Err_s > 0 means WP has been restarted
}


# ── CPU Attribution: Thresholds & Computation ─────────────────────────────────
# CPU attribution is handled programmatically by the work_processes analyzer:
#   - parse_cpu_seconds()       → parse Cpu_s format
#   - compute_wp_cpu_deltas()   → per-WP CPU delta with reliability flags
#   - rank_programs_by_cpu()    → ranked list per WP type (BTC, DIA, UPD)
#
# The analyzer automatically detects CPU hogs (BTC_CPU_HOG, DIA_CPU_HOG, etc.)
# and returns investigation_hints pointing to BatchJobs_CL for cross-reference.
#
# KEY DATA SOURCE LIMITATIONS (for reference):
#   SMON_CL  → system-level CPU % only (CPU_CONS_d). NO per-program breakdown.
#   SWNC_CL  → task-type totals only. NO per-program CPU.
#   ABAPGetWPTable_CL → THE source for per-program CPU via Cpu_s delta technique.
# Used by the work_processes analyzer to detect CPU hogs per WP type.

CPU_ATTRIBUTION_THRESHOLDS: dict[str, int | float] = {
    "SAME_PROGRAM_WP_COUNT": 3,   # ≥3 WPs running same program = anomaly
    "CPU_DOMINANCE_PCT": 60,      # one program consuming >60% of type's CPU = hog
    "MIN_SNAPSHOTS_FOR_DELTA": 2, # need ≥2 snapshots per WP for meaningful delta
    "CONSECUTIVE_SNAPSHOT_GAP_SEC": 180,  # max gap between snapshots to count as consecutive (3 min)
    "CPU_BOUND_EFFICIENCY": 0.7,  # efficiency ≥0.7 → program is CPU-bound
    "IO_BOUND_EFFICIENCY": 0.2,   # efficiency ≤0.2 → program is I/O or wait-bound
    "LONG_RUNNING_REQUEST_SEC": 300,  # Time_s ≥300s → flag as long-running request
}

# WP type reliability for CPU attribution (referenced by compute_wp_cpu_deltas)
_WP_CPU_RELIABILITY: dict[str, dict] = {
    "BTC": {
        "default_reliable": True,
        "reason": "BTC WP is dedicated to one batch job — Cpu_s delta = that program's CPU.",
    },
    "DIA": {
        "default_reliable": False,
        "reason": (
            "DIA WPs handle many short-lived dialog steps. Cpu_s delta is a mix of "
            "all programs that ran on this WP between snapshots."
        ),
        "exception": (
            "Reliable IF the same Program_s appears on the same DIA WP (No_d) across "
            "≥2 consecutive snapshots — indicates a long-running request (>1 min)."
        ),
    },
    "UPD": {
        "default_reliable": True,
        "reason": "UPD WPs process one update task at a time — similar to BTC.",
    },
    "UP2": {
        "default_reliable": True,
        "reason": "UP2 (Update-2) WPs process one deferred update at a time.",
    },
    "SPO": {
        "default_reliable": True,
        "reason": "SPO (Spool) WPs process one spool request at a time.",
    },
}


def parse_cpu_seconds(cpu_str: str) -> int | None:
    """Parse ABAPGetWPTable Cpu_s format 'H:MM:SS' or 'H:M:SS' into total seconds.

    Returns None if the format is unrecognizable.

    Examples:
        '0:00:00' → 0
        '1:23:45' → 5025
        '12:05:03' → 43503
    """
    if not cpu_str or not isinstance(cpu_str, str):
        return None
    cpu_str = cpu_str.strip()
    if not cpu_str:
        return None
    # Try H:MM:SS or H:M:SS or HH:MM:SS
    import re
    m = re.match(r"^(\d+):(\d{1,2}):(\d{2})$", cpu_str)
    if not m:
        return None
    hours, minutes, seconds = int(m.group(1)), int(m.group(2)), int(m.group(3))
    return hours * 3600 + minutes * 60 + seconds


def compute_wp_cpu_deltas(rows: list[dict]) -> list[dict]:
    """Compute CPU delta per work process from ABAPGetWPTable_CL rows.

    Groups rows by (No_d, hostname_s) — each unique WP.
    For each WP, computes max(Cpu_s) - min(Cpu_s) = CPU consumed during the window.
    Also computes CPU efficiency (cpu_delta / wall_clock_delta) and tracks
    max request runtime from Time_s.

    Args:
        rows: Raw rows from SapNetweaver_ABAPGetWPTable_CL with at least:
              No_d, hostname_s, Typ_s, Program_s, Cpu_s, TimeGenerated
              Optional: Time_s (request elapsed seconds)

    Returns:
        List of dicts, one per WP that had a computable delta:
        [
            {
                "No_d": 13, "hostname_s": "vchaa01l0c",
                "Program_s": "ZBAD_REPORT", "Typ_s": "BTC",
                "cpu_delta_sec": 560, "snapshots": 8,
                "min_cpu_sec": 100, "max_cpu_sec": 660,
                "wall_clock_delta_sec": 600,
                "cpu_efficiency": 0.93,
                "cpu_bound": True,
                "max_request_runtime_sec": 580,
                "reliable": True,
                "reliability_note": "BTC WP dedicated to one batch job"
            },
            ...
        ]
    """
    from collections import defaultdict
    from datetime import datetime

    # Group rows by unique WP identifier: (No_d, hostname_s)
    wp_groups: dict[tuple, list[dict]] = defaultdict(list)
    for row in rows:
        no_d = row.get("No_d") or row.get("No_d")
        hostname = str(row.get("hostname_s", "")).strip()
        if no_d is None or not hostname:
            continue
        try:
            wp_key = (int(float(no_d)), hostname)
        except (TypeError, ValueError):
            continue
        wp_groups[wp_key].append(row)

    max_gap = CPU_ATTRIBUTION_THRESHOLDS["CONSECUTIVE_SNAPSHOT_GAP_SEC"]
    cpu_bound_thresh = CPU_ATTRIBUTION_THRESHOLDS["CPU_BOUND_EFFICIENCY"]
    io_bound_thresh = CPU_ATTRIBUTION_THRESHOLDS["IO_BOUND_EFFICIENCY"]
    results: list[dict] = []

    for (no_d, hostname), wp_rows in wp_groups.items():
        # Parse Cpu_s and Time_s for each row, pair with timestamp
        parsed: list[tuple[int, str, str]] = []  # (cpu_sec, program, timestamp_str)
        time_s_values: list[int] = []
        for r in wp_rows:
            cpu_sec = parse_cpu_seconds(str(r.get("Cpu_s", "")))
            if cpu_sec is None:
                continue
            program = str(r.get("Program_s", "")).strip()
            ts = str(r.get("TimeGenerated", "")).strip()
            parsed.append((cpu_sec, program, ts))
            # Parse Time_s (request elapsed seconds)
            time_s_raw = str(r.get("Time_s", "")).strip()
            if time_s_raw:
                try:
                    time_s_values.append(int(float(time_s_raw)))
                except (ValueError, TypeError):
                    pass

        if len(parsed) < 1:
            continue

        # Sort by timestamp for consecutive-snapshot analysis
        parsed.sort(key=lambda x: x[2])

        cpu_values = [p[0] for p in parsed]
        min_cpu = min(cpu_values)
        max_cpu = max(cpu_values)
        delta = max_cpu - min_cpu

        # Compute wall-clock delta from timestamps
        wall_clock_delta: float | None = None
        cpu_efficiency: float | None = None
        is_cpu_bound: bool | None = None
        if len(parsed) >= 2:
            try:
                ts_first = datetime.fromisoformat(parsed[0][2].replace("Z", "+00:00"))
                ts_last = datetime.fromisoformat(parsed[-1][2].replace("Z", "+00:00"))
                wc = abs((ts_last - ts_first).total_seconds())
                if wc > 0:
                    wall_clock_delta = wc
                    cpu_efficiency = round(delta / wc, 3)
                    if cpu_efficiency >= cpu_bound_thresh:
                        is_cpu_bound = True
                    elif cpu_efficiency <= io_bound_thresh:
                        is_cpu_bound = False
            except (ValueError, TypeError):
                pass

        max_request_runtime = max(time_s_values) if time_s_values else None

        # Determine the dominant program (most frequent in running snapshots)
        from collections import Counter
        program_counts = Counter(p[1] for p in parsed if p[1])
        dominant_program = program_counts.most_common(1)[0][0] if program_counts else ""

        typ = str(wp_rows[0].get("Typ_s", "")).strip()

        # Reliability assessment
        type_info = _WP_CPU_RELIABILITY.get(typ, {
            "default_reliable": False,
            "reason": f"Unknown WP type '{typ}' — reliability unknown.",
        })
        reliable = type_info["default_reliable"]
        reliability_note = type_info["reason"]

        # DIA exception check: same Program_s across consecutive snapshots
        if typ == "DIA" and not reliable and len(parsed) >= 2:
            consecutive_same_count = _count_consecutive_same_program(parsed, max_gap)
            if consecutive_same_count >= 2:
                reliable = True
                reliability_note = (
                    f"DIA exception: same program '{dominant_program}' persisted on WP #{no_d} "
                    f"across {consecutive_same_count} consecutive snapshots — long-running request."
                )

        result_entry: dict = {
            "No_d": no_d,
            "hostname_s": hostname,
            "Program_s": dominant_program,
            "Typ_s": typ,
            "cpu_delta_sec": delta,
            "snapshots": len(parsed),
            "min_cpu_sec": min_cpu,
            "max_cpu_sec": max_cpu,
            "reliable": reliable,
            "reliability_note": reliability_note,
        }
        if wall_clock_delta is not None:
            result_entry["wall_clock_delta_sec"] = round(wall_clock_delta, 1)
        if cpu_efficiency is not None:
            result_entry["cpu_efficiency"] = cpu_efficiency
        if is_cpu_bound is not None:
            result_entry["cpu_bound"] = is_cpu_bound
        if max_request_runtime is not None:
            result_entry["max_request_runtime_sec"] = max_request_runtime

        results.append(result_entry)

    return results


def _count_consecutive_same_program(
    parsed: list[tuple[int, str, str]], max_gap_sec: int
) -> int:
    """Count the longest run of consecutive snapshots with the same Program_s.

    Args:
        parsed: Sorted list of (cpu_sec, program, timestamp_str) tuples.
        max_gap_sec: Max seconds between snapshots to count as consecutive.

    Returns:
        Length of the longest consecutive run with the same program.
    """
    from datetime import datetime

    if len(parsed) < 2:
        return len(parsed)

    best_run = 1
    current_run = 1
    current_program = parsed[0][1]

    for i in range(1, len(parsed)):
        prev_program = parsed[i - 1][1]
        curr_program = parsed[i][1]

        # Check program match
        if curr_program and curr_program == prev_program:
            # Check time gap
            try:
                ts_prev = datetime.fromisoformat(parsed[i - 1][2].replace("Z", "+00:00"))
                ts_curr = datetime.fromisoformat(parsed[i][2].replace("Z", "+00:00"))
                gap = abs((ts_curr - ts_prev).total_seconds())
                if gap <= max_gap_sec:
                    current_run += 1
                else:
                    current_run = 1
                    current_program = curr_program
            except (ValueError, TypeError):
                # Can't parse timestamps — assume consecutive
                current_run += 1
        else:
            current_run = 1
            current_program = curr_program

        best_run = max(best_run, current_run)

    return best_run


def rank_programs_by_cpu(
    deltas: list[dict],
    wall_clock_sec: float | None = None,
    core_count: int | None = None,
) -> dict[str, list[dict]]:
    """Rank programs by CPU consumption, segregated by WP type.

    Takes the output of compute_wp_cpu_deltas() and produces a per-type ranking.
    Each type's cpu_pct is calculated within that type's total CPU delta.
    When wall_clock_sec and core_count are provided, also computes server_cpu_pct
    (what % of total server CPU capacity this program consumed).

    Args:
        deltas: Output from compute_wp_cpu_deltas().
        wall_clock_sec: Elapsed wall-clock seconds of the observation window.
        core_count: Number of CPU cores on the host.

    Returns:
        Dict keyed by Typ_s, each containing a ranked list:
        {
            "BTC": [
                {"Program_s": "ZBAD_REPORT", "total_cpu_sec": 2240, "wp_count": 4,
                 "cpu_pct": 83.2, "server_cpu_pct": 93.3, "reliable": True, ...},
            ],
            ...
        }
    """
    from collections import defaultdict

    can_compute_server_pct = (
        wall_clock_sec is not None and core_count is not None
        and wall_clock_sec > 0 and core_count > 0
    )
    total_capacity = (wall_clock_sec * core_count) if can_compute_server_pct else 0.0

    # Group deltas by (Typ_s, Program_s)
    type_program: dict[str, dict[str, dict]] = defaultdict(lambda: defaultdict(lambda: {
        "total_cpu_sec": 0, "wp_count": 0, "reliable_count": 0,
        "unreliable_count": 0, "reliability_notes": [],
    }))

    for d in deltas:
        typ = d["Typ_s"]
        prog = d["Program_s"]
        if not prog:
            continue
        entry = type_program[typ][prog]
        entry["total_cpu_sec"] += d["cpu_delta_sec"]
        entry["wp_count"] += 1
        if d["reliable"]:
            entry["reliable_count"] += 1
        else:
            entry["unreliable_count"] += 1
        if d["reliability_note"] not in entry["reliability_notes"]:
            entry["reliability_notes"].append(d["reliability_note"])

    # Build ranked lists per type
    result: dict[str, list[dict]] = {}
    for typ, programs in sorted(type_program.items()):
        type_total = sum(p["total_cpu_sec"] for p in programs.values())
        ranked: list[dict] = []
        for prog, info in programs.items():
            cpu_pct = round(info["total_cpu_sec"] / type_total * 100, 1) if type_total > 0 else 0.0
            server_cpu_pct = (
                round(info["total_cpu_sec"] / total_capacity * 100, 1)
                if can_compute_server_pct else None
            )
            # Overall reliability: reliable only if ALL WPs for this program were reliable
            all_reliable = info["unreliable_count"] == 0 and info["reliable_count"] > 0
            ranked.append({
                "Program_s": prog,
                "total_cpu_sec": info["total_cpu_sec"],
                "wp_count": info["wp_count"],
                "cpu_pct": cpu_pct,
                "server_cpu_pct": server_cpu_pct,
                "reliable": all_reliable,
                "reliability_note": (
                    info["reliability_notes"][0] if len(info["reliability_notes"]) == 1
                    else f"{info['reliable_count']} reliable, {info['unreliable_count']} unreliable WPs"
                ),
            })
        ranked.sort(key=lambda x: x["total_cpu_sec"], reverse=True)
        result[typ] = ranked

    return result


def compute_wp_type_server_cpu(
    deltas: list[dict],
    wall_clock_sec: float,
    core_count: int,
) -> dict[str, dict]:
    """Compute per-WP-type and total server CPU % from WP CPU deltas.

    Args:
        deltas: Output from compute_wp_cpu_deltas().
        wall_clock_sec: Elapsed seconds of the observation window.
        core_count: Number of CPU cores on the host.

    Returns:
        {
            "BTC": {"total_cpu_sec": 2075, "server_cpu_pct": 86.5, "wp_count": 4},
            "DIA": {"total_cpu_sec": 120,  "server_cpu_pct": 5.0,  "wp_count": 2},
            "_all_wp": {"total_cpu_sec": 2195, "server_cpu_pct": 91.5, "wp_count": 6},
            "_capacity": {"wall_clock_sec": 600, "core_count": 4, "total_cpu_capacity_sec": 2400},
        }
    """
    from collections import defaultdict

    if wall_clock_sec <= 0 or core_count <= 0:
        return {}

    total_capacity = wall_clock_sec * core_count

    type_agg: dict[str, dict] = defaultdict(lambda: {"total_cpu_sec": 0, "wp_count": 0})
    for d in deltas:
        entry = type_agg[d["Typ_s"]]
        entry["total_cpu_sec"] += d["cpu_delta_sec"]
        entry["wp_count"] += 1

    result: dict[str, dict] = {}
    all_cpu = 0
    all_wps = 0
    for typ, info in sorted(type_agg.items()):
        result[typ] = {
            "total_cpu_sec": info["total_cpu_sec"],
            "server_cpu_pct": round(info["total_cpu_sec"] / total_capacity * 100, 1),
            "wp_count": info["wp_count"],
        }
        all_cpu += info["total_cpu_sec"]
        all_wps += info["wp_count"]

    result["_all_wp"] = {
        "total_cpu_sec": all_cpu,
        "server_cpu_pct": round(all_cpu / total_capacity * 100, 1),
        "wp_count": all_wps,
    }
    result["_capacity"] = {
        "wall_clock_sec": round(wall_clock_sec, 1),
        "core_count": core_count,
        "total_cpu_capacity_sec": round(total_capacity, 1),
    }
    return result


# ── SMON Metric Thresholds (System Monitor) ──────────────────────────────────
# Each entry defines when a metric value is warning/critical, what the metric
# means in SAP context, and what to investigate when the threshold is breached.
# "direction" = "above" (default) means value > threshold is bad.
#               "below" means value < threshold is bad (e.g. free memory %).

SMON_METRIC_THRESHOLDS: dict[str, dict] = {
    "CPU_CONS_d": {
        "warning": 80, "critical": 95,
        "direction": "above",
        "meaning": "CPU consumption % across all cores.",
        "investigation_hints": {
            "warning": [
                "Identify which programs consume the most CPU — query ABAPGetWPTable_CL with "
                "analysis_type='workprocess_status' over the spike window. The analyzer computes "
                "CPU deltas per WP and ranks programs by actual CPU consumed, segregated by WP type.",
                "Check BTC (batch) WP count — sudden increase in running BTC WPs often indicates runaway batch jobs.",
            ],
            "critical": [
                "CPU saturation causes TIME_OUT dumps and dialog queue buildup (DIAQ_d).",
                "Query ABAPGetWPTable_CL with analysis_type='workprocess_status' over the spike window — "
                "the analyzer automatically ranks programs by CPU consumed and flags CPU hogs (BTC_CPU_HOG).",
                "Check for runaway batch jobs: multiple BTC WPs running the same Program_s = likely culprit.",
            ],
        },
    },
    "FREE_MEM_PERC_d": {
        "warning": 20, "critical": 10,
        "direction": "below",
        "meaning": "Free physical memory percentage.",
        "investigation_hints": {
            "warning": ["Check HEAPSUMKB_d for heap consumed by PRIV-mode WPs.",
                        "Check PAGE_IN_PERC_d / PAGE_OUT_PERC_d — if >0, system is swapping."],
            "critical": ["Memory exhaustion imminent — TSV_TNEW_PAGE_ALLOC_FAILED dumps likely.",
                         "Identify which users/programs consume the most memory."],
        },
    },
    "PRIVWPNO_d": {
        "warning": 2, "critical": 5,
        "direction": "above",
        "meaning": "Number of work processes in PRIV (private memory) mode.",
        "investigation_hints": {
            "warning": ["Identify PRIV users/programs in ABAPGetWPTable_CL."],
            "critical": ["WP exhaustion risk — PRIV WPs cannot serve other users.",
                         "Cross-reference with DIAQ_d — if both elevated, system stall imminent."],
        },
    },
    "DIAQ_d": {
        "warning": 1, "critical": 10,
        "direction": "above",
        "meaning": "Dialog queue depth — requests waiting for a dialog WP.",
        "investigation_hints": {
            "warning": ["Users are experiencing wait times. Check WP availability."],
            "critical": ["System stall — all dialog WPs consumed.",
                         "Check ABAPGetWPTable_CL for what programs hold WPs."],
        },
    },
    "UPDQ_d": {
        "warning": 1, "critical": 10,
        "direction": "above",
        "meaning": "Update queue depth — pending V1/V2 updates waiting for an update WP.",
        "investigation_hints": {
            "warning": ["Check update WP availability — SM13 failures may follow."],
            "critical": ["Update processing backed up — data consistency at risk."],
        },
    },
    "ENQQ_d": {
        "warning": 1, "critical": 5,
        "direction": "above",
        "meaning": "Enqueue queue depth — lock requests waiting for enqueue server.",
        "investigation_hints": {
            "warning": ["Enqueue server is slow. Check EnqGetStatistic_CL for lock table fill."],
            "critical": ["Lock request backlog — transactions will fail with ENQUEUE_FAIL."],
        },
    },
    "STEAL_TIME_d": {
        "warning": 5, "critical": 15,
        "direction": "above",
        "meaning": "CPU steal time % — time stolen by hypervisor from this VM.",
        "investigation_hints": {
            "warning": ["VM competing for CPU with co-tenants. Consider VM resize."],
            "critical": ["Severe hypervisor contention — application performance impacted."],
        },
    },
    "PAGE_IN_PERC_d": {
        "warning": 0.01, "critical": 1,
        "direction": "above",
        "meaning": "Paging in rate — any value > 0 means OS is reading from swap.",
        "investigation_hints": {
            "warning": ["Memory pressure causing swap reads — performance degraded."],
            "critical": ["Heavy swapping — all operations significantly slowed."],
        },
    },
    "PAGE_OUT_PERC_d": {
        "warning": 0.01, "critical": 1,
        "direction": "above",
        "meaning": "Paging out rate — any value > 0 means OS is writing to swap.",
        "investigation_hints": {
            "warning": ["Memory pressure causing swap writes — performance degraded."],
            "critical": ["Heavy swapping — all operations significantly slowed."],
        },
    },
    "DIAAVG60_d": {
        "warning": 1000, "critical": 3000,
        "direction": "above",
        "meaning": "Average dialog response time over last 60 seconds (ms).",
        "investigation_hints": {
            "warning": ["User experience degraded. Check DB time and CPU time breakdown."],
            "critical": ["Dialog response time > 3 seconds — users effectively blocked.",
                         "Check SWNC_CL for response time component breakdown."],
        },
    },
}


def classify_smon_metric(metric_name: str, value: float) -> dict:
    """Classify a single SMON metric value against thresholds.

    Args:
        metric_name: Column name from SMON_CL (e.g. 'CPU_CONS_d').
        value:       The numeric value to classify.

    Returns dict with: severity ('normal'|'warning'|'critical'), meaning, investigation_hints.
    """
    entry = SMON_METRIC_THRESHOLDS.get(metric_name)
    if not entry:
        return {"severity": "normal", "meaning": f"No threshold defined for {metric_name}.", "investigation_hints": []}

    direction = entry.get("direction", "above")
    if direction == "below":
        # Lower is worse (e.g. FREE_MEM_PERC_d)
        if value <= entry["critical"]:
            severity = "critical"
        elif value <= entry["warning"]:
            severity = "warning"
        else:
            severity = "normal"
    else:
        # Higher is worse (default — e.g. CPU_CONS_d)
        if value >= entry["critical"]:
            severity = "critical"
        elif value >= entry["warning"]:
            severity = "warning"
        else:
            severity = "normal"

    return {
        "severity": severity,
        "meaning": entry["meaning"],
        "investigation_hints": entry.get("investigation_hints", {}).get(severity, []),
    }


# ── Failed Update State Labels (SM13) ────────────────────────────────────────
# Maps VBSTATE_s values from FailedUpdates_CL.

FAILED_UPDATE_STATES: dict[str, dict] = {
    "0": {"label": "Initial",    "is_failure": False, "meaning": "Update created, not yet processed."},
    "1": {"label": "Error",      "is_failure": True,  "meaning": "Update terminated with error. Data NOT committed.",
          "investigation_hints": ["Check ST22 for a dump with matching timestamp and program.",
                                  "Check SM21 for E* (enqueue/update) messages at this time."]},
    "2": {"label": "Success",    "is_failure": False, "meaning": "Update completed successfully."},
    "3": {"label": "In Process", "is_failure": False, "meaning": "Update currently running."},
    "4": {"label": "Terminated", "is_failure": True,  "meaning": "Update was forcibly terminated.",
          "investigation_hints": ["Check if an admin cancelled this update in SM13.",
                                  "Check if the update WP crashed — look for Q02 in SM21."]},
    "5": {"label": "Retry",     "is_failure": True,  "meaning": "Update failed and is queued for retry."},
    "6": {"label": "Restarted",  "is_failure": False, "meaning": "Update restarted after failure — now succeeded."},
}

UPDATE_CONTEXT_LABELS: dict[str, dict] = {
    "V": {"label": "V1 Update (sync)",  "meaning": "Synchronous update — data consistency depends on this."},
    "W": {"label": "V2 Update (async)", "meaning": "Asynchronous statistical update — less critical."},
    "B": {"label": "Background",        "meaning": "Update triggered from a background job."},
    "L": {"label": "Local Update",      "meaning": "Local update — processed on the same app server."},
    "E": {"label": "Error Context",     "meaning": "Error state context record."},
    "R": {"label": "Restarted",         "meaning": "Update was restarted after failure."},
}


def classify_update_state(state: str) -> dict:
    """Classify an SM13 update state code. Returns label, is_failure, meaning, hints."""
    return FAILED_UPDATE_STATES.get(state, {
        "label": f"Unknown ({state})", "is_failure": False,
        "meaning": f"Update state '{state}' is not in the local knowledge base.",
    })


def classify_update_context(ctx: str) -> dict:
    """Classify an SM13 update context code (VBCONTEXT_s)."""
    # VBCONTEXT_s may contain surrounding characters like *V* — extract the letter
    clean = ctx.strip("* ") if ctx else ""
    return UPDATE_CONTEXT_LABELS.get(clean, {
        "label": f"Unknown ({ctx})", "meaning": f"Update context '{ctx}' is not in the local knowledge base.",
    })


# ── Workload Statistics — Task Types and Response Time Components (ST03N) ─────

WORKLOAD_TASK_TYPES: dict[str, dict] = {
    "DIALOG":      {"label": "Dialog",      "meaning": "Interactive user requests. SLA-critical.", "sla_threshold_ms": 1000},
    "BACKGROUND":  {"label": "Background",  "meaning": "Batch job processing.", "sla_threshold_ms": None},
    "UPDATE":      {"label": "Update V1",   "meaning": "Synchronous database updates."},
    "UPDATE2":     {"label": "Update V2",   "meaning": "Asynchronous statistical updates."},
    "RFC":         {"label": "RFC",         "meaning": "Remote function calls from/to other systems."},
    "SPOOL":       {"label": "Spool",       "meaning": "Print/output processing."},
    "BUFFER_SYNC": {"label": "Buffer Sync", "meaning": "Table buffer sync between app servers."},
}

RESPONSE_TIME_COMPONENTS: dict[str, dict] = {
    "db":         {"label": "Database",      "field": "ST03_DB_Time_d",         "high_threshold": 0.6,
                   "meaning": "Time spent waiting for database (HANA). High = DB-bound.",
                   "investigation_hints": ["Check HANA LoadHistory_CL for DB resource pressure.",
                                           "High sequential reads vs direct reads suggests missing indexes."]},
    "cpu":        {"label": "CPU/Processing","field": "ST03_CPU_Time_d",        "high_threshold": 0.4,
                   "meaning": "ABAP CPU processing time.",
                   "investigation_hints": ["Application code is CPU-intensive. Check for inefficient ABAP loops."]},
    "queue":      {"label": "Queue/Wait",    "field": "ST03_Queue_Time_d",      "high_threshold": 0.01,
                   "meaning": "Time waiting in dispatcher queue for a free WP.",
                   "investigation_hints": ["WP shortage. Check SMON DIAQ_d and WP counts.",
                                           "Consider adding more dialog WPs or app servers."]},
    "rollwait":   {"label": "Roll-Wait",     "field": "ST03_RollWait_Time_d",   "high_threshold": 0.3,
                   "meaning": "Time waiting for RFC responses, GUI roundtrips, or enqueue operations.",
                   "investigation_hints": ["Check RFC destinations for high latency.",
                                           "Check network between app server and target systems."]},
    "processing": {"label": "Processing",    "field": "ST03_Processing_Time_d", "high_threshold": 0.4,
                   "meaning": "ABAP application processing (non-DB, non-CPU kernel)."},
}


def classify_task_type(task_type: str) -> dict:
    """Classify a workload task type name. Returns label, meaning, SLA threshold."""
    return WORKLOAD_TASK_TYPES.get(task_type, {
        "label": task_type, "meaning": f"Task type '{task_type}' is not in the local knowledge base.",
    })


def classify_response_component(component: str, fraction: float) -> dict:
    """Classify a response time component by its fraction of total response time.

    Args:
        component: One of 'db', 'cpu', 'queue', 'rollwait', 'processing'.
        fraction:  The fraction (0.0–1.0) this component represents.

    Returns: label, is_dominant, meaning, investigation_hints.
    """
    entry = RESPONSE_TIME_COMPONENTS.get(component)
    if not entry:
        return {"label": component, "is_dominant": False, "meaning": "Unknown component."}
    is_dominant = fraction >= entry.get("high_threshold", 1.0)
    result = {
        "label": entry["label"],
        "is_dominant": is_dominant,
        "meaning": entry["meaning"],
        "fraction": round(fraction, 3),
    }
    if is_dominant:
        result["investigation_hints"] = entry.get("investigation_hints", [])
    return result


# ── tRFC State Labels (SM58) ─────────────────────────────────────────────────

TRFC_STATE_LABELS: dict[str, dict] = {
    "SYSFAIL":  {"label": "System Failure", "is_failure": True,
                 "meaning": "Target system returned a system-level error.",
                 "investigation_hints": ["Check if target system was available at the time.",
                                         "Check target system SM21 for crash/error messages."]},
    "CPICERR":  {"label": "CPIC Error", "is_failure": True,
                 "meaning": "CPIC communication error — network issue or target unreachable.",
                 "investigation_hints": ["Check network connectivity to target system.",
                                         "Check if target SAP gateway was running."]},
    "RECORDED": {"label": "Recorded", "is_failure": False,
                 "meaning": "tRFC recorded, waiting to be sent. Normal transitional state."},
    "EXECUTED": {"label": "Executed", "is_failure": False,
                 "meaning": "Successfully executed on target system."},
}

QUEUE_DEPTH_THRESHOLDS: dict[str, float] = {
    "warning": 100,
    "critical": 1000,
    "age_warning_hours": 4,
    "age_critical_hours": 24,
}


def classify_trfc_state(state: str) -> dict:
    """Classify a tRFC state code from SM58. Returns label, is_failure, meaning, hints."""
    return TRFC_STATE_LABELS.get(state, {
        "label": f"Unknown ({state})", "is_failure": False,
        "meaning": f"tRFC state '{state}' is not in the local knowledge base.",
    })


def classify_queue_depth(depth: float) -> str:
    """Classify a queue depth value. Returns 'critical', 'warning', or 'normal'."""
    if depth >= QUEUE_DEPTH_THRESHOLDS["critical"]:
        return "critical"
    if depth >= QUEUE_DEPTH_THRESHOLDS["warning"]:
        return "warning"
    return "normal"


# ── Transport Status / Function / Object Labels (STMS) ───────────────────────

TRANSPORT_STATUS_LABELS: dict[str, dict] = {
    "R": {"label": "Released",        "meaning": "Transport released and importable."},
    "D": {"label": "Modifiable",      "meaning": "Still being modified. Not yet released."},
    "L": {"label": "Not Released",    "meaning": "Locked — cannot be imported."},
    "O": {"label": "Release Started", "meaning": "Release process initiated but not complete."},
    "N": {"label": "Not Importable",  "meaning": "Cannot be imported — may be rejected or incompatible."},
}

TRANSPORT_FUNCTION_LABELS: dict[str, dict] = {
    "K": {"label": "Workbench", "meaning": "Code changes — programs, classes, function modules. Higher risk.",
          "investigation_hints": ["Code changes can introduce new dumps, performance issues, or functional errors."]},
    "W": {"label": "Customizing", "meaning": "Configuration changes — business rules, parameters.",
          "investigation_hints": ["Config changes can alter business logic behavior."]},
    "T": {"label": "Transport of Copies", "meaning": "Copy of objects — typically for testing."},
    "D": {"label": "Delivery", "meaning": "SAP standard delivery — support packs, notes, patches.",
          "investigation_hints": ["SAP patches can change standard program behavior. Check SAP note for known issues."]},
}

TRANSPORT_OBJECT_TYPES: dict[str, dict] = {
    "CLAS": {"label": "Class",           "is_code": True},
    "PROG": {"label": "Program",         "is_code": True},
    "FUNC": {"label": "Function Module", "is_code": True},
    "FUGR": {"label": "Function Group",  "is_code": True},
    "TABD": {"label": "Table Definition","is_code": False},
    "DOMA": {"label": "Domain",          "is_code": False},
    "DTEL": {"label": "Data Element",    "is_code": False},
    "VIEW": {"label": "View",            "is_code": False},
    "ENQU": {"label": "Lock Object",     "is_code": False},
    "MSAG": {"label": "Message Class",   "is_code": False},
    "TTYP": {"label": "Table Type",      "is_code": False},
    "XSLT": {"label": "XSLT Program",   "is_code": True},
}


def classify_transport_status(status: str) -> dict:
    """Classify a transport request status code."""
    return TRANSPORT_STATUS_LABELS.get(status, {
        "label": f"Unknown ({status})", "meaning": f"Transport status '{status}' is not in the local knowledge base.",
    })


def classify_transport_function(func: str) -> dict:
    """Classify a transport function type code (K=Workbench, W=Customizing, etc.)."""
    return TRANSPORT_FUNCTION_LABELS.get(func, {
        "label": f"Unknown ({func})", "meaning": f"Transport function '{func}' is not in the local knowledge base.",
    })


def classify_transport_object(obj_type: str) -> dict:
    """Classify a transport object type (CLAS, PROG, FUNC, etc.).

    Returns: label, is_code (True for code objects, False for config/dictionary).
    """
    return TRANSPORT_OBJECT_TYPES.get(obj_type, {
        "label": obj_type, "is_code": False,
    })


def classify_wp_type(typ: str) -> dict:
    """Classify a work process type code (DIA, BTC, UPD, etc.)."""
    return WP_TYPE_LABELS.get(typ, {
        "label": f"Unknown ({typ})", "description": f"WP type '{typ}' is not in the local knowledge base.",
    })


def classify_wp_status(status: str) -> dict:
    """Classify a work process status (Run, Wait, Hold, etc.)."""
    return WP_STATUS_LABELS.get(status, {
        "label": f"Unknown ({status})", "is_busy": True, "meaning": f"WP status '{status}' is not classified.",
    })


def classify_wp_reason(reason: str) -> dict:
    """Classify a work process reason flag (e.g. PRIV)."""
    return WP_REASON_FLAGS.get(reason, {
        "severity": "info", "meaning": f"WP reason '{reason}' is not in the local knowledge base.",
        "investigation_hints": [],
    })


