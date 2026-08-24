"""Generate the AMS MCP Server Performance Improvement Design Document (.docx)
with before/after architecture diagrams (Mermaid source) and detailed analysis.

Run:  python generate_design_doc.py
Output: AMS_MCP_Server_Design_Document.docx  (in the same directory)
        diagrams/  folder with .mmd Mermaid source files
"""
from __future__ import annotations
import os
from docx import Document
from docx.shared import Inches, Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.style import WD_STYLE_TYPE

# ── helpers ──────────────────────────────────────────────────────────────────

def set_cell_shading(cell, color_hex: str):
    """Set cell background color."""
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement
    shading = OxmlElement("w:shd")
    shading.set(qn("w:fill"), color_hex)
    shading.set(qn("w:val"), "clear")
    cell._tc.get_or_add_tcPr().append(shading)


def add_table_row(table, cells: list[str], header: bool = False, color: str = ""):
    row = table.add_row()
    for i, text in enumerate(cells):
        row.cells[i].text = text
        for p in row.cells[i].paragraphs:
            p.style = doc.styles["Normal"]
            for run in p.runs:
                run.font.size = Pt(10)
                if header:
                    run.bold = True
                    run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        if header:
            set_cell_shading(row.cells[i], "2F5496")
        elif color:
            set_cell_shading(row.cells[i], color)
    return row


# ── document ─────────────────────────────────────────────────────────────────

doc = Document()

# -- Styles --
style_normal = doc.styles["Normal"]
style_normal.font.name = "Calibri"
style_normal.font.size = Pt(11)
style_normal.paragraph_format.space_after = Pt(6)

# -- Title Page --
for _ in range(6):
    doc.add_paragraph("")

title = doc.add_paragraph()
title.alignment = WD_ALIGN_PARAGRAPH.CENTER
run = title.add_run("AMS MCP Server\nPerformance Improvement Design Document")
run.font.size = Pt(28)
run.font.color.rgb = RGBColor(0x2F, 0x54, 0x96)
run.bold = True

subtitle = doc.add_paragraph()
subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
run = subtitle.add_run("Token Optimization & Architecture Modernization")
run.font.size = Pt(16)
run.font.color.rgb = RGBColor(0x59, 0x56, 0x59)

doc.add_paragraph("")
meta = doc.add_paragraph()
meta.alignment = WD_ALIGN_PARAGRAPH.CENTER
run = meta.add_run(
    "Azure Monitor for SAP Solutions (AMS)\n"
    "MCP Server — Enterprise Edition\n\n"
    "Date: August 2026\n"
    "Version: 2.0\n"
    "Status: Implemented"
)
run.font.size = Pt(12)
run.font.color.rgb = RGBColor(0x59, 0x56, 0x59)

doc.add_page_break()

# ═══════════════════════════════════════════════════════════════════════════
# TABLE OF CONTENTS (manual — Word will update field codes)
# ═══════════════════════════════════════════════════════════════════════════
doc.add_heading("Table of Contents", level=1)
toc_items = [
    "1. Executive Summary",
    "2. Problem Statement",
    "3. Architecture Overview",
    "   3.1  Before: POC Architecture",
    "   3.2  After: Enterprise Architecture",
    "4. Performance Improvements — Detailed Design",
    "   4.1  Change 1: Generic Statistical Summarizer",
    "   4.2  Change 2: TOON Output Compaction",
    "   4.3  Change 3: Server-Side Result Cache & Progressive Disclosure",
    "   4.4  Change 4: Plugin-Based Analyzer Registry",
    "5. Data Flow Comparison",
    "5A. execute_query — Internal Pipeline Deep Dive",
    "   5A.1 Pipeline Steps",
    "   5A.2 What Gets Returned to the AI Agent",
    "5B. Cache Architecture — Hosting & Compute",
    "   5B.1 Where the Cache Lives",
    "   5B.2 Cache Parameters",
    "   5B.3 Where Compute Happens",
    "   5B.4 Data Flow: What Goes Where",
    "6. Token Usage Impact Analysis",
    "7. File Change Summary",
    "8. MCP Tool Interface (Before vs After)",
    "9. Testing Strategy",
    "10. Risks & Mitigations",
    "11. Appendix: Mermaid Diagram Source",
]
for item in toc_items:
    p = doc.add_paragraph(item)
    p.paragraph_format.space_after = Pt(2)

doc.add_page_break()

# ═══════════════════════════════════════════════════════════════════════════
# 1. EXECUTIVE SUMMARY
# ═══════════════════════════════════════════════════════════════════════════
doc.add_heading("1. Executive Summary", level=1)
doc.add_paragraph(
    "This document describes the performance optimization of the AMS (Azure Monitor for SAP Solutions) "
    "MCP Server — the Model Context Protocol server that enables AI agents (GitHub Copilot, Azure AI Foundry agents, Claude) "
    "to investigate SAP system health by querying Azure Log Analytics workspaces."
)
doc.add_paragraph(
    "The original POC implementation returned raw query results (up to 1,000 rows) directly to the AI model, "
    "consuming excessive tokens and degrading response quality. The optimized architecture introduces four key changes "
    "that reduce token consumption by ~78% while improving answer quality through structured, pre-classified findings."
)

doc.add_heading("Key Metrics", level=2)
t = doc.add_table(rows=1, cols=3)
t.alignment = WD_TABLE_ALIGNMENT.CENTER
t.style = "Table Grid"
add_table_row(t, ["Metric", "Before (POC)", "After (Enterprise)"], header=True)
add_table_row(t, ["Avg response payload per query", "~14 KB (raw rows)", "~3.1 KB (structured summary)"])
add_table_row(t, ["Token reduction", "Baseline", "~78% reduction"])
add_table_row(t, ["Tool calls for health check", "5-8 calls (query + classify + re-query)", "3-4 calls (query returns classified)"])
add_table_row(t, ["Analyzer code architecture", "1,350-line monolithic if/elif", "6 plugin modules (~250 lines avg)"])
add_table_row(t, ["MCP tools exposed", "4 (get_schema, execute_query, deeper_rca, run_full_rca)", "5 (+get_details for drill-down)"])
add_table_row(t, ["Adding a new SAP domain analyzer", "Edit 3 files, keep frozenset in sync", "Create 1 file with @register decorator"])
t.rows[0].cells[0].width = Cm(6)

doc.add_page_break()

# ═══════════════════════════════════════════════════════════════════════════
# 2. PROBLEM STATEMENT
# ═══════════════════════════════════════════════════════════════════════════
doc.add_heading("2. Problem Statement", level=1)

