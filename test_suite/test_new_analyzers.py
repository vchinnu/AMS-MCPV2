"""Test all new NetWeaver analyzers + domain knowledge + schema registry changes.

Exercises with mock data:
  1. Domain knowledge classifiers (SM50, SMON, SM13, ST03N, SM58, STMS)
  2. system_monitor analyzer (SMON)
  3. workload analyzer (ST03N / SWNC)
  4. work_processes analyzer (SM50)
  5. rfc_queues analyzer (SM58 tRFC, SMQ1, SMQ2, dispatcher)
  6. transports analyzer (STMS requests + objects)
  7. failed_updates analyzer (SM13)
  8. Schema registry CLASSIFIED_ANALYSIS_TYPES consistency

Run:  python test_new_analyzers.py
"""
from __future__ import annotations
import json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

passed = 0
failed = 0

def section(title: str) -> None:
    print()
    print("=" * 70)
    print(f"  {title}")
    print("=" * 70)

def check(label: str, condition: bool, detail: str = "") -> None:
    global passed, failed
    if condition:
        passed += 1
        print(f"   ✓ {label}")
    else:
        failed += 1
        print(f"   ✗ FAIL: {label}  — {detail}")

# ═══════════════════════════════════════════════════════════════════════════════
# 1. DOMAIN KNOWLEDGE CLASSIFIERS
# ═══════════════════════════════════════════════════════════════════════════════

section("1. DOMAIN KNOWLEDGE — SM50 Work Process classifiers")
import domain_registry as dr

# classify_wp_type
dia = dr.classify_wp_type("DIA")
check("classify_wp_type('DIA') returns label", dia["label"] == "Dialog")
btc = dr.classify_wp_type("BTC")
check("classify_wp_type('BTC') returns label", btc["label"] == "Background")
unk = dr.classify_wp_type("XYZ")
check("classify_wp_type unknown returns Unknown", unk["label"].startswith("Unknown"))

# classify_wp_status
run = dr.classify_wp_status("Run")
check("classify_wp_status('Run') is_busy=True", run["is_busy"] is True)
wait = dr.classify_wp_status("Wait")
check("classify_wp_status('Wait') is_busy=False", wait["is_busy"] is False)
unk_s = dr.classify_wp_status("ZZZZZ")
check("classify_wp_status unknown fallback works", "label" in unk_s)

# classify_wp_reason
priv = dr.classify_wp_reason("PRIV")
check("classify_wp_reason('PRIV') has meaning", len(priv["meaning"]) > 0)
empty_r = dr.classify_wp_reason("")
check("classify_wp_reason empty fallback works", "meaning" in empty_r)

# WP_THRESHOLDS
check("WP_THRESHOLDS has PRIV_WARNING", "PRIV_WARNING" in dr.WP_THRESHOLDS)
check("WP_THRESHOLDS has PRIV_CRITICAL", "PRIV_CRITICAL" in dr.WP_THRESHOLDS)


section("1b. DOMAIN KNOWLEDGE — SMON classifiers")
# classify_smon_metric
cpu_class = dr.classify_smon_metric("CPU_CONS_d", 95)
check("classify_smon_metric CPU=95 → critical", cpu_class["severity"] == "critical")
cpu_ok = dr.classify_smon_metric("CPU_CONS_d", 50)
check("classify_smon_metric CPU=50 → normal", cpu_ok["severity"] == "normal")
mem_low = dr.classify_smon_metric("FREE_MEM_PERC_d", 5)
check("classify_smon_metric FREE_MEM=5 → critical (below)", mem_low["severity"] == "critical")
unknown_m = dr.classify_smon_metric("NONEXISTENT_d", 100)
check("classify_smon_metric unknown metric fallback", unknown_m["severity"] == "normal")

check("SMON_METRIC_THRESHOLDS has CPU_CONS_d", "CPU_CONS_d" in dr.SMON_METRIC_THRESHOLDS)
check("SMON_METRIC_THRESHOLDS has ≥10 metrics", len(dr.SMON_METRIC_THRESHOLDS) >= 10)


section("1c. DOMAIN KNOWLEDGE — SM13 Failed Updates classifiers")
state_err = dr.classify_update_state("1")
check("classify_update_state('1') is_failure=True", state_err["is_failure"] is True)
state_ok = dr.classify_update_state("2")
check("classify_update_state('2') is_failure=False", state_ok["is_failure"] is False)

ctx_v = dr.classify_update_context("V")
check("classify_update_context('V') has label", len(ctx_v["label"]) > 0)


