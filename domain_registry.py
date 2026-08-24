"""Domain knowledge registry — single import point for all domain classifiers.

deeper_rca_analysis.py imports this as 'dr' and calls all domain functions through it.
To add a new domain:
  1. Create MCP/domain_knowledge_<domain>.py with its data + functions.
  2. Add a 'from domain_knowledge_<domain> import ...' line below.
  No other files need changing.

Current domains:
  domain_knowledge.py     — SAP application layer: ST22 short dumps, SM37 batch jobs, SM21 system logs
  domain_knowledge_ha.py  — HA cluster: Pacemaker / Corosync metric classification  (not yet created)
  domain_knowledge_os.py  — OS infrastructure: Prometheus node exporter classification (not yet created)
"""
from __future__ import annotations

# ── SAP Application layer (ST22 / SM37 / SM21 / NW Availability / FULL_SNAP) ─
from domain_knowledge import (
    classify_runtime_error,
    decode_job_status,
    get_msg_group,
    classify_nw_instance,
    get_section_guide,
    get_priority_sections,
)

# ── HA Cluster layer (Prometheus_HaClusterExporter_CL) ───────────────────────
from domain_knowledge_ha import classify_ha_metric

# ── OS Infrastructure layer (Prometheus_OSExporter_CL) ───────────────────────
from domain_knowledge_os import classify_os_metric
