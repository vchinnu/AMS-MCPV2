"""Standalone test script for the SAP RCA MCP server tools.

Run this directly to test tool logic and Log Analytics connectivity
WITHOUT needing an MCP client or inspector.

Usage:
    python MCP/test_tools.py

Requires:
    - .venv activated
    - az login done (or service principal in .env)
    - AZURE_LOG_ANALYTICS_WORKSPACE_ID set in MCP/.env
"""
import sys, json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# ── helpers ───────────────────────────────────────────────────────────────────
def section(title: str) -> None:
    print()
    print("=" * 60)
    print(f"  {title}")
    print("=" * 60)

def show(label: str, value) -> None:
    if isinstance(value, (dict, list)):
        print(f"\n[{label}]")
        print(json.dumps(value, indent=2, default=str)[:2000])
    else:
        print(f"[{label}] {value}")

# ─────────────────────────────────────────────────────────────────────────────
section("TEST 1 — Config + Schema Registry (no Azure needed)")
# ─────────────────────────────────────────────────────────────────────────────
import config
from tools.get_schema import get_schema

print(f"Workspace ID : {config.WORKSPACE_ID[:80]}...")
print(f"Tenant ID    : {config.TENANT_ID}")

schema_summary = get_schema()
print(f"\nRegistered tables: {schema_summary['total_tables']}")
for t in schema_summary["registered_tables"]:
    print(f"  {t['name']:45s} {t['analysis_type']}")

# Full schema for ShortDumps
short_dump_schema = get_schema(["SapNetweaver_ShortDumps_CL"])
sd = short_dump_schema["SapNetweaver_ShortDumps_CL"]
print(f"\nShortDumps columns: {len(sd['columns'])}")
print(f"KQL hints count   : {len(sd['kql_hints'])}")
print("First KQL hint    :", sd["kql_hints"][0])


# HANA tables in registry
hana_names = [t["name"] for t in schema_summary["registered_tables"] if t["name"].startswith("SapHana_")]
print(f"\nHANA tables registered: {len(hana_names)}")
assert len(hana_names) == 25, f"Expected 25 HANA tables, got {len(hana_names)}"
for n in hana_names:
    print(f"  {n}")

# Full schema fetch for two key HANA tables
hana_sr = get_schema(["SapHana_SystemReplication_CL"])["SapHana_SystemReplication_CL"]
print(f"\nSystemReplication columns : {len(hana_sr['columns'])}")
assert "SYSTEM_REPLICATION_STATUS_s" in hana_sr["columns"], "Missing SYSTEM_REPLICATION_STATUS_s"
assert "TIME_DIFF_SECONDS_d" in hana_sr["columns"], "Missing TIME_DIFF_SECONDS_d"
assert hana_sr["time_column"] == "TimeGenerated", f"Wrong time_column: {hana_sr['time_column']}"
assert hana_sr["sid_column"]  == "sapsid_s",      f"Wrong sid_column: {hana_sr['sid_column']}"
print("  key columns present -- PASS")
print(f"  time_column : {hana_sr['time_column']}")
print(f"  sid_column  : {hana_sr['sid_column']}")

hana_svc = get_schema(["SapHana_Services_CL"])["SapHana_Services_CL"]
print(f"\nServices columns          : {len(hana_svc['columns'])}")
assert "ACTIVE_STATUS_s" in hana_svc["columns"], "Missing ACTIVE_STATUS_s"
assert "SERVICE_NAME_s"  in hana_svc["columns"], "Missing SERVICE_NAME_s"
print("  key columns present -- PASS")

# Not-found returns hint
nf = get_schema(["SapHana_NonExistent_CL"])
assert "not_found" in nf, "Expected not_found key for unknown table"
assert "SapHana_NonExistent_CL" in nf["not_found"]
print("\n  not_found behaviour -- PASS")

print("\n✓ TEST 1 PASSED")

# ─────────────────────────────────────────────────────────────────────────────
section("TEST 2 — deeper_rca_analysis with sample data (no Azure needed)")
# ─────────────────────────────────────────────────────────────────────────────
from tools.deeper_rca_analysis import deeper_rca_analysis