section("1d. DOMAIN KNOWLEDGE — ST03N Workload classifiers")
dialog = dr.classify_task_type("DIALOG")
check("classify_task_type('DIALOG') has sla_threshold_ms", "sla_threshold_ms" in dialog)
unknown_t = dr.classify_task_type("ZZZNOTYPE")
check("classify_task_type unknown fallback works", "label" in unknown_t)

comp = dr.classify_response_component("db", 0.75)
check("classify_response_component('db', 0.75) is_dominant=True", comp["is_dominant"] is True)
comp_low = dr.classify_response_component("cpu", 0.1)
check("classify_response_component('cpu', 0.1) is_dominant=False", comp_low["is_dominant"] is False)


section("1e. DOMAIN KNOWLEDGE — SM58 tRFC / Queue classifiers")
sysfail = dr.classify_trfc_state("SYSFAIL")
check("classify_trfc_state('SYSFAIL') is_failure=True", sysfail["is_failure"] is True)
executed = dr.classify_trfc_state("EXECUTED")
check("classify_trfc_state('EXECUTED') is_failure=False", executed["is_failure"] is False)

depth_ok = dr.classify_queue_depth(10)
check("classify_queue_depth(10) → normal", depth_ok in ("ok", "healthy", "normal"))
depth_warn = dr.classify_queue_depth(500)
check("classify_queue_depth(500) → warning", depth_warn == "warning")
depth_crit = dr.classify_queue_depth(2000)
check("classify_queue_depth(2000) → critical", depth_crit == "critical")

check("QUEUE_DEPTH_THRESHOLDS has warning", "warning" in dr.QUEUE_DEPTH_THRESHOLDS)


section("1f. DOMAIN KNOWLEDGE — STMS Transport classifiers")
released = dr.classify_transport_status("R")
check("classify_transport_status('R') has label", len(released["label"]) > 0)

wb = dr.classify_transport_function("K")
check("classify_transport_function('K') has label", len(wb["label"]) > 0)

prog = dr.classify_transport_object("PROG")
check("classify_transport_object('PROG') is_code=True", prog["is_code"] is True)
tabd = dr.classify_transport_object("TABD")
check("classify_transport_object('TABD') is_code=False", tabd["is_code"] is False)


# ═══════════════════════════════════════════════════════════════════════════════
# 2. SYSTEM MONITOR ANALYZER (SMON)
# ═══════════════════════════════════════════════════════════════════════════════

section("2. SYSTEM MONITOR ANALYZER — healthy scenario")
from analyzers import get_analyzer

smon_analyzer = get_analyzer("system_performance")
check("system_performance analyzer registered", smon_analyzer is not None)

mock_smon_healthy = [
    {"hostname_s": "sapapp01", "CPU_CONS_d": 45, "FREE_MEM_PERC_d": 60,
     "PRIVWPNO_d": 0, "DIAQ_d": 0, "UPDQ_d": 0, "ENQQ_d": 0,
     "STEAL_TIME_d": 0, "PAGE_IN_PERC_d": 0, "PAGE_OUT_PERC_d": 0,
     "DIAAVG60_d": 200, "SESSIONS_d": 50, "serverTimestamp_t": "2026-08-27T10:00:00Z"},
]
result = smon_analyzer(mock_smon_healthy, "SID=PRD healthy test")
check("Healthy SMON → status=success", result["status"] == "success")
check("Healthy SMON → severity=healthy", result["severity"] == "healthy")
check("Healthy SMON → has peak_stress_window", result["peak_stress_window"] is not None)
print(f"   Summary: {result['summary']}")

section("2b. SYSTEM MONITOR ANALYZER — critical scenario (WP exhaustion cascade)")
mock_smon_critical = [
    {"hostname_s": "sapapp01", "CPU_CONS_d": 96, "FREE_MEM_PERC_d": 8,
     "PRIVWPNO_d": 4, "DIAQ_d": 12, "UPDQ_d": 3, "ENQQ_d": 0,
     "STEAL_TIME_d": 0, "PAGE_IN_PERC_d": 0, "PAGE_OUT_PERC_d": 0,
     "DIAAVG60_d": 5500, "SESSIONS_d": 120, "serverTimestamp_t": "2026-08-27T10:05:00Z"},
    {"hostname_s": "sapapp01", "CPU_CONS_d": 88, "FREE_MEM_PERC_d": 12,
     "PRIVWPNO_d": 2, "DIAQ_d": 5, "UPDQ_d": 1, "ENQQ_d": 0,
     "STEAL_TIME_d": 0, "PAGE_IN_PERC_d": 0, "PAGE_OUT_PERC_d": 0,
     "DIAAVG60_d": 3200, "SESSIONS_d": 100, "serverTimestamp_t": "2026-08-27T10:10:00Z"},
]
result2 = smon_analyzer(mock_smon_critical, "SID=PRD critical test")
check("Critical SMON → severity=critical", result2["severity"] == "critical")
check("Critical SMON → has critical_findings", len(result2["critical_findings"]) > 0)
finding_types = [f["finding"] for f in result2["critical_findings"]]
check("Detects WP_EXHAUSTION_CASCADE", "WP_EXHAUSTION_CASCADE" in finding_types)
check("Detects COMPOUND_RESOURCE_PRESSURE", "COMPOUND_RESOURCE_PRESSURE" in finding_types)
print(f"   Summary: {result2['summary']}")
print(f"   Critical findings: {len(result2['critical_findings'])}")