doc.add_heading("2.1 Token Waste from Raw Row Returns", level=2)
doc.add_paragraph(
    "When execute_query was called without an analysis_type, the server returned up to 1,000 raw rows "
    "directly in the MCP tool response. Each row contained 10-20 columns (many null or empty), "
    "resulting in 10-15 KB of JSON per query. The AI model then had to parse all rows to extract insights — "
    "consuming input tokens on raw data that could have been summarized server-side."
)

doc.add_heading("2.2 Verbose Classified Output", level=2)
doc.add_paragraph(
    "Even when analysis_type was set and the domain classifier ran, the output included null fields, "
    "empty arrays, and duplicated information. A classified result for 50 short dumps could still be 8 KB "
    "when a 1 KB summary with a drill-down pointer would suffice."
)

doc.add_heading("2.3 No Progressive Disclosure", level=2)
doc.add_paragraph(
    "The server had no mechanism to hold data server-side and let the model request details incrementally. "
    "Every query returned everything at once — the model either got all rows or none. "
    "There was no way to say 'show me more about the Database Error category' without re-running the query."
)

doc.add_heading("2.4 Monolithic Analyzer Code", level=2)
doc.add_paragraph(
    "All domain classification logic lived in a single 1,350-line file (deeper_rca_analysis.py) with a "
    "long if/elif chain. Adding a new SAP domain required editing 3 files and keeping a frozenset "
    "(CLASSIFIED_ANALYSIS_TYPES) in sync manually. This was error-prone and made the codebase hard to extend."
)

doc.add_page_break()

# ═══════════════════════════════════════════════════════════════════════════
# 3. ARCHITECTURE OVERVIEW
# ═══════════════════════════════════════════════════════════════════════════
doc.add_heading("3. Architecture Overview", level=1)

doc.add_heading("3.1 Before: POC Architecture", level=2)
doc.add_paragraph(
    "The diagram below shows the original data flow. Note that raw rows flow directly from Log Analytics "
    "to the AI model, and classification requires a separate tool call."
)

# BEFORE diagram description (text representation since we can't embed images directly)
before_box = doc.add_paragraph()
before_box.alignment = WD_ALIGN_PARAGRAPH.LEFT
run = before_box.add_run(
    "┌─────────────────────────────────────────────────────────────────────┐\n"
    "│                    BEFORE: POC Architecture                        │\n"
    "├─────────────────────────────────────────────────────────────────────┤\n"
    "│                                                                     │\n"
    "│  AI Model (Copilot/Foundry Agent)                                   │\n"
    "│       │                                                             │\n"
    "│       ├──► get_schema()          → Table metadata                   │\n"
    "│       │                                                             │\n"
    "│       ├──► execute_query(kql)    → Up to 1000 RAW ROWS  ◄── WASTE  │\n"
    "│       │         │                                                   │\n"
    "│       │         └──► la_client ──► Azure Log Analytics              │\n"
    "│       │                                                             │\n"
    "│       ├──► deeper_rca_analysis() → Classified (but verbose)         │\n"
    "│       │         │                                                   │\n"
    "│       │         └──► 1350-line if/elif chain                        │\n"
    "│       │                                                             │\n"
    "│       └──► [run_full_rca()]      → Full RCA (disabled)              │\n"
    "│                                                                     │\n"
    "│  Problems:                                                          │\n"
    "│   • Raw rows sent to model = high token consumption                 │\n"
    "│   • Classification is a separate call = extra round-trip            │\n"
    "│   • No caching = repeat queries re-execute                          │\n"
    "│   • Monolithic analyzer = hard to extend                            │\n"
    "└─────────────────────────────────────────────────────────────────────┘"
)
run.font.name = "Consolas"
run.font.size = Pt(8)

doc.add_paragraph("")

doc.add_heading("3.2 After: Enterprise Architecture", level=2)
doc.add_paragraph(
    "The optimized architecture introduces server-side summarization, caching, and a plugin registry. "
    "The AI model never sees raw rows — it receives compact summaries with a query_id for drill-down."
)

after_box = doc.add_paragraph()
after_box.alignment = WD_ALIGN_PARAGRAPH.LEFT
run = after_box.add_run(
    "┌──────────────────────────────────────────────────────────────────────────┐\n"
    "│                    AFTER: Enterprise Architecture                        │\n"
    "├──────────────────────────────────────────────────────────────────────────┤\n"
    "│                                                                          │\n"
    "│  AI Model (Copilot/Foundry Agent)                                        │\n"
    "│       │                                                                  │\n"
    "│       ├──► get_schema()                → Table metadata (unchanged)      │\n"
    "│       │                                                                  │\n"
    "│       ├──► execute_query(kql, type)     → COMPACT SUMMARY + query_id     │\n"
    "│       │         │                                                        │\n"
    "│       │         ├──► la_client ──► Azure Log Analytics                   │\n"
    "│       │         │                                                        │\n"
    "│       │         ├──► result_cache.store() ◄── Cache full rows server-side│\n"
    "│       │         │                                                        │\n"
    "│       │         ├──► [If type set] ──► Analyzer Registry ──► Plugin      │\n"
    "│       │         │         └──► toon_formatter ──► Compact output         │\n"
    "│       │         │                                                        │\n"
    "│       │         └──► [If no type] ──► generic_summarizer                 │\n"
    "│       │                   └──► Stats + 3 samples (never raw rows)        │\n"
    "│       │                                                                  │\n"
    "│       ├──► get_details(query_id, cat)   → Drill-down from cache  ◄── NEW│\n"
    "│       │                                                                  │\n"
    "│       ├──► deeper_rca_analysis()        → Thin wrapper → Registry        │\n"
    "│       │                                                                  │\n"
    "│       └──► [run_full_rca()]             → Full RCA (disabled)            │\n"
    "│                                                                          │\n"
    "│  Benefits:                                                               │\n"
    "│   • ~78% token reduction (summaries, not raw rows)                       │\n"
    "│   • Auto-classification in execute_query (fewer round-trips)             │\n"
    "│   • Progressive disclosure via get_details (drill on demand)             │\n"
    "│   • Plugin analyzers (@register decorator = 1 file to add new domain)    │\n"
    "└──────────────────────────────────────────────────────────────────────────┘"
)
run.font.name = "Consolas"
run.font.size = Pt(8)

doc.add_paragraph(
    "See Appendix for Mermaid diagram source files that can be rendered as SVG/PNG for presentations."
)

doc.add_page_break()