sample_dumps = {
    "status": "success",
    "rows": [
        {"Runtime_Error_s": "TIME_OUT",          "Program_s": "ZBATCH_PROC",  "E2E_USER_s": "BATCHUSR",  "E2E_HOST_s": "saphost01", "Error_Short_Text_s": "Execution timeout",       "serverTimestamp_t": "2026-04-06T06:00:00Z"},
        {"Runtime_Error_s": "TIME_OUT",          "Program_s": "ZBATCH_PROC",  "E2E_USER_s": "BATCHUSR",  "E2E_HOST_s": "saphost01", "Error_Short_Text_s": "Execution timeout",       "serverTimestamp_t": "2026-04-06T06:05:00Z"},
        {"Runtime_Error_s": "DBIF_RSQL_SQL_ERROR","Program_s": "ZSAP_DB_CALL","E2E_USER_s": "SAPSYS",    "E2E_HOST_s": "saphost02", "Error_Short_Text_s": "SQL error in open SQL",   "serverTimestamp_t": "2026-04-06T06:02:00Z"},
        {"Runtime_Error_s": "MESSAGE_TYPE_X",    "Program_s": "ZFICO_REPORT", "E2E_USER_s": "FIUSER1",   "E2E_HOST_s": "saphost01", "Error_Short_Text_s": "Termination by MESSAGE X","serverTimestamp_t": "2026-04-06T06:10:00Z"},
    ],
    "row_count": 4,
}
result = deeper_rca_analysis(sample_dumps, "short_dumps", "SID=TST, last 4h")
print(f"Summary   : {result['summary']}")
print(f"Categories: {result['category_breakdown']}")
print(f"Top errors: {[e['runtime_error'] for e in result['error_investigation']]}")
_e0 = result["error_investigation"][0]
print(f"Affected sample  : users={_e0.get('affected_users')} programs={_e0.get('affected_programs')} hosts={_e0.get('affected_hosts')}")

sample_jobs = {
    "status": "success",
    "rows": [
        {"JOBNAME_s": "ZBATCH_PROC",     "STATUS_s": "A", "REAXSERVER_s": "saphost01", "serverTimestamp_t": "2026-04-06T06:01:00Z"},
        {"JOBNAME_s": "ZMONITOR_JOB",    "STATUS_s": "A", "REAXSERVER_s": "saphost01", "serverTimestamp_t": "2026-04-06T06:03:00Z"},
        {"JOBNAME_s": "ZBATCH_PROC",     "STATUS_s": "A", "REAXSERVER_s": "saphost01", "serverTimestamp_t": "2026-04-06T06:07:00Z"},
        {"JOBNAME_s": "ZFICO_REPORT",    "STATUS_s": "F", "REAXSERVER_s": "saphost02", "serverTimestamp_t": "2026-04-06T06:09:00Z"},
    ],
    "row_count": 4,
}
job_result = deeper_rca_analysis(sample_jobs, "batch_jobs", "SID=TST")
print(f"\nBatch jobs summary: {job_result['summary']}")
print(f"Status breakdown  : {job_result['status_breakdown']}")
print(f"Top cancelled     : {job_result['top_cancelled_jobs']}")

