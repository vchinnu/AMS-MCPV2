# AMS Agentic RCA — MCP Server Work Summary

## Overview

This document summarizes all work done on the SAP RCA MCP (Model Context Protocol) server — including tool design, code changes, deployment, and Foundry agent integration.

---

## Architecture

```
Azure AI Foundry Agent
        │
        │ MCP protocol (SSE)
        ▼
Azure Container App: sap-rca-mcp
  https://sap-rca-mcp.yellowhill-4ff05bed.eastus.azurecontainerapps.io/mcp
        │
        │ KQL queries
        ▼
Azure Log Analytics Workspace
  (AMS / SAP telemetry tables)
```

---

## MCP Tools

The server exposes 4 tools to the Foundry agent:

| Tool | Purpose |
|---|---|
| `get_schema` | Returns schema for all 7 LAW tables (columns, types, descriptions) |
| `execute_query` | Runs a KQL query; auto-classifies result if `analysis_type` is set |
| `deeper_rca_analysis` | Classifies pre-fetched query results into RCA categories |
| `run_full_rca` | Executes all 8 RCA steps and returns a structured report |

### Auto-classification in `execute_query`

When `execute_query` is called with `analysis_type` (e.g. `"short_dumps"`), the server internally runs `deeper_rca_analysis` and returns the classified result. A `_pipeline` field is included in the response so the agent can confirm it ran:

```json
"_pipeline": "execute_query → deeper_rca_analysis (auto-classified as 'short_dumps')"
```

Currently supported `analysis_type` values: `short_dumps`, `batch_job_failures`, `rfc_errors`, `idoc_errors`, `abap_dumps`, `update_failures`, `spool_issues`, `lock_conflicts`, `job_cancellations`, `transaction_errors`.

---

## Key Files

```
MCP/
├── server.py                   # FastMCP server — registers all 4 tools; sets server instructions
├── config.py                   # Env-driven config (workspace ID, tenant, DEFAULT_TIMESPAN_HOURS, etc.)
├── domain_knowledge.py         # SAP domain data: MSG_GROUP_PREFIXES, RUNTIME_ERROR_CATEGORIES,
│                               #   JOB_STATUS_LABELS, SM21_MSG_GROUPS, classify_runtime_error,
│                               #   decode_job_status
├── schema_registry.py          # CLASSIFIED_ANALYSIS_TYPES frozenset (single source of truth);
│                               #   get_schema() aggregates all schemas; HOW TO ADD A NEW DOMAIN guide
├── schemas/
│   ├── __init__.py             # Imports all schema modules
│   ├── sap_application.py      # 7 SAP NetWeaver tables:
│   │                           #   SapNetweaver_ShortDumps_CL        (short_dumps)
│   │                           #   SapNetweaver_BatchJobs_CL         (batch_jobs)
│   │                           #   SapNetweaver_SysLogs_CL           (system_logs)
│   │                           #   SapNetweaver_GetSystemInstanceList_CL (raw)
│   │                           #   SapNetweaver_GetProcessList_CL    (raw)
│   │                           #   SapNetweaver_ABAPGetWPTable_CL    (raw)
│   │                           #   SapNetweaver_FailedUpdates_CL     (raw)
│   ├── ha_cluster.py           # HA Pacemaker cluster tables (Prometheus_HaClusterExporter_CL)
│   ├── os_infrastructure.py    # OS metrics tables (Prometheus_OSExporter_CL)
│   └── hana_db.py              # HANA DB tables (placeholder, not yet populated)
├── tools/
│   ├── execute_query.py        # KQL executor + auto-classify gate + _pipeline field
│   ├── deeper_rca_analysis.py  # Classification engine:
│   │                           #   _analyze_short_dumps, _analyze_batch_jobs, _analyze_system_logs
│   ├── rca_orchestrator.py     # run_full_rca — calls deeper_rca_analysis across all tables
│   └── analyze_results.py      # Legacy reference copy — not imported anywhere
├── register-mcp-agent.py       # Local script: creates/updates Foundry agent via AI Projects SDK
├── foundry_mcp_client.py       # Local script: Foundry MCP client for testing
├── refresh-token.ps1           # Refreshes AZURE_BEARER_TOKEN in .env for LAW queries
├── Dockerfile                  # Container image definition (python:3.11-slim, 14 steps)
├── deploy-to-aca.ps1           # Build via ACR Tasks + push + az containerapp update
└── requirements.txt            # Python dependencies
```

---

## Code Changes Made

### `MCP/tools/execute_query.py` — `_pipeline` field
Added visibility indicator when `deeper_rca_analysis` runs internally via auto-classify:

```python
if analysis_type and analysis_type in CLASSIFIED_ANALYSIS_TYPES:
    classified = _classify(result, analysis_type, context)
    classified["_pipeline"] = f"execute_query → deeper_rca_analysis (auto-classified as '{analysis_type}')"
    return classified
```

### `MCP/register-mcp-agent.py` — Fixed tool name
`analyze_results` → `deeper_rca_analysis` in both `SYSTEM_INSTRUCTIONS` and `allowed_tools` list.

### `MCP/foundry_mcp_client.py` — Fixed tool name
`analyze_results` → `deeper_rca_analysis` in `SYSTEM_INSTRUCTIONS`.