# ═══════════════════════════════════════════════════════════════════════════
# 4. PERFORMANCE IMPROVEMENTS — DETAILED DESIGN
# ═══════════════════════════════════════════════════════════════════════════
doc.add_heading("4. Performance Improvements — Detailed Design", level=1)

# -- Change 1 --
doc.add_heading("4.1 Change 1: Generic Statistical Summarizer", level=2)
doc.add_heading("Problem", level=3)
doc.add_paragraph(
    "When execute_query was called without analysis_type (e.g., for ad-hoc OS metric queries, HANA load "
    "history, or custom KQL), the server returned up to 1,000 raw rows directly. The AI model received "
    "all columns and all rows — most of which were redundant or irrelevant for answering the question."
)
doc.add_heading("Solution", level=3)
doc.add_paragraph(
    "A new module tools/generic_summarizer.py provides a fallback statistical summary for any query "
    "result that has no matching domain analyzer. It:"
)
bullets = [
    "Detects column types automatically (numeric, categorical, time) via heuristic analysis of the first 50 rows",
    "Computes statistics for numeric columns: min, max, avg, p95",
    "Computes distributions for categorical columns: top-5 value counts",
    "Identifies time range for datetime columns: earliest → latest",
    "Returns only 3 representative sample rows (first, middle, last) instead of all rows",
    "Never returns raw rows to the model — the full dataset stays in the server-side cache",
]
for b in bullets:
    doc.add_paragraph(b, style="List Bullet")

doc.add_heading("Token Impact", level=3)
doc.add_paragraph(
    "For a query returning 500 rows × 12 columns: Before = ~50 KB payload. After = ~1.2 KB "
    "(stats + 3 samples). Reduction: ~96%."
)

doc.add_heading("File", level=3)
doc.add_paragraph("tools/generic_summarizer.py (NEW — ~170 lines)")

doc.add_paragraph("")

# -- Change 2 --
doc.add_heading("4.2 Change 2: TOON Output Compaction", level=2)
doc.add_heading("Problem", level=3)
doc.add_paragraph(
    "Classified analyzer outputs (short dumps, system logs, etc.) included null values, empty strings, "
    "empty arrays, and duplicated entries. A short dump analysis of 50 dumps might return 8 KB of JSON "
    "where 60% of the bytes were nulls and empty fields."
)
doc.add_heading("Solution", level=3)
doc.add_paragraph(
    'TOON (Token-Optimized Output Notation) formatting inspired by the "TOON Protocol" research and '
    "Cloudflare's MCP token optimization. The module tools/toon_formatter.py provides:"
)
bullets = [
    "compact(obj): Recursively strips null values, empty strings, empty lists/dicts from any nested structure",
    "format_summary_response(classified, query_id, row_count): Creates a tier-1 summary with category breakdown, "
    "top error patterns, and a query_id pointer for drill-down",
    "Adds _hint field instructing the model: 'Use get_details(query_id, category) to drill into specific findings'",
    "Deduplicates list entries where possible",
]
for b in bullets:
    doc.add_paragraph(b, style="List Bullet")

doc.add_heading("Token Impact", level=3)
doc.add_paragraph(
    "For a classified short dump output: Before = ~8 KB verbose. After = ~2.5 KB compact + drill-down pointer. "
    "Reduction: ~70% of classified output size."
)

doc.add_heading("File", level=3)
doc.add_paragraph("tools/toon_formatter.py (NEW — ~110 lines)")

doc.add_paragraph("")

# -- Change 3 --
doc.add_heading("4.3 Change 3: Server-Side Result Cache & Progressive Disclosure", level=2)
doc.add_heading("Problem", level=3)
doc.add_paragraph(
    "The server was stateless — every query result was returned in full and then discarded. If the model "
    "wanted to see more details about a specific finding category, it had to re-execute the entire query. "
    "This doubled token consumption and Log Analytics query costs."
)
doc.add_heading("Solution", level=3)
doc.add_paragraph(
    "An in-memory server-side cache (tools/result_cache.py) stores query results keyed by a deterministic "
    "query_id (hash of KQL + SID). Combined with a new MCP tool get_details, this enables progressive disclosure:"
)

doc.add_paragraph("Step 1: execute_query returns a compact summary + query_id (e.g., q_ab12cd34)", style="List Number")
doc.add_paragraph("Step 2: Model decides which category or finding to drill into", style="List Number")
doc.add_paragraph("Step 3: get_details(query_id, category='Database Error', offset=0, limit=5) returns just those rows", style="List Number")
doc.add_paragraph("Step 4: Model can paginate further with offset=5, limit=5 if needed", style="List Number")

doc.add_heading("Cache Design", level=3)
t = doc.add_table(rows=1, cols=2)
t.style = "Table Grid"
add_table_row(t, ["Parameter", "Value"], header=True)
add_table_row(t, ["Storage", "In-memory dict (server process lifetime)"])
add_table_row(t, ["TTL", "300 seconds (configurable)"])
add_table_row(t, ["Max entries", "50 (LRU eviction)"])
add_table_row(t, ["Key format", "q_{first 8 chars of SHA-256(kql + sid)}"])
add_table_row(t, ["Stored data", "Raw rows, classified result (if any), metadata"])

doc.add_heading("Token Impact", level=3)
doc.add_paragraph(
    "Eliminates repeat query execution. A drill-down via get_details returns only 5 rows (default) "
    "instead of re-running the full query. Estimated savings: 50-80% reduction in follow-up query tokens."
)

doc.add_heading("Files", level=3)
doc.add_paragraph("tools/result_cache.py (NEW — ~100 lines)")
doc.add_paragraph("server.py — new get_details tool registered")

doc.add_paragraph("")

# -- Change 4 --
doc.add_heading("4.4 Change 4: Plugin-Based Analyzer Registry", level=2)
doc.add_heading("Problem", level=3)
doc.add_paragraph(
    "All SAP domain classification logic was in a single 1,350-line file (tools/deeper_rca_analysis.py) "
    "with an if/elif chain routing to internal functions. Adding a new domain (e.g., HANA DB analysis) required:"
)
doc.add_paragraph("Adding a new elif branch in deeper_rca_analysis.py", style="List Number")
doc.add_paragraph("Adding the type name to CLASSIFIED_ANALYSIS_TYPES frozenset in schema_registry.py", style="List Number")
doc.add_paragraph("Keeping the server.py instructions string in sync", style="List Number")

doc.add_heading("Solution", level=3)
doc.add_paragraph(
    "A plugin-based analyzer registry (analyzers/ package) with auto-discovery. Each analyzer is a "
    "standalone Python module that self-registers using a @register decorator:"
)

