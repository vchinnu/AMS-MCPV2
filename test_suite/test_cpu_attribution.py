"""Quick validation of CPU attribution domain knowledge functions."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from domain_registry import (
    parse_cpu_seconds, compute_wp_cpu_deltas, rank_programs_by_cpu,
    compute_wp_type_server_cpu, CPU_ATTRIBUTION_THRESHOLDS,
)

print("Imports OK")
print("Thresholds:", CPU_ATTRIBUTION_THRESHOLDS)

# Test parse_cpu_seconds
assert parse_cpu_seconds("0:00:00") == 0
assert parse_cpu_seconds("1:23:45") == 5025
assert parse_cpu_seconds("12:05:03") == 43503
assert parse_cpu_seconds("") is None
assert parse_cpu_seconds(None) is None
print("parse_cpu_seconds: all tests pass")

# Test compute_wp_cpu_deltas with mock rows simulating Scenario 3
rows = [
    # 3 BTC WPs running ZBAD_REPORT (2 snapshots each, 5 min apart)
    # CPU-bound: ~560s CPU in 300s wall-clock
    {"No_d": 13, "hostname_s": "host1", "Typ_s": "BTC", "Program_s": "ZBAD_REPORT",
     "Cpu_s": "0:10:00", "Status_s": "Run", "Time_s": "295",
     "TimeGenerated": "2026-08-31T10:05:00Z"},
    {"No_d": 13, "hostname_s": "host1", "Typ_s": "BTC", "Program_s": "ZBAD_REPORT",
     "Cpu_s": "0:19:20", "Status_s": "Run", "Time_s": "595",
     "TimeGenerated": "2026-08-31T10:10:00Z"},
    {"No_d": 14, "hostname_s": "host1", "Typ_s": "BTC", "Program_s": "ZBAD_REPORT",
     "Cpu_s": "0:08:00", "Status_s": "Run", "Time_s": "590",
     "TimeGenerated": "2026-08-31T10:10:00Z"},
    {"No_d": 14, "hostname_s": "host1", "Typ_s": "BTC", "Program_s": "ZBAD_REPORT",
     "Cpu_s": "0:17:30", "Status_s": "Run", "Time_s": "290",
     "TimeGenerated": "2026-08-31T10:05:00Z"},
    {"No_d": 15, "hostname_s": "host1", "Typ_s": "BTC", "Program_s": "ZBAD_REPORT",
     "Cpu_s": "0:09:00", "Status_s": "Run", "Time_s": "285",
     "TimeGenerated": "2026-08-31T10:05:00Z"},
    {"No_d": 15, "hostname_s": "host1", "Typ_s": "BTC", "Program_s": "ZBAD_REPORT",
     "Cpu_s": "0:18:00", "Status_s": "Run", "Time_s": "585",
     "TimeGenerated": "2026-08-31T10:10:00Z"},
    # 1 BTC WP running RSMONICDP — I/O bound (low CPU delta vs wall-clock)
    {"No_d": 20, "hostname_s": "host1", "Typ_s": "BTC", "Program_s": "RSMONICDP",
     "Cpu_s": "5:00:00", "Status_s": "Run", "Time_s": "30",
     "TimeGenerated": "2026-08-31T10:05:00Z"},
    {"No_d": 20, "hostname_s": "host1", "Typ_s": "BTC", "Program_s": "RSMONICDP",
     "Cpu_s": "5:00:10", "Status_s": "Run", "Time_s": "45",
     "TimeGenerated": "2026-08-31T10:10:00Z"},
    # 1 DIA WP with same program across 2 consecutive snapshots (long-running)
    {"No_d": 5, "hostname_s": "host1", "Typ_s": "DIA", "Program_s": "SAPLSMTR",
     "Cpu_s": "1:00:00", "Status_s": "Run", "Time_s": "350",
     "TimeGenerated": "2026-08-31T10:05:00Z"},
    {"No_d": 5, "hostname_s": "host1", "Typ_s": "DIA", "Program_s": "SAPLSMTR",
     "Cpu_s": "1:02:00", "Status_s": "Run", "Time_s": "410",
     "TimeGenerated": "2026-08-31T10:06:00Z"},
    # 1 DIA WP with changing programs (unreliable)
    {"No_d": 6, "hostname_s": "host1", "Typ_s": "DIA", "Program_s": "SAPMSSY1",
     "Cpu_s": "2:00:00", "Status_s": "Run", "Time_s": "3",
     "TimeGenerated": "2026-08-31T10:05:00Z"},
    {"No_d": 6, "hostname_s": "host1", "Typ_s": "DIA", "Program_s": "SAPLSDTX",
     "Cpu_s": "2:01:30", "Status_s": "Run", "Time_s": "5",
     "TimeGenerated": "2026-08-31T10:06:00Z"},
]

deltas = compute_wp_cpu_deltas(rows)
print(f"\ncompute_wp_cpu_deltas: {len(deltas)} WPs with deltas")
for d in deltas:
    eff_str = f" eff={d['cpu_efficiency']}" if 'cpu_efficiency' in d else ""
    bound_str = f" cpu_bound={d['cpu_bound']}" if 'cpu_bound' in d else ""
    rt_str = f" max_rt={d['max_request_runtime_sec']}s" if 'max_request_runtime_sec' in d else ""
    print(f"  WP#{d['No_d']} {d['Typ_s']} {d['Program_s']}: "
          f"delta={d['cpu_delta_sec']}s snapshots={d['snapshots']} "
          f"reliable={d['reliable']}{eff_str}{bound_str}{rt_str}")

ranking = rank_programs_by_cpu(deltas)
print(f"\nrank_programs_by_cpu (no server CPU): types = {list(ranking.keys())}")
for typ, programs in ranking.items():
    print(f"  {typ}:")
    for p in programs:
        print(f"    {p['Program_s']}: {p['total_cpu_sec']}s ({p['cpu_pct']}%) "
              f"on {p['wp_count']} WPs, reliable={p['reliable']}, "
              f"server_cpu_pct={p.get('server_cpu_pct')}")

# Without wall_clock/core_count, server_cpu_pct should be None
btc = ranking.get("BTC", [])
assert btc[0]["server_cpu_pct"] is None, "server_cpu_pct should be None without core_count"
print("Verified: server_cpu_pct is None when core_count not provided")

# Now test with wall_clock and core_count (4 cores, 5 min window = 300s)
ranking_with_server = rank_programs_by_cpu(deltas, wall_clock_sec=300.0, core_count=4)
print(f"\nrank_programs_by_cpu (with 4 cores, 300s window):")
for typ, programs in ranking_with_server.items():
    print(f"  {typ}:")
    for p in programs:
        print(f"    {p['Program_s']}: {p['total_cpu_sec']}s "
              f"({p['cpu_pct']}% of {typ}, {p['server_cpu_pct']}% of server) "
              f"on {p['wp_count']} WPs")

# Verify BTC ZBAD_REPORT has server_cpu_pct
btc = ranking_with_server.get("BTC", [])
assert btc[0]["server_cpu_pct"] is not None, "server_cpu_pct should be set with core_count"
assert btc[0]["server_cpu_pct"] > 0, "server_cpu_pct should be > 0"
print(f"Verified: ZBAD_REPORT server_cpu_pct = {btc[0]['server_cpu_pct']}%")

# Test compute_wp_type_server_cpu
type_server = compute_wp_type_server_cpu(deltas, wall_clock_sec=300.0, core_count=4)
print(f"\ncompute_wp_type_server_cpu (4 cores, 300s):")
for typ, info in type_server.items():
    print(f"  {typ}: {info}")

assert "BTC" in type_server, "BTC should be in type_server_cpu"
assert "DIA" in type_server, "DIA should be in type_server_cpu"
assert "_all_wp" in type_server, "_all_wp should be present"
assert "_capacity" in type_server, "_capacity should be present"
assert type_server["_capacity"]["core_count"] == 4
assert type_server["_capacity"]["wall_clock_sec"] == 300.0
assert type_server["_all_wp"]["server_cpu_pct"] > 0
print(f"Verified: all WPs = {type_server['_all_wp']['server_cpu_pct']}% of server CPU")

# Verify BTC dominates over DIA
assert type_server["BTC"]["server_cpu_pct"] > type_server["DIA"]["server_cpu_pct"], \
    "BTC should consume more server CPU than DIA in this scenario"
print(f"Verified: BTC ({type_server['BTC']['server_cpu_pct']}%) > DIA ({type_server['DIA']['server_cpu_pct']}%)")

# Verify BTC ZBAD_REPORT dominates
btc = ranking.get("BTC", [])
assert btc[0]["Program_s"] == "ZBAD_REPORT", f"Expected ZBAD_REPORT at top, got {btc[0]['Program_s']}"
assert btc[0]["wp_count"] == 3, f"Expected 3 WPs, got {btc[0]['wp_count']}"
assert btc[0]["reliable"] is True
print("\nBTC ranking verified: ZBAD_REPORT is top with 3 WPs, reliable=True")

# Verify DIA SAPLSMTR is reliable (consecutive same program), SAPLSDTX is not
dia = ranking.get("DIA", [])
for p in dia:
    if p["Program_s"] == "SAPLSMTR":
        assert p["reliable"] is True, "SAPLSMTR should be reliable (consecutive snapshots)"
        print(f"DIA SAPLSMTR: reliable=True (consecutive snapshots) - CORRECT")

# ── CPU efficiency tests ─────────────────────────────────────────────────────
print("\n--- CPU Efficiency Tests ---")

# ZBAD_REPORT WPs should be CPU-bound (high delta relative to wall-clock)
zbad_deltas = [d for d in deltas if d["Program_s"] == "ZBAD_REPORT"]
for d in zbad_deltas:
    assert "cpu_efficiency" in d, f"WP#{d['No_d']} should have cpu_efficiency"
    assert d["cpu_efficiency"] >= 0.7, (
        f"WP#{d['No_d']} ZBAD_REPORT should be CPU-bound, got eff={d['cpu_efficiency']}")
    assert d.get("cpu_bound") is True, f"WP#{d['No_d']} should be cpu_bound=True"
print(f"Verified: {len(zbad_deltas)} ZBAD_REPORT WPs are all CPU-bound")

# RSMONICDP WP should be I/O-bound (10s CPU in 300s wall-clock = 0.033)
rsmon_deltas = [d for d in deltas if d["Program_s"] == "RSMONICDP"]
assert len(rsmon_deltas) == 1
rsmon = rsmon_deltas[0]
assert rsmon["cpu_efficiency"] <= 0.2, f"RSMONICDP should be I/O-bound, got eff={rsmon['cpu_efficiency']}"
assert rsmon.get("cpu_bound") is False, "RSMONICDP should be cpu_bound=False"
print(f"Verified: RSMONICDP is I/O-bound (eff={rsmon['cpu_efficiency']})")

# Time_s / max_request_runtime tests
zbad13 = [d for d in deltas if d["No_d"] == 13][0]
assert zbad13.get("max_request_runtime_sec") == 595, \
    f"WP#13 max_request_runtime should be 595, got {zbad13.get('max_request_runtime_sec')}"
print(f"Verified: WP#13 max_request_runtime_sec = {zbad13['max_request_runtime_sec']}s")

# SAPLSMTR should be long-running (Time_s=410 > 300 threshold)
smtr = [d for d in deltas if d["Program_s"] == "SAPLSMTR"][0]
assert smtr.get("max_request_runtime_sec") == 410
print(f"Verified: SAPLSMTR max_request_runtime_sec = {smtr['max_request_runtime_sec']}s (long-running)")

# Short-lived DIA WPs should have low Time_s
short_dia = [d for d in deltas if d["No_d"] == 6][0]
assert short_dia.get("max_request_runtime_sec") == 5
print(f"Verified: WP#6 (short-lived) max_request_runtime_sec = {short_dia['max_request_runtime_sec']}s")

print("\nAll tests passed!")