sample_logs = {
    "status": "success",
    "rows": [
        {"Msg_area_Msd_Id_s": "AB-0", "Description_s": "Runtime error \"CALL_FUNCTION_OPEN_ERROR\" occurred.", "E2E_HOST_s": "vchaa01l0c_CHA_02", "E2E_USER_s": "SAP_SYSTEM_100", "Program_s": "/RPM/FICO_INT_PLANNING",    "serverTimestamp_t": "2026-04-13T10:19:12Z"},
        {"Msg_area_Msd_Id_s": "D0-1", "Description_s": "Transaction canceled 00 671 ( CALL_FUNCTION_OPEN_ERROR 20260413101613vchaa01l0c_CHA_02 SAP_SYSTEM 10", "E2E_HOST_s": "vchaa01l0c_CHA_02", "E2E_USER_s": "SAP_SYSTEM_100", "Program_s": "/RPM/FICO_INT_PLANNING",    "serverTimestamp_t": "2026-04-13T10:19:12Z"},
        {"Msg_area_Msd_Id_s": "AB-0", "Description_s": "Runtime error \"UNCAUGHT_EXCEPTION\" occurred.",       "E2E_HOST_s": "vchaa01l0c_CHA_02", "E2E_USER_s": "SAP_SYSTEM_100", "Program_s": "PLM_VC_AFL_SESSION_CLEANUP", "serverTimestamp_t": "2026-04-13T10:19:12Z"},
        {"Msg_area_Msd_Id_s": "D0-1", "Description_s": "Transaction canceled 00 671 ( UNCAUGHT_EXCEPTION 20260413101711vchaa01l0c_CHA_02 SAP_SYSTEM 100 )",    "E2E_HOST_s": "vchaa01l0c_CHA_02", "E2E_USER_s": "SAP_SYSTEM_100", "Program_s": "PLM_VC_AFL_SESSION_CLEANUP", "serverTimestamp_t": "2026-04-13T10:19:12Z"},
        {"Msg_area_Msd_Id_s": "AB-0", "Description_s": "Runtime error \"UNCAUGHT_EXCEPTION\" occurred.",       "E2E_HOST_s": "vchaa02l0c_CHA_00", "E2E_USER_s": "SAP_SYSTEM_100", "Program_s": "PLM_VC_AFL_SESSION_CLEANUP", "serverTimestamp_t": "2026-04-13T10:24:09Z"},
        {"Msg_area_Msd_Id_s": "D0-1", "Description_s": "Transaction canceled 00 671 ( UNCAUGHT_EXCEPTION 20260413102136vchaa02l0c_CHA_00 SAP_SYSTEM 100 )",    "E2E_HOST_s": "vchaa02l0c_CHA_00", "E2E_USER_s": "SAP_SYSTEM_100", "Program_s": "PLM_VC_AFL_SESSION_CLEANUP", "serverTimestamp_t": "2026-04-13T10:24:09Z"},
        {"Msg_area_Msd_Id_s": "AB-0", "Description_s": "Runtime error \"CALL_FUNCTION_OPEN_ERROR\" occurred.", "E2E_HOST_s": "vchaa01l0c_CHA_02", "E2E_USER_s": "SAP_SYSTEM_100", "Program_s": "/RPM/FICO_INT_PLANNING",    "serverTimestamp_t": "2026-04-13T10:24:09Z"},
        {"Msg_area_Msd_Id_s": "D0-1", "Description_s": "Transaction canceled 00 671 ( CALL_FUNCTION_OPEN_ERROR 20260413102114vchaa01l0c_CHA_02 SAP_SYSTEM 10", "E2E_HOST_s": "vchaa01l0c_CHA_02", "E2E_USER_s": "SAP_SYSTEM_100", "Program_s": "/RPM/FICO_INT_PLANNING",    "serverTimestamp_t": "2026-04-13T10:24:09Z"},
    ],
    "row_count": 8,
}
log_result = deeper_rca_analysis(sample_logs, "system_logs", "SM21 Severity 1 error for user SAP_SYSTEM_100")
print(f"\nSystem logs summary : {log_result['summary']}")
print(f"Severity            : {log_result['severity']}")
print(f"Groups found        : {[s['message_group'] for s in log_result['next_investigation_steps']]}")
print(f"\n--- next_investigation_steps (with filter_context) ---")
for step in log_result["next_investigation_steps"]:
    print(f"\n  message_group   : {step['message_group']}")
    print(f"  category        : {step['category']}")
    print(f"  count           : {step['count']}")
    fc = step.get("filter_context", {})
    print(f"  affected_programs : {fc.get('affected_programs', [])}")
    print(f"  affected_hosts    : {fc.get('affected_hosts', [])}")
    print(f"  affected_users    : {fc.get('affected_users', [])}")
    print(f"  descriptions      : {fc.get('descriptions', [])}")

# Assertions on the new filter_context fields
steps = {s["message_group"]: s for s in log_result["next_investigation_steps"]}
assert "AB" in steps, "Expected AB group"
assert "D"  in steps, "Expected D group"
ab_fc = steps["AB"]["filter_context"]
assert "/RPM/FICO_INT_PLANNING"    in ab_fc["affected_programs"], "Missing program in AB group"
assert "PLM_VC_AFL_SESSION_CLEANUP" in ab_fc["affected_programs"], "Missing program in AB group"
assert "vchaa01l0c_CHA_02" in ab_fc["affected_hosts"], "Missing host in AB group"
assert "vchaa02l0c_CHA_00" in ab_fc["affected_hosts"], "Missing host in AB group"
assert len(ab_fc["descriptions"]) >= 1, "Expected at least 1 description in AB group"

print("\n✓ TEST 2 PASSED — filter_context fields verified")

# ─────────────────────────────────────────────────────────────────────────────
section("TEST 2B — deeper_rca_analysis: ha_cluster (no Azure needed)")
# ─────────────────────────────────────────────────────────────────────────────
import json as _json

