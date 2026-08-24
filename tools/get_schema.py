"""Tool 1: get_schema — return table schema from the registry.

The agent MUST call this tool first before generating any KQL query.
The schema tells the agent the exact column names, data types, which column
to use for time filtering, which column holds the SID, and KQL writing hints.
"""
from __future__ import annotations

import schema_registry as registry


def get_schema(table_names: list[str] | None = None) -> dict:
    """Return schema information for Log Analytics tables in the SAP RCA schema registry.

    Call this FIRST before writing any KQL query. The response gives you the exact
    column names, types, time column, SID column, and KQL hints for each table.

    Args:
        table_names: List of specific table names to retrieve full schema for.
                     Pass None or an empty list to get a summary of all registered tables.

    Returns:
        When table_names is None/empty — a summary list of all registered tables
        with their descriptions and key column names.

        When table_names is provided — a dict keyed by table name, each containing
        the full schema: columns, time_column, sid_column, kql_hints, and more.
        Unrecognised table names are listed under 'not_found'.
    """
    registered = registry.get_table_names()

    if not table_names:

        def _short_desc(desc: str) -> str:
            """Return first sentence (up to first period within 100 chars) for compact summary."""
            idx = desc.find(".")
            if 0 < idx < 100:
                return desc[: idx + 1]
            return desc[:80]

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
    ]

    # Build a reverse map: analysis_type alias → [actual table names]
    # Derived live from SCHEMA_REGISTRY so it is always in sync — no hardcoding needed.
    # Tables with no analysis_type (empty string) are skipped to keep the map clean.
    _alias_map: dict[str, list[str]] = {}
    for _t, _s in registry.SCHEMA_REGISTRY.items():
        atype = _s.get("analysis_type", "")
        if atype:                          # skip tables with no analysis_type
            _alias_map.setdefault(atype, []).append(_t)

    # Static keyword map for fuzzy resolution — maps common agent guesses to real tables.
    _keyword_map: dict[str, str] = {
        "sm21": "SapNetweaver_SysLogs_CL",
        "syslog": "SapNetweaver_SysLogs_CL",
        "systemlog": "SapNetweaver_SysLogs_CL",
        "system log": "SapNetweaver_SysLogs_CL",
        "st22": "SapNetweaver_ShortDumps_CL",
        "shortdump": "SapNetweaver_ShortDumps_CL",
        "short dump": "SapNetweaver_ShortDumps_CL",
        "sm37": "SapNetweaver_BatchJobs_CL",
        "batch job": "SapNetweaver_BatchJobs_CL",
        "batchjob": "SapNetweaver_BatchJobs_CL",
        "snapfulldump": "SapNetweaver_ShortDumps_SNAPFulldump_CL",
        "full snap": "SapNetweaver_ShortDumps_SNAPFulldump_CL",
        "fullsnap": "SapNetweaver_ShortDumps_SNAPFulldump_CL",
        "sm13": "SapNetweaver_FailedUpdates_CL",
        "failed update": "SapNetweaver_FailedUpdates_CL",
        "sm66": "SapNetweaver_ABAPGetWPTable_CL",
        "work process": "SapNetweaver_ABAPGetWPTable_CL",
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
        elif name in _alias_map:
            # Agent passed an analysis_type alias (e.g. "ha_cluster") instead of
            # the real table name — resolve it to all matching tables transparently.
            for resolved in _alias_map[name]:
                result[resolved] = registry.SCHEMA_REGISTRY[resolved]
        else:
            # Try fuzzy resolution via alert_keywords or substring match
            fuzzy_matches = _fuzzy_resolve(name)
            if fuzzy_matches:
                for resolved in fuzzy_matches:
                    result[resolved] = registry.SCHEMA_REGISTRY[resolved]
                result.setdefault("_resolved", {})[name] = fuzzy_matches
            else:
                not_found.append(name)

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
