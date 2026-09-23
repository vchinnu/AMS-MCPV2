"""Common/cross-domain schemas — tables shared across SAP provider types.

Tables here are not specific to NetWeaver, HANA, HA Cluster, or OS layers.
"""
from __future__ import annotations

SCHEMAS: dict[str, dict] = {

    # -------------------------------------------------------------------------
    # COMMON_VM_ArmId_Mapping_CL
    # Provider-to-VM ARM resource mapping table
    # -------------------------------------------------------------------------
    "COMMON_VM_ArmId_Mapping_CL": {
        "table_name": "COMMON_VM_ArmId_Mapping_CL",
        "domain": "common",
        "description": (
            "SID-to-VM / provider-to-host mapping. Each row maps an AMS provider instance "
            "(and its SAP SID) to the monitored host and, where AMS could resolve it, to the "
            "Azure VM ARM resource (VM name, resource group, subscription). "
            "This is the join table for correlating SAP/HANA/HA/OS telemetry with the "
            "underlying Azure VM."
        ),
        "data_source": "SAP Monitor — VM ARM ID mapping (daily collection)",
        "time_column": "TimeGenerated",
        "sid_column": "sid_s",
        "key_columns": ["sid_s", "PROVIDER_INSTANCE_s", "Provider_Type_s", "host_name_s", "vm_name_s", "VM_ARM_ID_s"],
        "analysis_type": None,
        "columns": {
            "TimeGenerated": {"type": "datetime", "description": "UTC ingest timestamp. Use for time filters."},
            "Time_Generated_t": {"type": "datetime", "description": "Provider-side timestamp."},
            "sid_s": {
                "type": "string",
                "description": (
                    "SAP System ID for this provider instance (e.g. 'CHA'). LOWERCASE column name on this table. "
                    "May be empty for providers where AMS could not determine the SID."
                ),
            },
            "sapsid_s": {"type": "string", "description": "Alternate SAP SID column — normally identical to sid_s."},
            "PROVIDER_INSTANCE_s": {
                "type": "string",
                "description": (
                    "AMS provider instance name (e.g. 'T09HANA', 'CHA-OS', 'CHA-DB-Cluster'). "
                    "Joins to Prometheus_OSExporter_CL.instance_s and Prometheus_HaClusterExporter_CL.instance_s."
                ),
            },
            "Provider_Type_s": {"type": "string", "description": "Provider type: 'SapHana', 'SapNetWeaver', 'PrometheusOS', 'PrometheusHaCluster', 'MsSqlServer'."},
            "host_name_s": {
                "type": "string",
                "description": (
                    "Host identity as configured in AMS — FQDN, short hostname, or IP address "
                    "(e.g. 'saptst09db-1.redmond.corp.microsoft.com', '10.8.1.9'). "
                    "Because it may be an IP, do not assume it matches hostname_s on other tables."
                ),
            },
            "vm_name_s": {
                "type": "string",
                "description": (
                    "Azure VM name backing this host. EMPTY when the host is not an Azure VM "
                    "(on-premises / third-party cloud) or when ARM resolution failed. Always guard with isnotempty()."
                ),
            },
            "VM_ARM_ID_s": {
                "type": "string",
                "description": (
                    "Full Azure ARM resource ID of the VM "
                    "(/subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.Compute/virtualMachines/<vm>). "
                    "EMPTY when the host is not an Azure VM or ARM resolution failed. "
                    "Use this to pivot into Azure Monitor VM metrics / Activity Log for the same host."
                ),
            },
            "rg_name_s": {"type": "string", "description": "Azure resource group of the VM. Empty when not ARM-resolved."},
            "subscription_id_g": {"type": "guid", "description": "Azure subscription ID of the VM. Empty when not ARM-resolved."},
            "METADATA_s": {"type": "string", "description": "Collector metadata JSON. Not useful for RCA."},
            "SAPMON_VERSION_s": {"type": "string", "description": "Version of the SAP Monitor agent."},
        },
        "kql_hints": [
            "Filter by sid_s (LOWERCASE on this table): | where sid_s == '<sid>'",
            "Records are re-collected periodically — take the newest row per host: | summarize arg_max(TimeGenerated, *) by PROVIDER_INSTANCE_s, host_name_s",
            "SID -> VM lookup: | where sid_s == '<sid>' | where isnotempty(VM_ARM_ID_s) | distinct sid_s, host_name_s, vm_name_s, rg_name_s, VM_ARM_ID_s",
            "Join OS metrics to a VM: Prometheus_OSExporter_CL | join kind=leftouter (COMMON_VM_ArmId_Mapping_CL | summarize arg_max(TimeGenerated, *) by PROVIDER_INSTANCE_s) on $left.instance_s == $right.PROVIDER_INSTANCE_s",
            "vm_name_s / VM_ARM_ID_s / rg_name_s / subscription_id_g are EMPTY for non-Azure hosts — always check isnotempty() before relying on them.",
            "Filter Provider_Type_s to scope by layer: 'SapHana' for DB hosts, 'SapNetWeaver' for app servers, 'PrometheusOS'/'PrometheusHaCluster' for infrastructure.",
        ],
    },
}
