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
3. Create MCP/analyzers/<domain_name>.py with an @register("<analysis_type>") function.
   The analyzer registry is the single source of truth for which analysis_types are
   classified — nothing needs to be listed in this file.
"""
from __future__ import annotations

from schemas.sap_application  import SCHEMAS as _SAP_APP
from schemas.os_infrastructure import SCHEMAS as _OS_INFRA
from schemas.ha_cluster        import SCHEMAS as _HA_CLUSTER
from schemas.hana_db           import SCHEMAS as _HANA_DB
from schemas.common            import SCHEMAS as _COMMON

# Single merged registry — all tools and the rest of the codebase use this.
SCHEMA_REGISTRY: dict[str, dict] = {
    **_SAP_APP,
    **_OS_INFRA,
    **_HA_CLUSTER,
    **_HANA_DB,
    **_COMMON,
}

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