def _lbl(d): return _json.dumps(d)

sample_ha = {
    "status": "success",
    "rows": [
        # Quorum LOST
        {"name_s": "ha_cluster_corosync_quorate",          "value_d": 0.0,  "hostname_s": "chahanw01", "instance_s": "CHA-HA-NW1", "labels_s": "{}",                                                      "sid_s": "CHA", "clusterName_s": "CHA-NW"},
        # STONITH enabled (OK)
        {"name_s": "ha_cluster_pacemaker_stonith_enabled",  "value_d": 1.0,  "hostname_s": "chahanw01", "instance_s": "CHA-HA-NW1", "labels_s": "{}",                                                      "sid_s": "CHA", "clusterName_s": "CHA-NW"},
        # Node online
        {"name_s": "ha_cluster_pacemaker_nodes",            "value_d": 1.0,  "hostname_s": "chahanw01", "instance_s": "CHA-HA-NW1", "labels_s": _lbl({"node":"chahanw01","status":"online","type":"member"}), "sid_s": "CHA", "clusterName_s": "CHA-NW"},
        # Node UNCLEAN
        {"name_s": "ha_cluster_pacemaker_nodes",            "value_d": 1.0,  "hostname_s": "chahanw02", "instance_s": "CHA-HA-NW1", "labels_s": _lbl({"node":"chahanw02","status":"unclean","type":"member"}),"sid_s": "CHA", "clusterName_s": "CHA-NW"},
        # Resource FAILED
        {"name_s": "ha_cluster_pacemaker_resources",        "value_d": 1.0,  "hostname_s": "chahanw01", "instance_s": "CHA-HA-NW1", "labels_s": _lbl({"resource":"rsc_SAPInstance_CHA_ASCS00","status":"failed","role":"started","node":"chahanw01","managed":"true","group":"grp_CHA_ASCS00","clone":""}), "sid_s": "CHA", "clusterName_s": "CHA-NW"},
        # Resource ACTIVE
        {"name_s": "ha_cluster_pacemaker_resources",        "value_d": 1.0,  "hostname_s": "chahanw01", "instance_s": "CHA-HA-NW1", "labels_s": _lbl({"resource":"rsc_IPaddr2_CHA_ASCS00","status":"active","role":"started","node":"chahanw01","managed":"true","group":"grp_CHA_ASCS00","clone":""}),    "sid_s": "CHA", "clusterName_s": "CHA-NW"},
        # Fail count (non-infinity)
        {"name_s": "ha_cluster_pacemaker_fail_count",       "value_d": 2.0,  "hostname_s": "chahanw01", "instance_s": "CHA-HA-NW1", "labels_s": _lbl({"resource":"rsc_SAPInstance_CHA_ASCS00","node":"chahanw01"}),                                                                                          "sid_s": "CHA", "clusterName_s": "CHA-NW"},
        # HANA SFAIL (replication broken)
        {"name_s": "ha_cluster_pacemaker_node_attributes",  "value_d": 1.0,  "hostname_s": "chahadb02", "instance_s": "CHA-HA-DB2", "labels_s": _lbl({"node":"chahadb02","name":"hana_cha_sync_state","value":"SFAIL"}),                                                                                       "sid_s": "CHA", "clusterName_s": "CHA-DB"},
        # Scrape failure for pacemaker collector
        {"name_s": "ha_cluster_scrape_success",             "value_d": 0.0,  "hostname_s": "chahanw02", "instance_s": "CHA-HA-NW1", "labels_s": _lbl({"collector":"pacemaker"}),                                                                                                                              "sid_s": "CHA", "clusterName_s": "CHA-NW"},
        # sapmon heartbeat
        {"name_s": "sapmon",                                "value_d": 1.0,  "hostname_s": "chahanw01", "instance_s": "CHA-HA-NW1", "labels_s": _lbl({"PROVIDER_INSTANCE":"CHA-HA-NW1","SAPMON_VERSION":"3.2.1"}),                                                                                             "sid_s": "CHA", "clusterName_s": "CHA-NW"},
    ],
    "row_count": 10,
}

