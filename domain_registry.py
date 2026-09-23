"""Domain knowledge registry — single import point for all domain classifiers.

deeper_rca_analysis.py imports this as 'dr' and calls all domain functions through it.
To add a new domain:
  1. Create MCP/domain_knowledge_<domain>.py with its data + functions.
  2. Add a 'from domain_knowledge_<domain> import ...' line below.
  No other files need changing.

Current domains:
  domain_knowledge.py     — SAP application layer: ST22, SM37, SM21, SM50, SM13, SMON, ST03N, SM58, STMS
  domain_knowledge_ha.py  — HA cluster: Pacemaker / Corosync metric classification
  domain_knowledge_os.py  — OS infrastructure: Prometheus node exporter classification
"""
from __future__ import annotations

# ── SAP Application layer ────────────────────────────────────────────────────
# Original: ST22 / SM37 / SM21 / NW Availability / FULL_SNAP
from domain_knowledge import (
    classify_runtime_error,
    decode_job_status,
    get_msg_group,
    classify_nw_instance,
    get_section_guide,
    get_priority_sections,
)

# New: SM50 work processes
from domain_knowledge import classify_wp_type, classify_wp_status, classify_wp_reason
from domain_knowledge import WP_THRESHOLDS

# CPU attribution — per-program CPU consumption from ABAPGetWPTable
# Used by the work_processes analyzer to detect CPU hogs per WP type.
from domain_knowledge import (
    parse_cpu_seconds, compute_wp_cpu_deltas, rank_programs_by_cpu,
    compute_wp_type_server_cpu, CPU_ATTRIBUTION_THRESHOLDS,
)

# New: SMON system monitor
from domain_knowledge import classify_smon_metric, SMON_METRIC_THRESHOLDS

# New: SM13 failed updates
from domain_knowledge import classify_update_state, classify_update_context

# New: ST03N workload statistics
from domain_knowledge import classify_task_type, classify_response_component, RESPONSE_TIME_COMPONENTS

# New: SM58 tRFC / queue monitoring
from domain_knowledge import classify_trfc_state, classify_queue_depth, QUEUE_DEPTH_THRESHOLDS

# New: STMS transport management
from domain_knowledge import classify_transport_status, classify_transport_function, classify_transport_object

# ── HA Cluster layer (Prometheus_HaClusterExporter_CL) ───────────────────────
from domain_knowledge_ha import classify_ha_metric

# ── OS Infrastructure layer (Prometheus_OSExporter_CL) ───────────────────────
from domain_knowledge_os import classify_os_metric