section("2c. SYSTEM MONITOR ANALYZER — empty data")
empty = smon_analyzer([], "empty test")
check("Empty SMON → status=no_data", empty["status"] == "no_data")


# ═══════════════════════════════════════════════════════════════════════════════
# 3. WORKLOAD ANALYZER (ST03N / SWNC)
# ═══════════════════════════════════════════════════════════════════════════════

section("3. WORKLOAD ANALYZER — normal + SLA breach")
wl_analyzer = get_analyzer("workload_statistics")
check("workload_statistics analyzer registered", wl_analyzer is not None)

mock_swnc = [
    # DIALOG — normal response time
    {"Task_Type_Name_s": "DIALOG", "ST03_Avg_Resp_Time_d": 450,
     "ST03_DB_Time_d": 0.35, "ST03_CPU_Time_d": 0.20, "ST03_Queue_Time_d": 0.05,
     "ST03_RollWait_Time_d": 0.10, "ST03_Processing_Time_d": 0.30,
     "Total_Steps_d": 5000, "Total_DB_Seq_Read_Time_d": 100, "Total_DB_Dir_Read_Time_d": 500},
    # DIALOG — SLA breach (>1000ms)
    {"Task_Type_Name_s": "DIALOG", "ST03_Avg_Resp_Time_d": 1800,
     "ST03_DB_Time_d": 0.65, "ST03_CPU_Time_d": 0.10, "ST03_Queue_Time_d": 0.05,
     "ST03_RollWait_Time_d": 0.05, "ST03_Processing_Time_d": 0.15,
     "Total_Steps_d": 3000, "Total_DB_Seq_Read_Time_d": 800, "Total_DB_Dir_Read_Time_d": 200},
    # BACKGROUND
    {"Task_Type_Name_s": "BACKGROUND", "ST03_Avg_Resp_Time_d": 12000,
     "ST03_DB_Time_d": 0.50, "ST03_CPU_Time_d": 0.25, "ST03_Queue_Time_d": 0.02,
     "ST03_RollWait_Time_d": 0.03, "ST03_Processing_Time_d": 0.20,
     "Total_Steps_d": 200, "Total_DB_Seq_Read_Time_d": 50, "Total_DB_Dir_Read_Time_d": 300},
    # RFC
    {"Task_Type_Name_s": "RFC", "ST03_Avg_Resp_Time_d": 300,
     "ST03_DB_Time_d": 0.40, "ST03_CPU_Time_d": 0.30, "ST03_Queue_Time_d": 0.05,
     "ST03_RollWait_Time_d": 0.05, "ST03_Processing_Time_d": 0.20,
     "Total_Steps_d": 8000, "Total_DB_Seq_Read_Time_d": 100, "Total_DB_Dir_Read_Time_d": 500},
]
wl_result = wl_analyzer(mock_swnc, "SID=PRD workload test")
check("Workload → status=success", wl_result["status"] == "success")
check("Workload → has task_type_analysis", len(wl_result["task_type_analysis"]) > 0)
check("Workload → 3 task types analyzed", len(wl_result["task_type_analysis"]) == 3,
      f"got {len(wl_result['task_type_analysis'])}")

# Check SLA breach detection (avg of 450 and 1800 = 1125 > 1000)
sla_findings = [f for f in wl_result["performance_findings"] if f["finding"] == "SLA_BREACH"]
check("Detects DIALOG SLA breach", len(sla_findings) > 0)

# Check seq reads finding (DIALOG row 2 has 800 seq / 200 dir = 4.0 ratio)
seq_findings = [f for f in wl_result["performance_findings"] if f["finding"] == "EXPENSIVE_SEQUENTIAL_READS"]
check("Detects expensive sequential reads", len(seq_findings) > 0)

# Check throughput
check("Dialog steps counted", wl_result["throughput_summary"]["dialog_steps_total"] == 8000)
check("Batch steps counted", wl_result["throughput_summary"]["batch_steps_total"] == 200)
print(f"   Summary: {wl_result['summary']}")
print(f"   Performance findings: {len(wl_result['performance_findings'])}")

