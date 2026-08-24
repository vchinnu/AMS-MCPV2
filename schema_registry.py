"""Schema registry — thin loader that merges all domain schema files.

Each domain has its own file under MCP/schemas/:
  sap_application.py   — ST22 Short Dumps, SM37 Batch Jobs, SM21 System Logs,
                          SAP Instance Availability, Process List
  os_infrastructure.py — Prometheus_OSExporter_CL (CPU / Memory / Disk / Network)
  ha_cluster.py        — Prometheus_HaClusterExporter_CL (Pacemaker / Corosync)
  hana_db.py           — SAP HANA DB tables (alerts, backup, replication)

HOW TO ADD A NEW TABLE
──────────────────────
1. Open the relevant domain file in MCP/schemas/.
2. Add a new entry to the SCHEMAS dict following the existing pattern.
3. Restart the MCP server — no other files need changing.

HOW TO ADD A NEW DOMAIN
───────────────────────
1. Create MCP/schemas/<domain_name>.py with a SCHEMAS dict.
2. Import and merge it here (one line each in the imports and SCHEMA_REGISTRY).
3. Add an analysis_type handler in MCP/tools/deeper_rca_analysis.py.
4. Add the new analysis_type to CLASSIFIED_ANALYSIS_TYPES in this file.
"""
from __future__ import annotations

from schemas.sap_application  import SCHEMAS as _SAP_APP
from schemas.os_infrastructure import SCHEMAS as _OS_INFRA
from schemas.ha_cluster        import SCHEMAS as _HA_CLUSTER
from schemas.hana_db           import SCHEMAS as _HANA_DB

# Single merged registry — all tools and the rest of the codebase use this.
SCHEMA_REGISTRY: dict[str, dict] = {
    **_SAP_APP,
    **_OS_INFRA,
    **_HA_CLUSTER,
    **_HANA_DB,
}

# ── Classified analysis types ──────────────────────────────────────────────────
# Add a new entry here ONLY when a corresponding handler exists in
# tools/deeper_rca_analysis.py for that analysis_type.
# execute_query automatically routes results through deeper_rca_analysis
# for any analysis_type present in this set.
CLASSIFIED_ANALYSIS_TYPES: frozenset[str] = frozenset({
    "short_dumps",   # SapNetweaver_ShortDumps_CL        — ST22 ABAP short dumps
    "system_logs",   # SapNetweaver_SysLogs_CL            — SM21 system log entries
    "batch_jobs",    # SapNetweaver_BatchJobs_CL          — SM37 batch job monitor
    "ha_cluster",    # Prometheus_HaClusterExporter_CL   — Pacemaker / Corosync HA signals
    "os_metrics",    # Prometheus_OSExporter_CL           — OS node exporter metrics
    "availability",              # SapNetweaver_GetSystemInstanceList_CL — SAP instance up/down status
    "SAP_system_availability",   # alias — matches schema definition for GetSystemInstanceList_CL
    "SAP_Process_Availability",  # SapNetweaver_GetProcessList_CL — SAP process-level health
    # "hana_db",     # HANA DB tables                    — add when handler is implemented
})

# ── Convenience accessors (unchanged — all callers continue to work) ───────────

def get_table_names() -> list[str]:
    return list(SCHEMA_REGISTRY.keys())


def get_table_schema(table_name: str) -> dict | None:
    return SCHEMA_REGISTRY.get(table_name)


def get_analysis_type(table_name: str) -> str | None:
    schema = SCHEMA_REGISTRY.get(table_name)
    return schema["analysis_type"] if schema else None


def get_time_column(table_name: str) -> str:
    schema = SCHEMA_REGISTRY.get(table_name)