ha_result = deeper_rca_analysis(sample_ha, "ha_cluster", "SID=CHA, NW cluster investigation")
print(f"Severity         : {ha_result['severity']}")
print(f"Summary          : {ha_result['summary']}")
cs = ha_result["cluster_summary"]
print(f"Quorate          : {cs['quorate']}")
print(f"Nodes online     : {cs['nodes_online']}")
print(f"Nodes unclean    : {cs['nodes_unclean']}")
print(f"Resources active : {cs['resources_active_count']}")
print(f"Resources failed : {cs['resources_failed_count']}")
print(f"Scrape failures  : {cs['scrape_failures']}")
print(f"\nCritical findings ({len(ha_result['critical_findings'])}):")
for cf in ha_result["critical_findings"]:
    print(f"  [{cf['category']}] {cf['issue']}")
print(f"\nWarnings ({len(ha_result['warnings'])}):")
for w in ha_result["warnings"]:
    print(f"  [{w['category']}] {w['issue']}")

assert ha_result["severity"] == "critical",              f"Expected critical, got {ha_result['severity']}"
assert cs["quorate"] is False,                            "Expected quorate=False"
assert "chahanw02" in cs["nodes_unclean"],                "Expected chahanw02 in unclean"
assert cs["resources_failed_count"] == 1,                 "Expected 1 failed resource"
assert cs["resources_active_count"] == 1,                 "Expected 1 active resource"
assert "pacemaker" in cs["scrape_failures"],              "Expected pacemaker scrape failure"
assert any("SFAIL" in f["issue"] for f in ha_result["warnings"]), "Expected HANA SFAIL warning"
assert len(ha_result["critical_findings"]) >= 2,          "Expected >=2 critical findings (quorum + unclean)"

print("\n✓ TEST 2B PASSED — ha_cluster handler verified")

# ─────────────────────────────────────────────────────────────────────────────
section("TEST 2C — deeper_rca_analysis: os_metrics (no Azure needed)")
# ─────────────────────────────────────────────────────────────────────────────
sample_os = {
    "status": "success",
    "rows": [
        # CPU
        {"name_s": "node_cpu_seconds_total",           "value_d": 112345.6, "instance_s": "CHA-OS", "SID_s": "CHA", "labels_s": _lbl({"cpu":"0","mode":"idle"})},
        {"name_s": "node_cpu_seconds_total",           "value_d": 22345.1,  "instance_s": "CHA-OS", "SID_s": "CHA", "labels_s": _lbl({"cpu":"0","mode":"user"})},
        {"name_s": "node_cpu_seconds_total",           "value_d": 4500.3,   "instance_s": "CHA-OS", "SID_s": "CHA", "labels_s": _lbl({"cpu":"0","mode":"iowait"})},
        # Memory
        {"name_s": "node_memory_MemTotal_bytes",       "value_d": 137438953472.0, "instance_s": "CHA-OS", "SID_s": "CHA", "labels_s": "{}"},
        {"name_s": "node_memory_MemAvailable_bytes",   "value_d": 5368709120.0,   "instance_s": "CHA-OS", "SID_s": "CHA", "labels_s": "{}"},
        {"name_s": "node_memory_SwapFree_bytes",       "value_d": 2147483648.0,   "instance_s": "CHA-OS", "SID_s": "CHA", "labels_s": "{}"},
        # Disk
        {"name_s": "node_filesystem_avail_bytes",      "value_d": 10737418240.0,  "instance_s": "CHA-OS", "SID_s": "CHA", "labels_s": _lbl({"device":"/dev/sda1","mountpoint":"/hana/data","fstype":"xfs"})},
        {"name_s": "node_disk_io_time_seconds_total",  "value_d": 8765.4,         "instance_s": "CHA-OS", "SID_s": "CHA", "labels_s": _lbl({"device":"sda"})},
        # Network
        {"name_s": "node_network_receive_bytes_total", "value_d": 998877665544.0, "instance_s": "CHA-OS", "SID_s": "CHA", "labels_s": _lbl({"device":"eth0"})},
        {"name_s": "node_network_receive_errs_total",  "value_d": 12.0,           "instance_s": "CHA-OS", "SID_s": "CHA", "labels_s": _lbl({"device":"eth0"})},
        # System
        {"name_s": "node_boot_time_seconds",           "value_d": 1744000000.0,   "instance_s": "CHA-OS", "SID_s": "CHA", "labels_s": "{}"},
        # sapmon heartbeat — must be excluded from metric rows
        {"name_s": "sapmon",                           "value_d": 1.0,            "instance_s": "CHA-OS", "SID_s": "CHA", "labels_s": _lbl({"PROVIDER_INSTANCE":"CHA-OS","SAPMON_VERSION":"3.2.1"})},
    ],
    "row_count": 12,
}