section("3b. WORKLOAD ANALYZER — empty data")
empty_wl = wl_analyzer([], "empty test")
check("Empty workload → status=no_data", empty_wl["status"] == "no_data")


# ═══════════════════════════════════════════════════════════════════════════════
# 4. WORK PROCESSES ANALYZER (SM50)
# ═══════════════════════════════════════════════════════════════════════════════

section("4. WORK PROCESSES ANALYZER — WP exhaustion")
wp_analyzer = get_analyzer("workprocess_status")
check("workprocess_status analyzer registered", wp_analyzer is not None)

# All DIA WPs busy → exhaustion
mock_wp_exhaustion = [
    {"hostname_s": "sapapp01", "Typ_s": "DIA", "Status_s": "Run", "Reason_s": "",
     "Program_s": "SAPLZBC1", "User_s": "DDIC", "Err_s": "0"},
    {"hostname_s": "sapapp01", "Typ_s": "DIA", "Status_s": "Run", "Reason_s": "PRIV",
     "Program_s": "ZMY_REPORT", "User_s": "USER01", "Err_s": "0"},
    {"hostname_s": "sapapp01", "Typ_s": "DIA", "Status_s": "Hold", "Reason_s": "PRIV",
     "Program_s": "ZMY_REPORT2", "User_s": "USER02", "Err_s": "0"},
    {"hostname_s": "sapapp01", "Typ_s": "DIA", "Status_s": "Run", "Reason_s": "",
     "Program_s": "SAPLSE38", "User_s": "USER03", "Err_s": "0"},
    {"hostname_s": "sapapp01", "Typ_s": "BTC", "Status_s": "Wait", "Reason_s": "",
     "Program_s": "", "User_s": "", "Err_s": "0"},
    {"hostname_s": "sapapp01", "Typ_s": "BTC", "Status_s": "Run", "Reason_s": "",
     "Program_s": "ZBATCH_JOB", "User_s": "BATCH", "Err_s": "0"},
    {"hostname_s": "sapapp01", "Typ_s": "UPD", "Status_s": "Wait", "Reason_s": "",
     "Program_s": "", "User_s": "", "Err_s": "1"},
]
wp_result = wp_analyzer(mock_wp_exhaustion, "SID=PRD WP test")
check("WP → status=success", wp_result["status"] == "success")
check("WP → severity=critical", wp_result["severity"] == "critical")

# Should detect WP exhaustion (all 4 DIA are busy)
crit_findings = [f["finding"] for f in wp_result["critical_findings"]]
check("Detects WP_EXHAUSTION", "WP_EXHAUSTION" in crit_findings)

# Should detect WP restart (Err_s > 0 on UPD)
warn_findings = [w["finding"] for w in wp_result["warnings"]]
check("Detects WP_RESTARTS", "WP_RESTARTS" in warn_findings)

# PRIV mode — 2 PRIV WPs should trigger warning (threshold = 2)
all_finding_names = crit_findings + warn_findings
check("Detects PRIV_MODE (2 PRIV WPs)", "PRIV_MODE_WARNING" in all_finding_names or "PRIV_MODE_CRITICAL" in all_finding_names)

# Top programs should include SAPLZBC1 and ZMY_REPORT
top_progs = [p["program"] for p in wp_result["top_programs"]]
check("Top programs populated", len(top_progs) > 0)

print(f"   Summary: {wp_result['summary']}")
print(f"   Critical: {len(wp_result['critical_findings'])}, Warnings: {len(wp_result['warnings'])}")

section("4b. WORK PROCESSES ANALYZER — healthy scenario")
mock_wp_healthy = [
    {"hostname_s": "sapapp01", "Typ_s": "DIA", "Status_s": "Wait", "Reason_s": "",
     "Program_s": "", "User_s": "", "Err_s": "0"},
    {"hostname_s": "sapapp01", "Typ_s": "DIA", "Status_s": "Wait", "Reason_s": "",
     "Program_s": "", "User_s": "", "Err_s": "0"},
    {"hostname_s": "sapapp01", "Typ_s": "DIA", "Status_s": "Run", "Reason_s": "",
     "Program_s": "SAPMSSY1", "User_s": "USER01", "Err_s": "0"},
    {"hostname_s": "sapapp01", "Typ_s": "BTC", "Status_s": "Wait", "Reason_s": "",
     "Program_s": "", "User_s": "", "Err_s": "0"},
]
wp_healthy = wp_analyzer(mock_wp_healthy, "SID=PRD healthy WPs")
check("Healthy WP → severity=healthy", wp_healthy["severity"] == "healthy")
check("Healthy WP → no critical findings", len(wp_healthy["critical_findings"]) == 0)
print(f"   Summary: {wp_healthy['summary']}")