code = doc.add_paragraph()
run = code.add_run(
    '# analyzers/short_dumps.py\n'
    'from analyzers import register\n\n'
    '@register("short_dumps")\n'
    'def analyze(rows: list[dict], context: str = "") -> dict:\n'
    '    """ST22 Short Dump classification."""\n'
    '    # ... domain logic ...\n'
)
run.font.name = "Consolas"
run.font.size = Pt(9)

doc.add_paragraph("To add a new SAP domain analyzer, a developer now only needs to:")
doc.add_paragraph("Create a new file in analyzers/ (e.g., analyzers/hana_alerts.py)", style="List Number")
doc.add_paragraph('Add @register("hana_alerts") decorator to the analyze function', style="List Number")
doc.add_paragraph("Done — auto-discovered at import time, no other files to edit", style="List Number")

doc.add_heading("Registry Design", level=3)
t = doc.add_table(rows=1, cols=2)
t.style = "Table Grid"
add_table_row(t, ["Feature", "Detail"], header=True)
add_table_row(t, ["Discovery", "pkgutil.iter_modules() scans analyzers/ at import time"])
add_table_row(t, ["Registration", "@register(*analysis_types) decorator"])
add_table_row(t, ["Lookup", "get_analyzer(type) returns the function or None"])
add_table_row(t, ["Type listing", "get_all_analysis_types() returns set of all registered types"])
add_table_row(t, ["Multi-type support", 'One analyzer can register for multiple types (e.g., @register("availability", "SAP_system_availability"))'])

doc.add_heading("Current Registered Analyzers", level=3)
t = doc.add_table(rows=1, cols=3)
t.style = "Table Grid"
add_table_row(t, ["File", "Registered Types", "Lines"], header=True)
add_table_row(t, ["analyzers/short_dumps.py", "short_dumps", "~220"])
add_table_row(t, ["analyzers/system_logs.py", "system_logs", "~150"])
add_table_row(t, ["analyzers/batch_jobs.py", "batch_jobs", "~180"])
add_table_row(t, ["analyzers/ha_cluster.py", "ha_cluster", "~270"])
add_table_row(t, ["analyzers/os_metrics.py", "os_metrics", "~200"])
add_table_row(t, ["analyzers/availability.py", "availability, SAP_system_availability, SAP_Process_Availability", "~250"])

doc.add_heading("Files", level=3)
doc.add_paragraph("analyzers/__init__.py (NEW — registry + auto-discovery)")
doc.add_paragraph("analyzers/*.py (NEW — 6 plugin modules)")
doc.add_paragraph("tools/deeper_rca_analysis.py (REWRITTEN — 1,350 → 62 lines, thin wrapper)")

doc.add_page_break()

# ═══════════════════════════════════════════════════════════════════════════
# 5. DATA FLOW COMPARISON
# ═══════════════════════════════════════════════════════════════════════════
doc.add_heading("5. Data Flow Comparison", level=1)

doc.add_heading("5.1 Before: Unclassified Query", level=2)
flow = doc.add_paragraph()
run = flow.add_run(
    "Model → execute_query(kql, sid='MSS') → la_client → Log Analytics\n"
    "                                                         │\n"
    "                                       ┌─────────────────┘\n"
    "                                       │ 1000 raw rows (14 KB)\n"
    "                                       ▼\n"
    "                                    Model (wastes tokens parsing rows)\n"
    "                                       │\n"
    "                                       └──► deeper_rca_analysis(rows, type)\n"
    "                                                    │ classified output (8 KB)\n"
    "                                                    ▼\n"
    "                                                 Model (finally gets answer)\n"
    "\n"
    "Total: 2 tool calls, ~22 KB tokens consumed"
)
run.font.name = "Consolas"
run.font.size = Pt(9)

doc.add_heading("5.2 After: Classified Query (auto)", level=2)
flow = doc.add_paragraph()
run = flow.add_run(
    "Model → execute_query(kql, sid='MSS', analysis_type='short_dumps')\n"
    "           │\n"
    "           ├──► la_client → Log Analytics → rows\n"
    "           ├──► result_cache.store(query_id, rows)\n"
    "           ├──► analyzer_registry → short_dumps.analyze(rows)\n"
    "           ├──► toon_formatter.format_summary_response()\n"
    "           │\n"
    "           └──► Model receives: compact summary + query_id (~2.5 KB)\n"
    "\n"
    "Optional drill-down:\n"
    "Model → get_details(query_id, 'Database Error', limit=5)\n"
    "           └──► result_cache → 5 filtered rows (~0.8 KB)\n"
    "\n"
    "Total: 1-2 tool calls, ~3.3 KB tokens consumed"
)
run.font.name = "Consolas"
run.font.size = Pt(9)

doc.add_heading("5.3 After: Unclassified Query (generic)", level=2)
flow = doc.add_paragraph()
run = flow.add_run(
    "Model → execute_query(kql, sid='MSS')   ← no analysis_type\n"
    "           │\n"
    "           ├──► la_client → Log Analytics → 500 rows\n"
    "           ├──► result_cache.store(query_id, rows)\n"
    "           ├──► generic_summarizer.summarize()\n"
    "           │        └── stats + 3 sample rows\n"
    "           ├──► toon_formatter.compact()\n"
    "           │\n"
    "           └──► Model receives: statistical summary + query_id (~1.2 KB)\n"
    "\n"
    "Total: 1 tool call, ~1.2 KB tokens consumed (vs 14 KB before)"
)
run.font.name = "Consolas"
run.font.size = Pt(9)

doc.add_page_break()

# ═══════════════════════════════════════════════════════════════════════════
# 5A. EXECUTE_QUERY DEEP DIVE
# ═══════════════════════════════════════════════════════════════════════════
doc.add_heading("5A. execute_query — Internal Pipeline Deep Dive", level=1)

doc.add_paragraph(
    "execute_query is the workhorse tool of the MCP server. It is the only tool that "
    "communicates with Azure Log Analytics. Below is a step-by-step breakdown of its "
    "internal processing pipeline."
)

doc.add_heading("5A.1 Pipeline Steps", level=2)