os_result = deeper_rca_analysis(sample_os, "os_metrics", "SID=CHA, OS check")
print(f"Severity            : {os_result['severity']}")
print(f"Summary             : {os_result['summary']}")
print(f"Instances           : {os_result['instances']}")
print(f"SIDs                : {os_result['sids']}")
print(f"Categories present  : {[c['category'] for c in os_result['category_summary']]}")
print(f"Threshold guidance  : {[t['metric'] for t in os_result['threshold_guidance']]}")
print(f"Unknown metrics     : {os_result.get('unknown_metrics', [])}")
print(f"\nInvestigation hints by category:")
for inv in os_result["investigation_by_category"]:
    print(f"  [{inv['category']}] {len(inv['investigation_hints'])} hint(s), first: {inv['investigation_hints'][0][:80]}")

assert os_result["raw_row_count"] == 12,                         "Expected raw_row_count=12"
assert "CHA-OS" in os_result["instances"],                       "Expected CHA-OS in instances"
assert "CHA"    in os_result["sids"],                            "Expected CHA in sids"
cats = {c["category"] for c in os_result["category_summary"]}
for expected_cat in ("CPU", "Memory", "Filesystem", "Disk I/O", "Network", "System"):
    assert expected_cat in cats, f"Expected category '{expected_cat}' not found"
# sapmon excluded from metric rows — should NOT appear as a category
assert "Metadata" not in cats,                                   "sapmon must be excluded from metric categories"
# sapmon must NOT appear in unknown_metrics either
assert "sapmon" not in os_result.get("unknown_metrics", []),             "sapmon must be filtered before classification"
assert len(os_result["threshold_guidance"]) >= 1,                "Expected at least 1 metric with threshold guidance"
assert "2 metric rows" not in os_result["summary"],              "Summary should reflect 11 metric rows, not 2"

print("\n✓ TEST 2C PASSED — os_metrics handler verified")

# ─────────────────────────────────────────────────────────────────────────────
section("TEST 2D — deeper_rca_analysis: availability (no Azure needed)")
# ─────────────────────────────────────────────────────────────────────────────
# Scenario:
#   SID = CHA
#   chascs00cl1 / inst 0  → ASCS (MESSAGESERVER+ENQUE) — GREEN all rows  → healthy
#   vchaa01l0c  / inst 2  → AppServer (ABAP|ICMAN)     — GREEN + RED rows → intermittent
#   vchaa02l0c  / inst 0  → AppServer (ABAP|ICMAN)     — GREEN all rows   → healthy
#   chaers01cl2 / inst 1  → ERS (ENQREP)               — GRAY all rows    → warning

def _make_avail_row(hostname, inst_nr, features, dispstatus, ts):
    return {
        "SID_s": "CHA",
        "hostname_s": hostname,
        "instanceNr_d": float(inst_nr),
        "features_s": features,
        "dispstatus_s": dispstatus,
        "serverTimestamp_t": ts,
        "startPriority_s": "3",
        "httpPort_d": 50013.0,
        "httpsPort_d": 50014.0,
    }

avail_rows = [
    # ASCS — always GREEN
    _make_avail_row("chascs00cl1", 0, "GATEWAY|MESSAGESERVER|ENQUE", "SAPControl-GREEN", "2026-04-17T11:21:04Z"),
    _make_avail_row("chascs00cl1", 0, "GATEWAY|MESSAGESERVER|ENQUE", "SAPControl-GREEN", "2026-04-17T11:22:04Z"),
    # App server 1 — intermittent: was RED earlier, then GREEN at latest poll
    _make_avail_row("vchaa01l0c",  2, "ABAP|GATEWAY|ICMAN|IGS",      "SAPControl-RED",   "2026-04-17T11:21:04Z"),
    _make_avail_row("vchaa01l0c",  2, "ABAP|GATEWAY|ICMAN|IGS",      "SAPControl-GREEN", "2026-04-17T11:22:04Z"),
    # App server 2 — always GREEN
    _make_avail_row("vchaa02l0c",  0, "ABAP|GATEWAY|ICMAN|IGS",      "SAPControl-GREEN", "2026-04-17T11:21:04Z"),
    _make_avail_row("vchaa02l0c",  0, "ABAP|GATEWAY|ICMAN|IGS",      "SAPControl-GREEN", "2026-04-17T11:22:04Z"),
    # ERS — always GRAY
    _make_avail_row("chaers01cl2", 1, "ENQREP",                       "SAPControl-GRAY",  "2026-04-17T11:21:04Z"),
    _make_avail_row("chaers01cl2", 1, "ENQREP",                       "SAPControl-GRAY",  "2026-04-17T11:22:04Z"),
]

