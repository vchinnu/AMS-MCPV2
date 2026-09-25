"""Tool 1: get_schema — return table schema from the registry.

The agent MUST call this tool first before generating any KQL query.
The schema tells the agent the exact column names, data types, which column
to use for time filtering, which column holds the SID, and KQL writing hints.
"""
from __future__ import annotations

import schema_registry as registry

# SAP transactions AMS does NOT collect. Answered explicitly so the agent stops
# immediately instead of scanning available_tables for something that cannot exist.
# 'closest' names the nearest available data, or None when there is no substitute.
_NOT_COLLECTED: dict[str, dict] = {
    "st02":  {"topic": "SAP buffer / shared-memory statistics",
              "closest": "SapNetweaver_SWNC_Memory_CL (per-program extended memory only — no buffer hit ratios)"},
    "st05":  {"topic": "SQL / RFC / enqueue trace (per-statement)",
              "closest": "SapNetweaver_SWNC_Transaction_CL for aggregated DB time per transaction"},
    "stad":  {"topic": "individual statistical records (per dialog step)",
              "closest": "SapNetweaver_SWNC_Transaction_CL — same data aggregated per transaction per interval"},
    "st12":  {"topic": "ABAP single-transaction trace", "closest": None},
    "se30":  {"topic": "ABAP runtime analysis", "closest": None},
    "sat":   {"topic": "ABAP runtime analysis", "closest": None},
    "smicm": {"topic": "ICM / web dispatcher monitor", "closest": None},
    "rz20":  {"topic": "CCMS alert monitor", "closest": None},
    "al08":  {"topic": "logged-on user list",
              "closest": "SapNetweaver_SWNC_User_CL for per-user workload (not live sessions)"},
    "sm04":  {"topic": "active user sessions",
              "closest": "SapNetweaver_SWNC_User_CL for per-user workload (not live sessions)"},
    "sm59":  {"topic": "RFC destination configuration",
              "closest": "SapNetweaver_TransactionalRfc_CL for tRFC errors by destination"},
    "sm35":  {"topic": "batch input sessions", "closest": None},
    "sp01":  {"topic": "spool requests", "closest": None},
    "st07":  {"topic": "application monitor (user distribution)", "closest": None},
}