# ═══════════════════════════════════════════════════════════════════════════════
# 5. RFC & QUEUES ANALYZER
# ═══════════════════════════════════════════════════════════════════════════════

section("5a. RFC ANALYZER — SM58 tRFC failures")
rfc_analyzer = get_analyzer("transactional_rfc")
check("transactional_rfc analyzer registered", rfc_analyzer is not None)

# Also test queue_monitoring registration (same function handles both)
queue_analyzer = get_analyzer("queue_monitoring")
check("queue_monitoring analyzer registered", queue_analyzer is not None)

mock_trfc = [
    {"ARFCSTATE_s": "SYSFAIL", "ARFCDEST_s": "DEST_ERP01", "ARFCFNAM_s": "BAPI_MATERIAL_SAVEDATA",
     "ARFCMSG_s": "Connection refused", "ARFCUSER_s": "RFC_USER", "ARFCRETRYS_s": "12"},
    {"ARFCSTATE_s": "SYSFAIL", "ARFCDEST_s": "DEST_ERP01", "ARFCFNAM_s": "BAPI_SALESORDER_CREATEFROMDAT2",
     "ARFCMSG_s": "Connection refused", "ARFCUSER_s": "PI_USER", "ARFCRETRYS_s": "8"},
    {"ARFCSTATE_s": "CPICERR", "ARFCDEST_s": "DEST_BW01", "ARFCFNAM_s": "RSA1_TRANSFER",
     "ARFCMSG_s": "Partner not reached", "ARFCUSER_s": "BW_USER", "ARFCRETRYS_s": "3"},
    {"ARFCSTATE_s": "EXECUTED", "ARFCDEST_s": "DEST_ERP01", "ARFCFNAM_s": "BAPI_COMMIT",
     "ARFCMSG_s": "", "ARFCUSER_s": "RFC_USER", "ARFCRETRYS_s": "0"},
]
trfc_result = rfc_analyzer(mock_trfc, "SID=PRD tRFC test")
check("tRFC → status=success", trfc_result["status"] == "success")
check("tRFC → data_source=SM58", trfc_result["data_source"] == "SM58")
check("tRFC → total_failures=3", trfc_result["total_failures"] == 3)
check("tRFC → 2 failing destinations", len(trfc_result["failing_destinations"]) == 2)
# DEST_ERP01 should be first (2 failures > 1)
check("Top failing dest = DEST_ERP01", trfc_result["failing_destinations"][0]["destination"] == "DEST_ERP01")
check("DEST_ERP01 max_retries=12", trfc_result["failing_destinations"][0]["max_retries"] == 12)
print(f"   Summary: {trfc_result['summary']}")

section("5b. RFC ANALYZER — SMQ1 Outbound Queues")
mock_smq1 = [
    {"QNAME_s": "QOUT_DEST_ERP01_001", "DEST_s": "DEST_ERP01", "QDEEP_d": 1500,
     "FDATE_s": "20260826", "FTIME_s": "100000", "LDATE_s": "20260827", "LTIME_s": "080000"},
    {"QNAME_s": "QOUT_DEST_BW01_001", "DEST_s": "DEST_BW01", "QDEEP_d": 50,
     "FDATE_s": "20260827", "FTIME_s": "070000", "LDATE_s": "20260827", "LTIME_s": "073000"},
    {"QNAME_s": "QOUT_DEST_ERP02_001", "DEST_s": "DEST_ERP02", "QDEEP_d": 0,
     "FDATE_s": "", "FTIME_s": "", "LDATE_s": "", "LTIME_s": ""},
]
smq1_result = queue_analyzer(mock_smq1, "SID=PRD SMQ1 test")
check("SMQ1 → data_source=SMQ1_outbound", smq1_result["data_source"] == "SMQ1_outbound")
check("SMQ1 → 2 non-empty queues", smq1_result["non_empty_count"] == 2)
check("SMQ1 → severity=critical (1500 depth)", smq1_result["severity"] == "critical")
print(f"   Summary: {smq1_result['summary']}")

section("5c. RFC ANALYZER — SMQ2 Inbound Queues")
mock_smq2 = [
    {"QNAME_s": "QIN_001", "QDEEP_d": 200,
     "FDATE_s": "20260827", "FTIME_s": "060000"},
    {"QNAME_s": "QIN_002", "QDEEP_d": 0,
     "FDATE_s": "", "FTIME_s": ""},
]
smq2_result = queue_analyzer(mock_smq2, "SID=PRD SMQ2 test")
check("SMQ2 → data_source=SMQ2_inbound", smq2_result["data_source"] == "SMQ2_inbound")
check("SMQ2 → 1 non-empty queue", smq2_result["non_empty_count"] == 1)
print(f"   Summary: {smq2_result['summary']}")