steps = [
    ("1. Input Validation", [
        "SID validation: must be 1–10 uppercase alphanumeric (e.g., 'MSS', 'PRD') or 'ALL'",
        "Time resolution: start_time+end_time → absolute range; else timespan_hours → relative window; else default 24h",
        "If KQL contains its own time filter (ago(), between()), API window is widened to 30 days to avoid silent clipping",
    ]),
    ("2. Security Gate (Read-Only Check)", [
        "Blocks KQL management commands (lines starting with '.')",
        "Blocks SQL-style write keywords: INSERT INTO, UPDATE SET, DELETE FROM, DROP TABLE, TRUNCATE",
        "Strips comments before checking to prevent bypass via //INSERT INTO...",
    ]),
    ("3. Row Cap Enforcement", [
        "If the KQL has no '| take N' or '| limit N' clause, the server auto-appends '| take 1000'",
        "Prevents runaway queries from returning millions of rows",
        "Max configurable via MAX_QUERY_ROWS in .env (default: 1000)",
    ]),
    ("4. Query Execution", [
        "la_client.execute_kql() sends the validated KQL to Azure Log Analytics via Azure SDK",
        "Uses DefaultAzureCredential or a static bearer token (configured in .env)",
        "Workspace is resolved via SID_WORKSPACE_MAP or falls back to AZURE_LOG_ANALYTICS_WORKSPACE_ID",
        "Returns: list of row dicts + metadata",
    ]),
    ("5. Result Caching", [
        "A query_id is generated: q_{SHA256(kql:sid:timestamp)[:8]}",
        "Full rows + metadata are stored in the in-memory result_cache",
        "This enables get_details() drill-down without re-running the query",
        "Cache TTL: 300 seconds, max 50 entries, LRU eviction",
    ]),
    ("6a. Domain Classification Path (if analysis_type provided)", [
        "Looks up the analyzer from the plugin registry: get_analyzer(analysis_type)",
        "If found: runs the domain-specific analyzer (e.g., short_dumps.analyze(rows, context))",
        "Analyzer classifies rows into categories with investigation hints",
        "Result is formatted via toon_formatter.format_summary_response()",
        "Output: compact summary (~2-3 KB) with category_breakdown + query_id",
    ]),
    ("6b. Generic Summary Path (if no analysis_type or unknown type)", [
        "generic_summarizer.summarize() detects column types (numeric/categorical/time)",
        "Computes statistics: min/max/avg/p95 for numeric, top-5 distribution for categorical",
        "Returns 3 representative sample rows (first, middle, last) — never all rows",
        "Result is compacted via toon_formatter.compact()",
        "Output: statistical summary (~1-2 KB) with query_id",
    ]),
]

for step_title, bullets in steps:
    doc.add_heading(step_title, level=3)
    for b in bullets:
        doc.add_paragraph(b, style="List Bullet")

doc.add_heading("5A.2 What Gets Returned to the AI Agent", level=2)
doc.add_paragraph(
    "The AI agent ALWAYS receives a response from execute_query — but it is NEVER raw rows. "
    "The response is one of:"
)
t = doc.add_table(rows=1, cols=3)
t.style = "Table Grid"
add_table_row(t, ["Scenario", "What Agent Receives", "Size"], header=True)
add_table_row(t, [
    "analysis_type matches a registered analyzer",
    "Classified summary: category_breakdown, error_patterns, investigation_hints, query_id, _hint for drill-down",
    "~2-3 KB"
])
add_table_row(t, [
    "No analysis_type (or unknown type)",
    "Generic statistical summary: numeric stats, categorical distributions, 3 sample rows, query_id",
    "~1-2 KB"
])
add_table_row(t, [
    "Error / Rejected (invalid KQL, bad SID)",
    "Error object with descriptive message",
    "~0.2 KB"
])
add_table_row(t, [
    "No rows returned",
    "no_data status with recommendation to verify time range",
    "~0.1 KB"
])

doc.add_paragraph("")
doc.add_paragraph(
    "The full row set is retained in the server-side cache. The agent can drill into it "
    "via get_details(query_id, category) at any time within the 300-second TTL window."
)

doc.add_page_break()

# ═══════════════════════════════════════════════════════════════════════════
# 5B. CACHE ARCHITECTURE
# ═══════════════════════════════════════════════════════════════════════════
doc.add_heading("5B. Cache Architecture — Hosting & Compute", level=1)

doc.add_heading("5B.1 Where the Cache Lives", level=2)
doc.add_paragraph(
    "The result cache is an in-memory Python dictionary within the MCP server process. "
    "There is no external cache service (no Redis, no Cosmos DB, no file system). "
    "This is a deliberate design choice for simplicity and low latency."
)

t = doc.add_table(rows=1, cols=3)
t.style = "Table Grid"
add_table_row(t, ["Deployment Mode", "Cache Location", "Lifecycle"], header=True)
add_table_row(t, [
    "Local (stdio) — python server.py",
    "RAM of the Python process on developer's machine",
    "Lost on Ctrl+C or process exit"
])
add_table_row(t, [
    "Azure Container Apps (HTTP/SSE)",
    "RAM of the container instance",
    "Lost on container restart/scale-down"
])
add_table_row(t, [
    "Azure App Service",
    "RAM of the App Service worker process",
    "Lost on app restart or slot swap"
])

doc.add_paragraph("")
doc.add_paragraph(
    "Since cache loss only means the agent must re-run a query (cheap — ~2s latency, ~$0.001 per query), "
    "the trade-off of ephemeral RAM cache vs. persistent external store is strongly in favor of simplicity."
)

doc.add_heading("5B.2 Cache Parameters", level=2)
t = doc.add_table(rows=1, cols=3)
t.style = "Table Grid"
add_table_row(t, ["Parameter", "Value", "Rationale"], header=True)
add_table_row(t, ["Storage type", "Python dict (module-level)", "Zero-latency lookup, no serialization overhead"])
add_table_row(t, ["TTL", "300 seconds (5 min)", "Long enough for multi-step investigation, short enough to reflect fresh data"])
add_table_row(t, ["Max entries", "50", "Prevents memory leak; typical investigation uses 5-10 queries"])
add_table_row(t, ["Eviction policy", "Expired entries removed first; then LRU (oldest created_at)", "Balances freshness and recency"])
add_table_row(t, ["Key format", "q_{SHA256(kql:sid:timestamp)[:8]}", "Short, unique, URL-safe"])
add_table_row(t, ["Stored per entry", "Full row list + classified output + metadata (SID, KQL, timestamps)", "Enables both raw pagination and category drill-down"])
add_table_row(t, ["Memory estimate", "~50 entries × 1000 rows × 0.5 KB/row = ~25 MB max", "Well within container/App Service limits"])

doc.add_heading("5B.3 Where Compute Happens", level=2)
doc.add_paragraph(
    "The MCP server pipeline involves two compute locations:"
)