def get_schema(table_names: list[str] | None = None) -> dict:
    """Return schema information for Log Analytics tables in the SAP RCA schema registry.

    Call this FIRST before writing any KQL query. The response gives you the exact
    column names, types, time column, SID column, and KQL hints for each table.

    Args:
        table_names: Table names, analysis_types, domain names, or SAP transaction
                     codes. Pass None or an empty list to get a summary of all
                     registered tables.

    Returns:
        When table_names is None/empty — a summary of all registered tables
        (name, short description, analysis_type) plus the global KQL rules.

        When table_names is provided — a dict keyed by table name, each holding the
        full schema (columns, time_column, sid_column, key_columns, kql_hints).
        Names that do not resolve to exactly one small set of tables are reported
        under one of:
          _too_broad     — matched more than _MAX_EXPANDED tables; compact picks
                           are returned instead of full schemas
          _not_collected — a known SAP transaction that AMS does not collect
          _resolved      — fuzzy match applied; lists what the name resolved to
          not_found      — unrecognised
    """
    registered = registry.get_table_names()

    def _short_desc(desc: str) -> str:
        """Return first sentence (up to first period within 100 chars) for compact summary."""
        idx = desc.find(".")
        if 0 < idx < 100:
            return desc[: idx + 1]
        return desc[:80]

    if not table_names:

        # ── COMMENTED OUT: Drill-down enhancement (uncomment to surface related_tables in summary) ──
        # table_list = []
        # for name in registered:
        #     entry: dict = {
        #         "name": name,
        #         "description": _short_desc(registry.SCHEMA_REGISTRY[name]["description"]),
        #         "analysis_type": registry.SCHEMA_REGISTRY[name]["analysis_type"],
        #     }
        #     # Surface drill-down relationships so agent knows detail tables exist
        #     related = registry.SCHEMA_REGISTRY[name].get("related_tables")
        #     if related:
        #         entry["detail_table"] = related[0]["table"]
        #     table_list.append(entry)
        #
        # return {
        #     "registered_tables": table_list,
        #     "total_tables": len(registered),
        #     "global_kql_rules": [...],
        #     "drill_down_workflow": (
        #         "After identifying issues in a summary table, ALWAYS query its detail_table "
        #         "for root cause: ShortDumps_CL→SNAPFulldump_CL (call stack, source code), "
        #         "BatchJobs_CL→BatchJobLog_CL (runtime_error, failed step, job log)."
        #     ),
        #     "hint": "Call get_schema(['TableName']) ...",
        # }
        # ── END COMMENTED OUT ──

        return {
            "registered_tables": [
                {
                    "name": name,
                    "description": _short_desc(registry.SCHEMA_REGISTRY[name]["description"]),
                    "analysis_type": registry.SCHEMA_REGISTRY[name]["analysis_type"],
                }
                for name in registered
            ],
            "total_tables": len(registered),
            "global_kql_rules": [
                "Column names are CASE-SENSITIVE. Use exact names from this schema.",
                "Use sid_column field for SID filter (SID_s or sapsid_s varies by table).",
                "Use time_column field for time filter (varies: serverTimestamp_t, TimeGenerated, timestamp_t).",
                "A table that has never received data in a workspace exposes only the Log Analytics "
                "standard columns. Referencing any schema column then raises SemanticError instead of "
                "returning zero rows — treat that error as 'not collected here', not as a bad query. "
                "Confirm with: <Table> | getschema.",
            ],
            "hint": (
                "Call get_schema(['TableName']) to get full column list, key_columns, "
                "sid_column, time_column, and KQL hints for a specific table."
            ),
        }

    result: dict = {}
    not_found: list[str] = []

    # Global rules included in every response so the agent always sees them.
    result["global_kql_rules"] = [
        "Column names are CASE-SENSITIVE. Use exact names from this schema.",
        "Use sid_column for SID filter (SID_s or sapsid_s varies by table).",
        "Use time_column for time filter (varies: serverTimestamp_t, TimeGenerated, timestamp_t).",
        "A table that has never received data in a workspace exposes only the Log Analytics "
        "standard columns. Referencing any schema column then raises SemanticError instead of "
        "returning zero rows — treat that error as 'not collected here', not as a bad query. "
        "Confirm with: <Table> | getschema.",
    ]

    # Build a reverse map: analysis_type alias → [actual table names]
    # Derived live from SCHEMA_REGISTRY so it is always in sync — no hardcoding needed.
    # Tables with no analysis_type (empty string) are skipped to keep the map clean.
    _alias_map: dict[str, list[str]] = {}
    for _t, _s in registry.SCHEMA_REGISTRY.items():
        atype = _s.get("analysis_type", "")
        if atype:                          # skip tables with no analysis_type
            _alias_map.setdefault(atype, []).append(_t)

    # Domain names resolve too, so a layer name ('hana_db', 'sap_application') keeps working
    # even when its tables are later split across several analysis_types.
    _domain_map: dict[str, list[str]] = {}
    for _t, _s in registry.SCHEMA_REGISTRY.items():
        dom = _s.get("domain", "")
        if dom:
            _domain_map.setdefault(dom, []).append(_t)
    for dom, tabs in _domain_map.items():
        _alias_map.setdefault(dom, tabs)

    # Static keyword map for fuzzy resolution — maps common agent guesses to real tables.
    # Only needed for SAP transaction codes, which share no substring with the table name.
    # Anything whose name overlaps the table name resolves via substring match instead.
    _keyword_map: dict[str, str] = {
        # ── NetWeaver Basis transactions ──
        "sm21": "SapNetweaver_SysLogs_CL",
        "syslog": "SapNetweaver_SysLogs_CL",
        "systemlog": "SapNetweaver_SysLogs_CL",
        "system log": "SapNetweaver_SysLogs_CL",
        "st22": "SapNetweaver_ShortDumps_CL",
        "shortdump": "SapNetweaver_ShortDumps_CL",
        "short dump": "SapNetweaver_ShortDumps_CL",
        "sm37": "SapNetweaver_BatchJobs_CL",
        "sm36": "SapNetweaver_BatchJobs_CL",
        "batch job": "SapNetweaver_BatchJobs_CL",
        "batchjob": "SapNetweaver_BatchJobs_CL",
        "snapfulldump": "SapNetweaver_ShortDumps_SNAPFulldump_CL",
        "full snap": "SapNetweaver_ShortDumps_SNAPFulldump_CL",
        "fullsnap": "SapNetweaver_ShortDumps_SNAPFulldump_CL",
        "sm13": "SapNetweaver_FailedUpdates_CL",
        "failed update": "SapNetweaver_FailedUpdates_CL",
        "sm50": "SapNetweaver_ABAPGetWPTable_CL",
        "sm66": "SapNetweaver_ABAPGetWPTable_CL",
        "work process": "SapNetweaver_ABAPGetWPTable_CL",
        "sm51": "SapNetweaver_GetSystemInstanceList_CL",
        "sm58": "SapNetweaver_TransactionalRfc_CL",
        "trfc": "SapNetweaver_TransactionalRfc_CL",
        "smq1": "SapNetweaver_OutboundQueues_CL",
        "smq2": "SapNetweaver_InboundQueues_CL",
        "sm12": "SapNetweaver_EnqueueRead_CL",
        "enqueue lock": "SapNetweaver_EnqueueRead_CL",
        "st03": "SapNetweaver_SWNC_CL",
        "st03n": "SapNetweaver_SWNC_CL",
        "workload": "SapNetweaver_SWNC_CL",
        "/sdf/mon": "SapNetweaver_SMON_CL",
        # ── OS layer ──
        "st06": "Prometheus_OSExporter_CL",
        "os07": "Prometheus_OSExporter_CL",
        # ── HANA transactions ──
        "db12": "SapHana_BackupCatalog_CL",
        "db13": "SapHana_BackupCatalog_CL",
        "db02": "SapHana_size01_CL",
        "st04": "SapHana_LoadHistory_CL",
        "dbacockpit": "SapHana_SystemOverview_CL",
    }

    # Above this count, an alias/fuzzy match returns compact picks instead of full
    # schemas — 'hana_db' alone maps to 25 tables and would blow the token budget.
    _MAX_EXPANDED = 3

    def _pick(name: str) -> dict:
        s = registry.SCHEMA_REGISTRY[name]
        return {
            "name": name,
            "description": _short_desc(s["description"]),
            "time_column": s.get("time_column"),
            "sid_column": s.get("sid_column"),
            "key_columns": s.get("key_columns", []),
        }

    def _fuzzy_resolve(name: str) -> list[str]:
        """Try to resolve an unrecognised name via keyword map or substring match."""
        name_lower = name.lower().replace("_cl", "").replace("_", " ").strip()
        matches: list[str] = []
        # Check keyword map
        for keyword, table in _keyword_map.items():
            if keyword in name_lower or name_lower in keyword:
                if table not in matches:
                    matches.append(table)
        # Check if input is a substring of a table name (case-insensitive)
        if not matches:
            for tbl in registry.SCHEMA_REGISTRY:
                if name_lower.replace(" ", "") in tbl.lower().replace("_", ""):
                    matches.append(tbl)
        return matches

    for name in table_names:
        schema = registry.get_table_schema(name)
        if schema:
            result[name] = schema
            continue

        # Checked before fuzzy matching so a known-uncollected tcode is never
        # silently resolved to an unrelated table by substring match.
        known_gap = _NOT_COLLECTED.get(name.lower().strip())
        if known_gap:
            entry = {
                "topic": known_gap["topic"],
                "collected_by_ams": False,
                "hint": (
                    f"'{name}' ({known_gap['topic']}) is NOT collected by AMS — no table exists. "
                    "Do not search available_tables for it."
                ),
            }
            if known_gap["closest"]:
                entry["closest_available"] = known_gap["closest"]
            result.setdefault("_not_collected", {})[name] = entry
            continue

        matches = _alias_map.get(name) or _fuzzy_resolve(name)
        if not matches:
            not_found.append(name)
            continue

        if len(matches) > _MAX_EXPANDED:
            result.setdefault("_too_broad", {})[name] = {
                "matched_tables": len(matches),
                "candidates": [_pick(t) for t in matches],
                "hint": (
                    f"'{name}' matches {len(matches)} tables. Full schemas were not returned "
                    "to keep the response small. Pick the tables you need from 'candidates' "
                    "and call get_schema(['ExactTableName', ...]) again."
                ),
            }
            continue

        for resolved in matches:
            result[resolved] = registry.SCHEMA_REGISTRY[resolved]
        if name not in _alias_map:
            result.setdefault("_resolved", {})[name] = matches

    if not_found:
        result["not_found"] = not_found
        result["available_tables"] = list(registry.SCHEMA_REGISTRY.keys())
        result["hint"] = (
            f"Tables {not_found} are not in the registry. "
            "Use one of the available_tables listed above. "
            "You can also pass an analysis_type (e.g. 'system_logs', 'short_dumps', 'batch_jobs') "
            "or an alert keyword (e.g. 'SM21', 'ST22', 'SM37') to resolve the correct table."
        )

    return result