section("5d. RFC ANALYZER — Dispatcher Queues")
mock_disp = [
    {"hostname_s": "sapapp01", "Typ_s": "ABAP/DIA", "Now_d": 5, "High_d": 15, "Max_d": 100,
     "Reads_d": 50000, "Writes_d": 50005, "serverTimestamp_t": "2026-08-27T10:00:00Z"},
    {"hostname_s": "sapapp01", "Typ_s": "ABAP/BTC", "Now_d": 0, "High_d": 3, "Max_d": 50,
     "Reads_d": 2000, "Writes_d": 2000, "serverTimestamp_t": "2026-08-27T10:00:00Z"},
    {"hostname_s": "sapapp01", "Typ_s": "ICM/HTTP", "Now_d": 0, "High_d": 10, "Max_d": 200,
     "Reads_d": 100000, "Writes_d": 100000, "serverTimestamp_t": "2026-08-27T10:00:00Z"},
]
disp_result = queue_analyzer(mock_disp, "SID=PRD dispatcher test")
check("Dispatcher → data_source=dispatcher_queues", disp_result["data_source"] == "dispatcher_queues")
check("Dispatcher → severity=warning (DIA queue active)", disp_result["severity"] in ("warning", "critical"))
# DIA queue has Now_d=5, should produce DIALOG_QUEUE_ACTIVE finding
disp_findings = [f["finding"] for f in disp_result["findings"]]
check("Detects DIALOG_QUEUE_ACTIVE", "DIALOG_QUEUE_ACTIVE" in disp_findings)
print(f"   Summary: {disp_result['summary']}")

section("5e. RFC ANALYZER — empty data")
empty_rfc = rfc_analyzer([], "empty test")
check("Empty RFC → status=no_data", empty_rfc["status"] == "no_data")


# ═══════════════════════════════════════════════════════════════════════════════
# 6. TRANSPORTS ANALYZER (STMS)
# ═══════════════════════════════════════════════════════════════════════════════

section("6a. TRANSPORTS ANALYZER — STMS Requests")
tr_analyzer = get_analyzer("transport_management")
check("transport_management analyzer registered", tr_analyzer is not None)

mock_tr_requests = [
    {"TRKORR_s": "PRDK900001", "TRSTATUS_s": "R", "KORRDEV_s": "K", "AS4USER_s": "DEV01",
     "TARSYSTEM_s": "QAS"},
    {"TRKORR_s": "PRDK900002", "TRSTATUS_s": "R", "KORRDEV_s": "K", "AS4USER_s": "DEV02",
     "TARSYSTEM_s": "QAS"},
    {"TRKORR_s": "PRDK900003", "TRSTATUS_s": "D", "KORRDEV_s": "W", "AS4USER_s": "DEV01",
     "TARSYSTEM_s": ""},
    {"TRKORR_s": "PRDK900004", "TRSTATUS_s": "D", "KORRDEV_s": "K", "AS4USER_s": "DEV01",
     "TARSYSTEM_s": ""},
    {"TRKORR_s": "PRDK900005", "TRSTATUS_s": "L", "KORRDEV_s": "K", "AS4USER_s": "DEV03",
     "TARSYSTEM_s": "PRD"},
]
tr_result = tr_analyzer(mock_tr_requests, "SID=PRD transport requests test")
check("TR requests → data_source=STMS_requests", tr_result["data_source"] == "STMS_requests")
check("TR requests → status_distribution populated", len(tr_result["status_distribution"]) > 0)
check("TR requests → function_distribution populated", len(tr_result["function_distribution"]) > 0)
# DEV01 has 2 locked transports (D status)
locked_owners = {o["owner"]: o["locked_count"] for o in tr_result["owners_with_locked"]}
check("DEV01 has 2 locked transports", locked_owners.get("DEV01", 0) == 2)
print(f"   Summary: {tr_result['summary']}")