t = doc.add_table(rows=1, cols=4)
t.style = "Table Grid"
add_table_row(t, ["Step", "Where", "What Runs", "Cost/Latency"], header=True)
add_table_row(t, [
    "KQL query execution",
    "Azure Log Analytics (Microsoft-managed Kusto cluster)",
    "Distributed query engine scans workspace tables",
    "~1-3 seconds; billed per GB scanned"
])
add_table_row(t, [
    "Domain classification (analyzer)",
    "MCP Server process CPU",
    "Pure Python — loops through rows, categorizes via domain_registry.py rules",
    "~1-5 ms for 1000 rows"
])
add_table_row(t, [
    "Generic summarization",
    "MCP Server process CPU",
    "Column type detection + statistics computation (min/max/avg/p95)",
    "~2-10 ms for 1000 rows"
])
add_table_row(t, [
    "TOON compaction",
    "MCP Server process CPU",
    "Recursive null/empty stripping + summary formatting",
    "<1 ms"
])
add_table_row(t, [
    "Cache store/retrieve",
    "MCP Server process RAM",
    "Dict insert/lookup by query_id",
    "<0.1 ms"
])
add_table_row(t, [
    "get_details() slice",
    "MCP Server process RAM + CPU",
    "Dict lookup + list slice or category filter",
    "<1 ms"
])

doc.add_paragraph("")
doc.add_paragraph(
    "Key insight: The expensive operation (querying Log Analytics: ~1-3 seconds, billed) happens ONCE. "
    "All subsequent analysis, formatting, and drill-down operations are local CPU/RAM with sub-millisecond latency and zero cost."
)

doc.add_heading("5B.4 Data Flow: What Goes Where", level=2)
flow = doc.add_paragraph()
run = flow.add_run(
    "┌─────────────────────────────────────────────────────────────────────────────────┐\n"
    "│                                                                                 │\n"
    "│  Azure Log Analytics (Kusto)          MCP Server (Python Process)    AI Agent   │\n"
    "│  ─────────────────────────           ──────────────────────────────  ─────────  │\n"
    "│                                                                                 │\n"
    "│  ┌───────────────┐                   ┌──────────────────────────┐               │\n"
    "│  │ Workspace     │  ── 55 rows ──►   │ RAM:                     │               │\n"
    "│  │ (billions of  │     (full data)   │  result_cache[q_abc] =   │               │\n"
    "│  │  log rows)    │                   │    { rows: [55 items],   │               │\n"
    "│  └───────────────┘                   │      classified: {...},  │               │\n"
    "│                                      │      sid: 'MSS', ... }   │               │\n"
    "│       ▲                              │                          │               │\n"
    "│       │ KQL                          │  CPU:                    │    ┌────────┐ │\n"
    "│       │ query                        │   analyzer(rows) → 2ms   │    │ Agent  │ │\n"
    "│       │                              │   summarizer()   → 5ms   │───►│receives│ │\n"
    "│       │                              │   formatter()    → 0.5ms │    │~3 KB   │ │\n"
    "│       │                              │                          │    │summary │ │\n"
    "│       │                              └──────────────────────────┘    └────────┘ │\n"
    "│       │                                      │                          │       │\n"
    "│       │                                      │ get_details()            │       │\n"
    "│  NOT re-queried  ◄─── X ────────────────    │ (from cache, <1ms) ◄─────┘       │\n"
    "│                                              │                                  │\n"
    "│                                              └──► 5 filtered rows → Agent       │\n"
    "└─────────────────────────────────────────────────────────────────────────────────┘\n"
)
run.font.name = "Consolas"
run.font.size = Pt(8)

doc.add_paragraph(
    "The critical point: get_details() NEVER re-queries Azure Log Analytics. It serves data "
    "entirely from the server's RAM cache. This saves both time (~2 seconds) and money "
    "(Log Analytics is billed per GB scanned)."
)

doc.add_page_break()

# ═══════════════════════════════════════════════════════════════════════════
# 6. TOKEN USAGE IMPACT ANALYSIS
# ═══════════════════════════════════════════════════════════════════════════
doc.add_heading("6. Token Usage Impact Analysis", level=1)
doc.add_paragraph(
    "The following analysis is based on a real MSS system health check executed against the production "
    "Log Analytics workspace on August 18, 2026."
)

doc.add_heading("6.1 Test Scenario: 'Get the health of MSS system'", level=2)
t = doc.add_table(rows=1, cols=5)
t.style = "Table Grid"
add_table_row(t, ["Query", "Rows", "Old Payload", "New Payload", "Reduction"], header=True)
add_table_row(t, ["System Availability (55 instances)", "55", "~11 KB", "~0.4 KB", "96%"])
add_table_row(t, ["Short Dumps (6 dumps, 5 types)", "6", "~3 KB + follow-up call", "~2.5 KB (pre-classified)", "17% + 1 saved call"])
add_table_row(t, ["Batch Jobs (0 cancelled)", "0", "~0.2 KB", "~0.2 KB", "—"])
add_table_row(t, ["TOTAL", "61", "~14.2 KB + extra calls", "~3.1 KB", "~78%"], color="E2EFDA")

doc.add_heading("6.2 Projected Impact at Scale", level=2)
t = doc.add_table(rows=1, cols=4)
t.style = "Table Grid"
add_table_row(t, ["Scenario", "Queries/Day", "Old Tokens/Day (est)", "New Tokens/Day (est)"], header=True)
add_table_row(t, ["Single SID health check", "10", "~50K tokens", "~11K tokens"])
add_table_row(t, ["Multi-SID monitoring (5 SIDs)", "50", "~250K tokens", "~55K tokens"])
add_table_row(t, ["Full RCA investigation", "20", "~200K tokens", "~44K tokens"])
add_table_row(t, ["Daily aggregate", "80", "~500K tokens", "~110K tokens"], color="E2EFDA")

doc.add_page_break()

# ═══════════════════════════════════════════════════════════════════════════
# 7. FILE CHANGE SUMMARY
# ═══════════════════════════════════════════════════════════════════════════
doc.add_heading("7. File Change Summary", level=1)

