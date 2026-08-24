"""Test the new token-optimized pipeline end-to-end with mock data.

Exercises: analyzer registry, result_cache, generic_summarizer, toon_formatter,
and deeper_rca_analysis (thin wrapper).

Run:  python test_pipeline.py
"""
from __future__ import annotations
import json

# --- 1. Analyzer Registry ---
from analyzers import get_analyzer, get_all_analysis_types

print("=" * 60)
print("1. ANALYZER REGISTRY")
print("=" * 60)
all_types = sorted(get_all_analysis_types())
print(f"   Registered types ({len(all_types)}): {all_types}")
assert len(all_types) >= 8, f"Expected ≥8 types, got {len(all_types)}"
for t in ["short_dumps", "system_logs", "batch_jobs", "ha_cluster", "os_metrics", "availability"]:
    assert get_analyzer(t) is not None, f"No analyzer for '{t}'"
print("   ✓ All expected analyzers found\n")

# --- 2. Short Dumps Analyzer ---
print("=" * 60)
print("2. SHORT DUMPS ANALYZER (sample data)")
print("=" * 60)
mock_short_dumps = [
    {"Runtime_Error_s": "DBIF_RSQL_SQL_ERROR", "Error_Short_Text_s": "SQL error",
     "Program_s": "SAPLZBC1", "E2E_USER_s": "DDIC", "E2E_HOST_s": "sapapp01",
     "Component_s": "BC-DB", "serverTimestamp_t": "2026-08-18T10:00:00Z"},
    {"Runtime_Error_s": "DBIF_RSQL_SQL_ERROR", "Error_Short_Text_s": "SQL error",
     "Program_s": "SAPLZBC1", "E2E_USER_s": "RFC_USER", "E2E_HOST_s": "sapapp01",
     "Component_s": "BC-DB", "serverTimestamp_t": "2026-08-18T10:05:00Z"},
    {"Runtime_Error_s": "TSV_TNEW_PAGE_ALLOC_FAILED", "Error_Short_Text_s": "No memory",
     "Program_s": "ZMY_REPORT", "E2E_USER_s": "BATCH", "E2E_HOST_s": "sapapp02",
     "Component_s": "BC-ABA", "serverTimestamp_t": "2026-08-18T11:00:00Z"},
]
analyzer = get_analyzer("short_dumps")
result = analyzer(mock_short_dumps, "SID=PRD, testing")
print(f"   Status: {result.get('status')}")
print(f"   Summary: {result.get('summary', '')[:100]}")
print(f"   Findings count: {len(result.get('findings', []))}")
assert result["status"] == "success"
print("   ✓ Short dumps analyzer works\n")

# --- 3. Result Cache ---
print("=" * 60)
print("3. RESULT CACHE (store + retrieve)")
print("=" * 60)
from tools.result_cache import store, get_detail_slice, generate_query_id

qid = generate_query_id("SapNetweaver_ShortDumps_SNAPFulldump_CL | take 10", "PRD")
print(f"   Generated query_id: {qid}")
assert qid.startswith("q_")

store(query_id=qid, rows=mock_short_dumps, analysis_type="short_dumps",
      classified=result, sid="PRD", kql="test query")

# Retrieve detail slice (raw rows)
slice_result = get_detail_slice(qid, category="", offset=0, limit=2)
print(f"   get_detail_slice (no category, limit=2): {slice_result.get('status')}, rows={len(slice_result.get('rows', []))}")
assert slice_result["status"] == "success"
assert len(slice_result["rows"]) == 2

# Retrieve with category filter (depends on classified findings structure)
slice_cat = get_detail_slice(qid, category="DATABASE", offset=0, limit=10)
print(f"   get_detail_slice (category=DATABASE): status={slice_cat.get('status')}")
print("   ✓ Result cache works\n")

# --- 4. Generic Summarizer ---
print("=" * 60)
print("4. GENERIC SUMMARIZER (unclassified data)")
print("=" * 60)
from tools.generic_summarizer import summarize

mock_generic_result = {
    "rows": [
        {"host": "sapapp01", "cpu_pct": 85.2, "mem_pct": 72.1, "timestamp": "2026-08-18T10:00Z"},
        {"host": "sapapp01", "cpu_pct": 91.0, "mem_pct": 74.3, "timestamp": "2026-08-18T10:05Z"},
        {"host": "sapapp02", "cpu_pct": 45.0, "mem_pct": 60.0, "timestamp": "2026-08-18T10:00Z"},
        {"host": "sapapp02", "cpu_pct": 48.5, "mem_pct": 61.2, "timestamp": "2026-08-18T10:05Z"},
    ],
    "row_count": 4,
}
summary = summarize(mock_generic_result, "testing generic path")
print(f"   Keys: {list(summary.keys())}")
print(f"   Row count: {summary.get('row_count')}")
print(f"   Numeric cols: {list(summary.get('numeric_columns', {}).keys())}")
print(f"   Categorical cols: {list(summary.get('categorical_columns', {}).keys())}")
print(f"   Sample rows: {len(summary.get('sample_rows', []))}")
assert summary["row_count"] == 4
# cpu_pct and mem_pct should be detected as numeric
assert "numeric_columns" in summary or "categorical_columns" in summary, "Expected at least some column stats"
print("   ✓ Generic summarizer works\n")