section("6b. TRANSPORTS ANALYZER — STMS Objects")
mock_tr_objects = [
    {"TRKORR_s": "PRDK900001", "OBJECT_s": "PROG", "OBJ_NAME_s": "ZMY_REPORT"},
    {"TRKORR_s": "PRDK900001", "OBJECT_s": "CLAS", "OBJ_NAME_s": "ZCL_MY_CLASS"},
    {"TRKORR_s": "PRDK900001", "OBJECT_s": "FUNC", "OBJ_NAME_s": "Z_MY_FUNCTION"},
    {"TRKORR_s": "PRDK900002", "OBJECT_s": "TABD", "OBJ_NAME_s": "ZTABLE_CONFIG"},
    {"TRKORR_s": "PRDK900002", "OBJECT_s": "PROG", "OBJ_NAME_s": "ZMY_REPORT2"},
]
obj_result = tr_analyzer(mock_tr_objects, "SID=PRD transport objects test")
check("TR objects → data_source=STMS_objects", obj_result["data_source"] == "STMS_objects")
check("TR objects → code_vs_config populated", "code_vs_config" in obj_result)
check("TR objects → code=4 (PROG×2 + CLAS + FUNC)", obj_result["code_vs_config"]["code"] == 4)
check("TR objects → config_data=1 (TABD)", obj_result["code_vs_config"]["config_data"] == 1)
print(f"   Summary: {obj_result['summary']}")

section("6c. TRANSPORTS ANALYZER — empty data")
empty_tr = tr_analyzer([], "empty test")
check("Empty transports → status=no_data", empty_tr["status"] == "no_data")


# ═══════════════════════════════════════════════════════════════════════════════
# 7. FAILED UPDATES ANALYZER (SM13)
# ═══════════════════════════════════════════════════════════════════════════════

section("7a. FAILED UPDATES ANALYZER — with failures")
fu_analyzer = get_analyzer("Failed_updates")
check("Failed_updates analyzer registered", fu_analyzer is not None)

mock_failed_updates = [
    # 5 failures from same program → CONCENTRATED_FAILURE
    {"VBSTATE_s": "1", "VBNAME_s": "SAPMV45A", "VBTCODE_s": "VA01", "VBUSER_s": "USER01",
     "VBCONTEXT_s": "V", "VBERROR_s": "Lock conflict on VBAK", "hostname_s": "sapapp01"},
    {"VBSTATE_s": "1", "VBNAME_s": "SAPMV45A", "VBTCODE_s": "VA01", "VBUSER_s": "USER02",
     "VBCONTEXT_s": "V", "VBERROR_s": "Lock conflict on VBAK", "hostname_s": "sapapp01"},
    {"VBSTATE_s": "1", "VBNAME_s": "SAPMV45A", "VBTCODE_s": "VA02", "VBUSER_s": "USER03",
     "VBCONTEXT_s": "V", "VBERROR_s": "Lock conflict on VBAK", "hostname_s": "sapapp01"},
    {"VBSTATE_s": "1", "VBNAME_s": "SAPMV45A", "VBTCODE_s": "VA01", "VBUSER_s": "USER01",
     "VBCONTEXT_s": "V", "VBERROR_s": "Timeout", "hostname_s": "sapapp02"},
    {"VBSTATE_s": "1", "VBNAME_s": "SAPMV45A", "VBTCODE_s": "VA01", "VBUSER_s": "USER04",
     "VBCONTEXT_s": "W", "VBERROR_s": "Timeout", "hostname_s": "sapapp01"},
    # 1 success (auto-processed)
    {"VBSTATE_s": "2", "VBNAME_s": "SAPMV45A", "VBTCODE_s": "VA01", "VBUSER_s": "USER05",
     "VBCONTEXT_s": "V", "VBERROR_s": "", "hostname_s": "sapapp01"},
]
fu_result = fu_analyzer(mock_failed_updates, "SID=PRD failed updates test")
check("FU → status=success", fu_result["status"] == "success")
check("FU → total_failures=5", fu_result["total_failures"] == 5)
check("FU → analysis_type=Failed_updates", fu_result["analysis_type"] == "Failed_updates")

# Check concentrated failure detection (SAPMV45A = 5/5 = 100%)
fu_findings = [f["finding"] for f in fu_result["findings"]]
check("Detects CONCENTRATED_FAILURE", "CONCENTRATED_FAILURE" in fu_findings)

# Check V1 synchronous failure detection (context=V)
check("Detects V1_SYNCHRONOUS_FAILURES", "V1_SYNCHRONOUS_FAILURES" in fu_findings)

# Check top programs
check("Top program = SAPMV45A", fu_result["top_programs"][0]["program"] == "SAPMV45A")

# Check error messages
check("Error messages collected", len(fu_result["top_error_messages"]) > 0)

# Check context distribution
ctx_labels = [c["context_code"] for c in fu_result["context_distribution"]]
check("Context distribution has V and W", "V" in ctx_labels and "W" in ctx_labels)

print(f"   Summary: {fu_result['summary']}")
print(f"   Findings: {fu_findings}")