t = doc.add_table(rows=1, cols=4)
t.style = "Table Grid"
add_table_row(t, ["File", "Status", "Lines", "Purpose"], header=True)
add_table_row(t, ["tools/result_cache.py", "NEW", "~100", "Server-side in-memory cache for progressive disclosure"])
add_table_row(t, ["tools/generic_summarizer.py", "NEW", "~170", "Statistical summarizer for unclassified queries"])
add_table_row(t, ["tools/toon_formatter.py", "NEW", "~110", "TOON output compaction (strip nulls, format summaries)"])
add_table_row(t, ["analyzers/__init__.py", "NEW", "~60", "Plugin registry with @register decorator + auto-discovery"])
add_table_row(t, ["analyzers/short_dumps.py", "NEW", "~220", "ST22 dump classification (moved from deeper_rca)"])
add_table_row(t, ["analyzers/system_logs.py", "NEW", "~150", "SM21 system log classification"])
add_table_row(t, ["analyzers/batch_jobs.py", "NEW", "~180", "SM37 batch job classification"])
add_table_row(t, ["analyzers/ha_cluster.py", "NEW", "~270", "Pacemaker/Corosync HA cluster classification"])
add_table_row(t, ["analyzers/os_metrics.py", "NEW", "~200", "Prometheus OS node exporter classification"])
add_table_row(t, ["analyzers/availability.py", "NEW", "~250", "SAP instance availability classification"])
add_table_row(t, ["tools/execute_query.py", "MODIFIED", "~120", "Integrated cache, summarizer, TOON formatter, registry"])
add_table_row(t, ["tools/deeper_rca_analysis.py", "REWRITTEN", "62", "Thin wrapper delegating to analyzer registry"])
add_table_row(t, ["server.py", "MODIFIED", "~160", "Added get_details tool, updated imports & instructions"])
add_table_row(t, ["tools/analyze_results.py", "DELETED", "—", "Dead code removed"])

doc.add_page_break()

# ═══════════════════════════════════════════════════════════════════════════
# 8. MCP TOOL INTERFACE
# ═══════════════════════════════════════════════════════════════════════════
doc.add_heading("8. MCP Tool Interface (Before vs After)", level=1)

doc.add_heading("8.1 Before: 4 Tools", level=2)
t = doc.add_table(rows=1, cols=3)
t.style = "Table Grid"
add_table_row(t, ["Tool", "Purpose", "Notes"], header=True)
add_table_row(t, ["get_schema", "Table metadata", ""])
add_table_row(t, ["execute_query", "Run KQL, return raw rows or auto-classify", "Returns raw rows when no analysis_type"])
add_table_row(t, ["deeper_rca_analysis", "Classify raw rows after the fact", "Monolithic 1350-line implementation"])
add_table_row(t, ["run_full_rca", "Full 8-step automated RCA", "Disabled (too expensive)"])

doc.add_heading("8.2 After: 5 Tools", level=2)
t = doc.add_table(rows=1, cols=3)
t.style = "Table Grid"
add_table_row(t, ["Tool", "Purpose", "Notes"], header=True)
add_table_row(t, ["get_schema", "Table metadata", "Unchanged"])
add_table_row(t, ["execute_query", "Run KQL → auto-classify → compact summary + query_id", "Never returns raw rows; always returns query_id"])
add_table_row(t, ["get_details", "Drill into cached result by category or paginate", "NEW — enables progressive disclosure"])
add_table_row(t, ["deeper_rca_analysis", "Manual re-classification (backward compat)", "Now 62-line thin wrapper → registry"])
add_table_row(t, ["run_full_rca", "Full 8-step automated RCA", "Disabled (unchanged)"])

doc.add_heading("8.3 get_details — New Tool Specification", level=2)
t = doc.add_table(rows=1, cols=4)
t.style = "Table Grid"
add_table_row(t, ["Parameter", "Type", "Default", "Description"], header=True)
add_table_row(t, ["query_id", "str", "(required)", "The query_id returned by execute_query (e.g., q_ab12cd34)"])
add_table_row(t, ["category", "str", '""', "Filter to a specific finding category. Leave blank for raw row pagination."])
add_table_row(t, ["offset", "int", "0", "Pagination start position"])
add_table_row(t, ["limit", "int", "5", "Rows per page (max 50)"])

doc.add_page_break()

# ═══════════════════════════════════════════════════════════════════════════
# 9. TESTING STRATEGY
# ═══════════════════════════════════════════════════════════════════════════
doc.add_heading("9. Testing Strategy", level=1)

doc.add_heading("9.1 Unit Tests (Offline)", level=2)
doc.add_paragraph("Run: python test_pipeline.py")
doc.add_paragraph("Tests all new components with mock data — no Azure connection needed:")
bullets = [
    "Analyzer registry: verifies all 8 types auto-discovered",
    "Short dumps analyzer: tests classification of mock dump data",
    "Result cache: store/retrieve/pagination/category filter",
    "Generic summarizer: numeric/categorical/time column detection and stats",
    "TOON formatter: null stripping, compact output, format_summary_response",
    "Deeper RCA analysis wrapper: backward compat, error/no-data/unknown-type paths",
    "HA cluster analyzer: mock Pacemaker data",
    "OS metrics analyzer: mock Prometheus data",
]
for b in bullets:
    doc.add_paragraph(b, style="List Bullet")

doc.add_heading("9.2 Integration Tests (Live)", level=2)
doc.add_paragraph("Configure .vscode/mcp.json and start sap-local-mcp server, then test via Copilot chat:")
bullets = [
    "get_schema() → verify 23 tables returned",
    "execute_query with analysis_type → verify compact summary + query_id returned",
    "get_details(query_id, category) → verify drill-down returns filtered rows",
    "execute_query without analysis_type → verify generic summarizer output (not raw rows)",
]
for b in bullets:
    doc.add_paragraph(b, style="List Bullet")

doc.add_page_break()

# ═══════════════════════════════════════════════════════════════════════════
# 10. RISKS & MITIGATIONS
# ═══════════════════════════════════════════════════════════════════════════
doc.add_heading("10. Risks & Mitigations", level=1)

t = doc.add_table(rows=1, cols=3)
t.style = "Table Grid"
add_table_row(t, ["Risk", "Impact", "Mitigation"], header=True)
add_table_row(t, [
    "In-memory cache lost on server restart",
    "Low — cache is for convenience, not persistence. Queries can be re-executed.",
    "Cache TTL is 300s; server restart clears cache gracefully. Could add Redis/disk persistence if needed."
])
add_table_row(t, [
    "Generic summarizer misclassifies column types",
    "Low — affects only unclassified queries. Domain-specific analyzers bypass this.",
    "Heuristic uses 50-row sample + name conventions. Easy to tune thresholds."
])
add_table_row(t, [
    "TOON compaction strips useful null information",
    "Very Low — nulls in SAP data are almost always 'no value' not 'null is meaningful'.",
    "compact() only strips None/empty — non-null values are always preserved."
])
add_table_row(t, [
    "Plugin auto-discovery imports malicious code",
    "Low — analyzers/ directory is part of the trusted codebase.",
    "Only modules in the analyzers/ package directory are loaded. No user-uploaded code."
])
add_table_row(t, [
    "Backward compatibility with existing agents using deeper_rca_analysis",
    "Medium — existing agents may depend on the old output format.",
    "deeper_rca_analysis still exists as a thin wrapper with same function signature. Output is compacted but structurally similar."
])