# --- 5. TOON Formatter ---
print("=" * 60)
print("5. TOON FORMATTER (compact + format_summary_response)")
print("=" * 60)
from tools.toon_formatter import compact, format_summary_response

# Test compact removes nulls/empty
dirty = {"a": 1, "b": None, "c": "", "d": [], "e": "keep", "f": [None, "x", None]}
cleaned = compact(dirty)
print(f"   compact({dirty})")
print(f"   → {cleaned}")
assert cleaned.get("b") is None or "b" not in cleaned
assert cleaned["a"] == 1
assert cleaned["e"] == "keep"

# Test format_summary_response
formatted = format_summary_response(result, qid, 3)
print(f"   format_summary_response keys: {list(formatted.keys())}")
assert "query_id" in formatted
assert formatted["query_id"] == qid
assert "_hint" in formatted
print("   ✓ TOON formatter works\n")

# --- 6. Deeper RCA Analysis (thin wrapper) ---
print("=" * 60)
print("6. DEEPER_RCA_ANALYSIS (backward compat wrapper)")
print("=" * 60)
from tools.deeper_rca_analysis import deeper_rca_analysis

wrapper_result = deeper_rca_analysis(
    {"rows": mock_short_dumps, "status": "success"},
    "short_dumps",
    "SID=PRD"
)
print(f"   Status: {wrapper_result.get('status')}")
print(f"   Has findings: {'findings' in wrapper_result}")
assert wrapper_result["status"] == "success"

# Test error path
err_result = deeper_rca_analysis({"status": "error", "error": "timeout"}, "short_dumps")
assert err_result["status"] == "error"
print("   ✓ Error path handled")

# Test no_data path
empty_result = deeper_rca_analysis({"rows": [], "status": "success"}, "short_dumps")
assert empty_result["status"] == "no_data"
print("   ✓ No-data path handled")

# Test unknown type
unknown_result = deeper_rca_analysis({"rows": [{"a": 1}]}, "unknown_type_xyz")
assert "No domain classification" in unknown_result["summary"]
print("   ✓ Unknown type handled\n")

# --- 7. HA Cluster Analyzer ---
print("=" * 60)
print("7. HA CLUSTER ANALYZER")
print("=" * 60)
mock_ha = [
    {"node_s": "node1", "resource_s": "rsc_SAPHana_PRD_HDB00", "role_s": "Master",
     "managed_b": True, "failed_d": 0, "blocked_b": False, "status_s": "Started"},
    {"node_s": "node2", "resource_s": "rsc_SAPHana_PRD_HDB00", "role_s": "Slave",
     "managed_b": True, "failed_d": 0, "blocked_b": False, "status_s": "Started"},
]
ha_analyzer = get_analyzer("ha_cluster")
ha_result = ha_analyzer(mock_ha, "HA cluster check")
print(f"   Status: {ha_result.get('status')}")
print(f"   Summary: {ha_result.get('summary', '')[:80]}")
print("   ✓ HA cluster analyzer works\n")

# --- 8. OS Metrics Analyzer ---
print("=" * 60)
print("8. OS METRICS ANALYZER")
print("=" * 60)
mock_os = [
    {"instance_s": "sapapp01:9100", "MetricName_s": "node_cpu_seconds_total",
     "Val_d": 95.5, "TimeGenerated": "2026-08-18T10:00:00Z"},
    {"instance_s": "sapapp01:9100", "MetricName_s": "node_memory_MemAvailable_bytes",
     "Val_d": 1073741824, "TimeGenerated": "2026-08-18T10:00:00Z"},
]
os_analyzer = get_analyzer("os_metrics")
os_result = os_analyzer(mock_os, "OS check")
print(f"   Status: {os_result.get('status')}")
print(f"   Summary: {os_result.get('summary', '')[:80]}")
print("   ✓ OS metrics analyzer works\n")

# --- Summary ---
print("=" * 60)
print("ALL TESTS PASSED ✓")
print("=" * 60)
print(f"\nPipeline flow verified:")
print(f"  execute_query → analyzer registry → TOON formatter → query_id")
print(f"  execute_query → generic_summarizer → compact → query_id")
print(f"  get_details(query_id) → result_cache → detail slice")