section("7b. FAILED UPDATES ANALYZER — no failures (all auto-processed)")
mock_fu_healthy = [
    {"VBSTATE_s": "2", "VBNAME_s": "SAPMV45A", "VBTCODE_s": "VA01", "VBUSER_s": "USER01",
     "VBCONTEXT_s": "V", "VBERROR_s": "", "hostname_s": "sapapp01"},
    {"VBSTATE_s": "2", "VBNAME_s": "SAPLMM01", "VBTCODE_s": "ME21N", "VBUSER_s": "USER02",
     "VBCONTEXT_s": "V", "VBERROR_s": "", "hostname_s": "sapapp01"},
]
fu_healthy = fu_analyzer(mock_fu_healthy, "SID=PRD no failures")
check("FU healthy → severity=healthy", fu_healthy["severity"] == "healthy")
check("FU healthy → total_failures=0", fu_healthy["total_failures"] == 0)
print(f"   Summary: {fu_healthy['summary']}")

section("7c. FAILED UPDATES ANALYZER — empty data")
fu_empty = fu_analyzer([], "empty test")
check("Empty FU → status=no_data", fu_empty["status"] == "no_data")


# ═══════════════════════════════════════════════════════════════════════════════
# 8. SCHEMA REGISTRY & ANALYZER CONSISTENCY
# ═══════════════════════════════════════════════════════════════════════════════

section("8. SCHEMA REGISTRY CONSISTENCY")
import schema_registry
from analyzers import get_all_analysis_types

registered = get_all_analysis_types()
check(f"Registered analyzers count = {len(registered)}", len(registered) == 15)

# The analyzer registry is the single source of truth; schema analysis_types that
# have no analyzer fall through to generic_summarizer by design.
KNOWN_UNMAPPED = {"enqueue_locks", "enqueue_statistics", "hana_db"}
schema_types = {
    s["analysis_type"]
    for s in schema_registry.SCHEMA_REGISTRY.values()
    if s.get("analysis_type")
}
unmapped = schema_types - registered
check("No unexpected schema analysis_type without an analyzer",
      unmapped == KNOWN_UNMAPPED,
      f"Unexpected unmapped types: {unmapped - KNOWN_UNMAPPED}")
check("Every analyzer type is used by at least one schema",
      registered.issubset(schema_types | {"availability"}),
      f"Analyzers with no table: {registered - schema_types - {'availability'}}")

# Verify all new types are present
new_types = ["workprocess_status", "Failed_updates", "system_performance",
             "workload_statistics", "transactional_rfc", "queue_monitoring", "transport_management"]
for t in new_types:
    check(f"'{t}' has registered analyzer", get_analyzer(t) is not None)


# ═══════════════════════════════════════════════════════════════════════════════
# 9. DEEPER_RCA_ANALYSIS INTEGRATION (end-to-end through thin wrapper)
# ═══════════════════════════════════════════════════════════════════════════════

section("9. DEEPER_RCA_ANALYSIS — new analyzer types")
from tools.deeper_rca_analysis import deeper_rca_analysis

# Test each new type through the wrapper
test_cases = [
    ("system_performance", mock_smon_critical, "SMON through wrapper"),
    ("workload_statistics", mock_swnc, "SWNC through wrapper"),
    ("workprocess_status", mock_wp_exhaustion, "WP through wrapper"),
    ("transactional_rfc", mock_trfc, "tRFC through wrapper"),
    ("queue_monitoring", mock_smq1, "SMQ1 through wrapper"),
    ("transport_management", mock_tr_requests, "TR requests through wrapper"),
    ("Failed_updates", mock_failed_updates, "Failed updates through wrapper"),
]
for analysis_type, mock_data, label in test_cases:
    wrapper_result = deeper_rca_analysis(
        {"rows": mock_data, "status": "success"},
        analysis_type,
        f"SID=PRD {label}"
    )
    check(f"{analysis_type} → wrapper status=success", wrapper_result["status"] == "success",
          f"got {wrapper_result.get('status')}: {wrapper_result.get('summary', '')[:80]}")


# ═══════════════════════════════════════════════════════════════════════════════
# FINAL SUMMARY
# ═══════════════════════════════════════════════════════════════════════════════

print()
print("=" * 70)
if failed == 0:
    print(f"  ALL {passed} TESTS PASSED ✓")
else:
    print(f"  {passed} PASSED, {failed} FAILED ✗")
print("=" * 70)
print()
print("Analyzers tested:")
print("  ✓ system_monitor  (SMON — system_performance)")
print("  ✓ workload        (SWNC — workload_statistics)")
print("  ✓ work_processes  (SM50 — workprocess_status)")
print("  ✓ rfc_queues      (SM58/SMQ1/SMQ2/Dispatcher — transactional_rfc, queue_monitoring)")
print("  ✓ transports      (STMS requests + objects — transport_management)")
print("  ✓ failed_updates  (SM13 — Failed_updates)")
print()

sys.exit(1 if failed > 0 else 0)