doc.add_page_break()

# ═══════════════════════════════════════════════════════════════════════════
# 11. APPENDIX: MERMAID DIAGRAMS
# ═══════════════════════════════════════════════════════════════════════════
doc.add_heading("11. Appendix: Mermaid Diagram Source", level=1)
doc.add_paragraph(
    "The following Mermaid diagram sources can be rendered at mermaid.live, in VS Code with the "
    "Mermaid extension, or in any Markdown renderer that supports Mermaid fenced code blocks. "
    "They are also saved as .mmd files in the diagrams/ folder."
)

# BEFORE diagram
doc.add_heading("11.1 Before Architecture (Mermaid)", level=2)
before_mermaid = '''\
graph TD
    A["AI Model<br/>(Copilot / Foundry Agent)"] -->|"1. get_schema()"| B["MCP Server<br/>server.py"]
    A -->|"2. execute_query(kql, sid)"| B
    B -->|"KQL query"| C["la_client.py"]
    C -->|"Azure SDK"| D["Azure Log Analytics<br/>Workspace"]
    D -->|"Up to 1000 raw rows"| C
    C -->|"Raw rows (14 KB)"| B
    B -->|"❌ Raw rows returned<br/>to model"| A
    A -->|"3. deeper_rca_analysis(rows, type)"| B
    B -->|"if/elif chain<br/>(1350 lines)"| E["deeper_rca_analysis.py<br/>Monolithic Analyzer"]
    E -->|"Classified output (8 KB)"| B
    B -->|"Verbose classified"| A

    style A fill:#4472C4,color:#fff
    style B fill:#ED7D31,color:#fff
    style D fill:#70AD47,color:#fff
    style E fill:#FFC000,color:#000
'''
code_p = doc.add_paragraph()
run = code_p.add_run(before_mermaid)
run.font.name = "Consolas"
run.font.size = Pt(8)

# AFTER diagram
doc.add_heading("11.2 After Architecture (Mermaid)", level=2)
after_mermaid = '''\
graph TD
    A["AI Model<br/>(Copilot / Foundry Agent)"] -->|"1. get_schema()"| B["MCP Server<br/>server.py"]
    A -->|"2. execute_query(kql, sid, type)"| B
    B -->|"KQL query"| C["la_client.py"]
    C -->|"Azure SDK"| D["Azure Log Analytics<br/>Workspace"]
    D -->|"Rows"| C
    C -->|"Rows"| B

    B -->|"Store full rows"| CACHE["result_cache.py<br/>In-Memory Cache<br/>(TTL 300s, max 50)"]

    B -->|"If analysis_type set"| REG["analyzers/__init__.py<br/>Plugin Registry"]
    REG -->|"@register lookup"| PLUG["analyzers/*.py<br/>6 Plugin Modules"]
    PLUG -->|"Classified result"| TOON["toon_formatter.py<br/>Compact + query_id"]

    B -->|"If no analysis_type"| GEN["generic_summarizer.py<br/>Stats + 3 Samples"]
    GEN -->|"Summary"| TOON

    TOON -->|"✅ Compact summary<br/>~3 KB + query_id"| B
    B -->|"Summary + query_id"| A

    A -->|"3. get_details(query_id, cat)"| B
    B -->|"Lookup"| CACHE
    CACHE -->|"Filtered slice<br/>(5 rows)"| B
    B -->|"Detail rows"| A

    style A fill:#4472C4,color:#fff
    style B fill:#ED7D31,color:#fff
    style D fill:#70AD47,color:#fff
    style CACHE fill:#9DC3E6,color:#000
    style REG fill:#FFC000,color:#000
    style PLUG fill:#FFE699,color:#000
    style TOON fill:#A9D18E,color:#000
    style GEN fill:#F4B183,color:#000
'''
code_p = doc.add_paragraph()
run = code_p.add_run(after_mermaid)
run.font.name = "Consolas"
run.font.size = Pt(8)

# PIPELINE FLOW diagram
doc.add_heading("11.3 Execute Query Pipeline Flow (Mermaid)", level=2)
pipeline_mermaid = '''\
flowchart LR
    subgraph execute_query
        A[KQL + SID] --> B[la_client<br/>Run Query]
        B --> C{Rows returned?}
        C -->|Yes| D[result_cache<br/>store rows]
        C -->|No| Z[Return no_data]
        D --> E{analysis_type<br/>provided?}
        E -->|Yes| F[analyzer_registry<br/>get_analyzer type]
        F --> G{Analyzer<br/>found?}
        G -->|Yes| H[Run Plugin<br/>Analyzer]
        G -->|No| I[generic_summarizer]
        E -->|No| I
        H --> J[toon_formatter<br/>format_summary_response]
        I --> K[toon_formatter<br/>compact]
        J --> L["Return summary<br/>+ query_id"]
        K --> L
    end

    style A fill:#4472C4,color:#fff
    style D fill:#9DC3E6,color:#000
    style H fill:#FFE699,color:#000
    style I fill:#F4B183,color:#000
    style J fill:#A9D18E,color:#000
    style K fill:#A9D18E,color:#000
    style L fill:#70AD47,color:#fff
'''
code_p = doc.add_paragraph()
run = code_p.add_run(pipeline_mermaid)
run.font.name = "Consolas"
run.font.size = Pt(8)

# ── Save document ────────────────────────────────────────────────────────
output_path = os.path.join(os.path.dirname(__file__), "AMS_MCP_Server_Design_Document.docx")
doc.save(output_path)
print(f"✓ Document saved: {output_path}")

# ── Save Mermaid files ───────────────────────────────────────────────────
diagrams_dir = os.path.join(os.path.dirname(__file__), "diagrams")
os.makedirs(diagrams_dir, exist_ok=True)

for name, content in [
    ("before_architecture.mmd", before_mermaid),
    ("after_architecture.mmd", after_mermaid),
    ("execute_query_pipeline.mmd", pipeline_mermaid),
]:
    path = os.path.join(diagrams_dir, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"✓ Diagram saved: {path}")

print("\nDone! Open the .docx in Word and the .mmd files in mermaid.live or VS Code Mermaid preview.")