avail_result = deeper_rca_analysis(
    {"status": "success", "rows": avail_rows},
    analysis_type="availability",
    context="Test scenario: ERS down, app server intermittent",
)
print(f"Status:        {avail_result['status']}")
print(f"Severity:      {avail_result['severity']}")
print(f"System health: {avail_result['system_health']}")
print(f"App servers:   {avail_result['app_servers_up']}/{avail_result['app_servers_total']}")
print(f"ASCS healthy:  {avail_result['ascs_healthy']}")
print(f"Warnings:      {len(avail_result['warnings'])}")
print(f"Summary:       {avail_result['summary']}")

# ── Assertions ──
assert avail_result["status"]        == "success",          "status must be success"
assert avail_result["ascs_healthy"]  is True,               "ASCS is GREEN — must be healthy"
assert avail_result["app_servers_total"] == 2,              "Expected 2 app servers"
assert avail_result["app_servers_up"]    == 2,              "Both app servers GREEN at latest poll"
assert avail_result["system_health"] == "Available",        "Both ASCS and all app servers GREEN → Available"
# ERS GRAY should produce a warning
ers_warnings = [w for w in avail_result["warnings"] if w.get("instance_type") == "ERS"]
assert len(ers_warnings) >= 1,                              "Expected at least 1 ERS warning"
# Intermittent flag on vchaa01l0c (was RED then GREEN)
intermittent_warnings = [
    w for w in avail_result["warnings"] if "INTERMITTENT" in w.get("issue", "").upper()
]
assert len(intermittent_warnings) >= 1,                     "Expected intermittent warning for vchaa01l0c"
# No critical findings — ASCS was always GREEN
assert len(avail_result.get("critical_findings", [])) == 0,         "No ASCS outage → no critical findings"
# instance_summary must have 4 entries
assert len(avail_result["instance_summary"]) == 4,          "Expected 4 instances in summary"
# instance types correctly classified
types_seen = {i["instance_type"] for i in avail_result["instance_summary"]}
assert "ASCS"      in types_seen,                           "Expected ASCS type"
assert "AppServer" in types_seen,                           "Expected AppServer type"
assert "ERS"       in types_seen,                           "Expected ERS type"
# severity: ERS GRAY + intermittent warning → medium (no app server down at latest timestamp)
assert avail_result["severity"] in ("medium",),             f"Expected medium severity, got {avail_result['severity']}"

# ── Sub-scenario: ASCS RED → critical ──────────────────────────────────────
critical_rows = [
    _make_avail_row("chascs00cl1", 0, "GATEWAY|MESSAGESERVER|ENQUE", "SAPControl-RED",   "2026-04-17T11:22:04Z"),
    _make_avail_row("vchaa01l0c",  2, "ABAP|GATEWAY|ICMAN|IGS",      "SAPControl-GREEN", "2026-04-17T11:22:04Z"),
]
ascs_down = deeper_rca_analysis(
    {"status": "success", "rows": critical_rows},
    analysis_type="availability",
    context="ASCS gone RED",
)
assert ascs_down["severity"]     == "critical",  f"ASCS RED must be critical, got {ascs_down['severity']}"
assert ascs_down["system_health"] == "Offline",   f"ASCS RED → system_health must be Offline"
assert ascs_down["ascs_healthy"] is False,        "ASCS RED → ascs_healthy must be False"
assert len(ascs_down["critical_findings"]) == 1,  "Expected exactly 1 critical finding for ASCS RED"
print("  Sub-scenario ASCS RED ✓")

print("\n✓ TEST 2D PASSED — availability handler verified")

# ─────────────────────────────────────────────────────────────────────────────
section("TEST 3 — execute_query read-only guard (no Azure needed)")
# ─────────────────────────────────────────────────────────────────────────────
from tools.execute_query import execute_query

# Should be REJECTED — write operation
bad_result = execute_query(".drop table SapNetweaver_ShortDumps_CL", sid="TST")
print(f"Write-op blocked: status={bad_result['status']}, error={bad_result['error']}")
assert bad_result["status"] == "rejected"