---

## Deployment

### Container Registry
- **ACR**: `padmamsrcacr.azurecr.io`
- **Image**: `sap-rca-mcp-server:latest`
- **Last build digest**: `sha256:dd0bf41448c2b934e4a3285ab853c9990d4110f998ac374519e77941f44285df`

### Container App
- **Name**: `sap-rca-mcp`
- **Resource Group**: `PADM-AMS-RCA`
- **Active revision**: `sap-rca-mcp--0000008` (deployed April 14, 2026)
- **Public URL**: `https://sap-rca-mcp.yellowhill-4ff05bed.eastus.azurecontainerapps.io`
- **MCP endpoint**: `https://sap-rca-mcp.yellowhill-4ff05bed.eastus.azurecontainerapps.io/mcp`

### Deploy command
```powershell
.\MCP\deploy-to-aca.ps1
```

### Force new revision (if same `latest` tag doesn't trigger revision)
```powershell
az containerapp update `
  --name sap-rca-mcp `
  --resource-group PADM-AMS-RCA `
  --image padmamsrcacr.azurecr.io/sap-rca-mcp-server@sha256:<digest>
```

### Verify revision health
```powershell
az containerapp revision list --name sap-rca-mcp --resource-group PADM-AMS-RCA -o table
az containerapp logs show --name sap-rca-mcp --resource-group PADM-AMS-RCA --revision sap-rca-mcp--0000008 --tail 30
```

---

## Foundry Agent

| Property | Value |
|---|---|
| Name | `AMS-MCP-RCAAgent` |
| Version | v9 |
| Model | `gpt-4.1` |
| Endpoint | `https://padmaja-ams-rca-resource.services.ai.azure.com/api/projects/padmaja-ams-rca` |
| MCP connection | Points to Container App `/mcp` endpoint |

### Refreshing MCP connection in Foundry
When tools change, delete the old MCP connection in Foundry and re-add it:
1. Foundry portal → Agent → Tools → MCP → delete old connection
2. Re-add with same URL (`https://sap-rca-mcp.yellowhill-4ff05bed.eastus.azurecontainerapps.io/mcp`)

### Agent Instructions (v9)
Full instructions are maintained in [MCP/Foundry_Agent_Instructions.txt](Foundry_Agent_Instructions.txt).

Summary of what the instructions cover:
- **STEP 1** — Call `get_schema` once at the start
- **STEP 2** — Extract SID, time range, symptom clues from user message
- **STEP 3** — Analyse with hard limit of 10 `execute_query` calls; parallel calls allowed; stop when conclusive
- **STEP 4** — Mandatory summary: Overview, Findings (on explicit user request only), Root Cause Analysis, Recommended Fix, Data Limitations
- **Absolute constraints** — read-only KQL, always filter `SID_s`, never answer from memory

---

## Log Analytics Tables (via `get_schema`)

| Table | Key Content |
|---|---|
| `SAPSystemLog_CL` | ABAP system log — short dumps, errors, security events |
| `SAPWorkProcesses_CL` | Work process states — dialog, background, spool, enqueue |
| `SAPSystemInstanceList_CL` | All SAP instances and their status |
| `SAPProcessList_CL` | OS-level SAP process list |
| `SAPABAPGetWPTable_CL` | ABAP work process detail table |
| `SAPFailedUpdates_CL` | Failed V1/V2 update records |
| `SAPHAProvider_CL` | High availability cluster events and failovers |

---

## Issues Resolved

| Issue | Root Cause | Fix |
|---|---|---|
| No visibility that `deeper_rca_analysis` ran | Auto-classify was silent | Added `_pipeline` field to classified results |
| Foundry showed old tools after redeploy | Same `latest` tag → no new revision | Force revision with image digest |
| Portal showed container error on new revision | False alarm from portal caching | Confirmed via logs — server was healthy |
| Foundry still showed `analyze_results` tool | Old revision `--0000007` cached | Forced revision `--0000008` in place |
| `analyze_results` in `register-mcp-agent.py` | Stale copy | Updated to `deeper_rca_analysis` |
| `analyze_results` in `foundry_mcp_client.py` | Stale copy | Updated to `deeper_rca_analysis` |
| "Connection name must be unique" in Foundry | Re-add without deleting old | Delete old connection first, then re-add |

---

## End-to-End Flow (as tested)

1. User sends SAP incident description to Foundry agent
2. Agent calls `get_schema` → sees 7 tables
3. Agent calls `execute_query` with KQL + `analysis_type="short_dumps"`
4. MCP server internally runs `deeper_rca_analysis`, returns classified result with `_pipeline` field
5. Agent presents structured RCA summary: categories, investigation hints, recommended fixes

---

## Token Refresh

If queries return auth errors:
```powershell
.\MCP\refresh-token.ps1
```

---

## Future Work

- Add `_analyze_<type>()` handlers in `deeper_rca_analysis.py` for 4 raw tables:
  - `GetSystemInstanceList`, `GetProcessList`, `ABAPGetWPTable`, `FailedUpdates`
- Set corresponding `analysis_type` in `schema_registry.py`
- Add new types to `CLASSIFIED_ANALYSIS_TYPES` in `execute_query.py`