# Should be REJECTED — SQL write keyword
bad_result2 = execute_query("DELETE FROM SapNetweaver_ShortDumps_CL", sid="TST")
print(f"SQL write blocked: status={bad_result2['status']}")
assert bad_result2["status"] == "rejected"

print("\n✓ TEST 3 PASSED (read-only guard working)")

# ─────────────────────────────────────────────────────────────────────────────
section("TEST 4 — Live Log Analytics query (requires az login)")
# ─────────────────────────────────────────────────────────────────────────────
print("Attempting live connection to Log Analytics...")
print(f"Workspace: {config.WORKSPACE_ID[-40:]}")
print()

# Simple test query — just check the table exists and is reachable
test_kql = """SapNetweaver_ShortDumps_CL
| where serverTimestamp_t > ago(24h)
| summarize TotalDumps=count(), UniqueErrors=dcount(Runtime_Error_s), UniqueSIDs=dcount(SID_s)
| take 1"""

live_result = execute_query(test_kql, sid="ALL", timespan_hours=24)

if live_result["status"] in ("success", "partial"):
    print("✓ Connected to Log Analytics successfully!")
    show("Query result (last 24h across all SIDs)", live_result.get("summary"))
elif live_result["status"] == "error":
    err = live_result["error"]
    if "credential" in err.lower() or "token" in err.lower() or "auth" in err.lower():
        print("⚠ Authentication error — run: az login --tenant 72f988bf-86f1-41af-91ab-2d7cd011db47")
    elif "workspace" in err.lower() or "resource" in err.lower():
        print("⚠ Workspace not found — check AZURE_LOG_ANALYTICS_WORKSPACE_ID in MCP/.env")
    else:
        print(f"⚠ Query error: {err}")
    print("\nTests 1–3 all passed. Fix auth above to enable live querying.")


# ─────────────────────────────────────────────────────────────────────────────
section("TEST 4B — Live HANA queries (requires az login)")
# ─────────────────────────────────────────────────────────────────────────────
print("Querying HANA tables in Log Analytics...")

hana_queries = {
    "SapHana_SystemReplication_CL": """SapHana_SystemReplication_CL
| where TimeGenerated > ago(1h)
| project TimeGenerated, sapsid_s, HOST_s, SYSTEM_REPLICATION_STATUS_s, SERVICE_REPLICATION_STATUS_s, TIME_DIFF_SECONDS_d, SECONDARY_HOST_s
| order by TimeGenerated desc
| take 5""",
    "SapHana_Services_CL": """SapHana_Services_CL
| where TimeGenerated > ago(1h)
| project TimeGenerated, sapsid_s, HOST_s, SERVICE_NAME_s, ACTIVE_STATUS_s, PORT_d
| order by TimeGenerated desc
| take 5""",
    "SapHana_SystemAvailability_CL": """SapHana_SystemAvailability_CL
| where TimeGenerated > ago(1h)
| project TimeGenerated, sapsid_s, SYSTEM_ACTIVE_s, SYSTEM_STATUS_s, HOST_s, ERROR_MESSAGE_s
| order by TimeGenerated desc
| take 5""",
}

for tbl, kql in hana_queries.items():
    r = execute_query(kql, sid="ALL", timespan_hours=1)
    if r["status"] in ("success", "partial"):
        print(f"  ✓ {tbl} — {r['row_count']} rows returned")
        if r["row_count"] > 0:
            print(f"    summary: {str(r.get('summary'))[:160]}")
    elif r["status"] == "error":
        err = r["error"]
        if "credential" in err.lower() or "token" in err.lower() or "auth" in err.lower():
            print(f"  ⚠ {tbl} — auth error (run az login)")
        elif "recognize" in err.lower() or "table" in err.lower():
            print(f"  ⚠ {tbl} — table not found in workspace (check sapmon provider)")
        else:
            print(f"  ⚠ {tbl} — {err[:120]}")

# ─────────────────────────────────────────────────────────────────────────────
section("SUMMARY")
# ─────────────────────────────────────────────────────────────────────────────
print("Tests 1-3: Core logic, schema, domain knowledge — PASSED (no Azure needed)")
print("Test 4:    Live LA query — requires 'az login' first")
print()
print("To run full RCA once authenticated:")
print("  from tools.rca_orchestrator import run_full_rca")
print("  result = run_full_rca(sid='MST', time_range_hours=4)")
print("  import json; print(json.dumps(result, indent=2, default=str))")
