# SAP RCA MCP Server — Build Plan

> **Status:** Awaiting confirmation to proceed with implementation.  
> Review this plan, then confirm and the full code will be generated.

---

## 1. What We Are Building

A **Python-based MCP (Model Context Protocol) server** that exposes SAP observability tools so that any MCP-compatible AI agent (Azure AI Foundry, Claude, Copilot Studio, etc.) can:

- Query 7 Azure Log Analytics tables covering SAP NetWeaver, OS, and HA cluster data.
- Run structured RCA workflows across all data sources automatically.
- Classify root causes using embedded SAP domain knowledge (runtime error categories, SM21 message IDs, job status codes).

---

## 2. Architecture

```
AI Agent (Azure AI Foundry / Claude / Copilot)
        │  MCP Tool Calls (JSON-RPC 2.0)
        ▼
┌─────────────────────────────────────────────┐
│         SAP RCA MCP Server (Python)          │
│  ┌─────────────────────────────────────────┐ │
│  │  FastMCP  (stdio / SSE transport)        │ │
│  └─────────────────────────────────────────┘ │
│  ┌──────────────┐  ┌──────────────────────┐  │
│  │ Schema       │  │  Domain Knowledge    │  │
│  │ Registry     │  │  (RCA Classification)│  │
│  └──────────────┘  └──────────────────────┘  │
│  ┌─────────────────────────────────────────┐  │
│  │     Azure Log Analytics Client          │  │
│  │  (DefaultAzureCredential / Managed ID)  │  │
│  └─────────────────────────────────────────┘  │
└─────────────────────────────────────────────┘
        │  KQL Queries (read-only)
        ▼
┌──────────────────────────────────────────────┐
│           Azure Log Analytics Workspace       │
│  ┌────────────────────────────────────────┐  │
│  │ SapNetweaver_SysLogs_CL       (SM21)   │  │
│  │ SapNetweaver_ShortDumps_CL    (ST22)   │  │
│  │ SapNetweaver_BatchJobs_CL     (SM37)   │  │
│  │ SapNetweaver_GetSystemInstanceList_CL  │  │
│  │ SapNetweaver_GetProcessList_CL         │  │
│  │ Prometheus_OSExporter_CL               │  │
│  │ Prometheus_HaClusterExporter_CL        │  │
│  └────────────────────────────────────────┘  │
└──────────────────────────────────────────────┘
```

---

## 3. File Structure

```
MCP/
├── server.py                    # Entry point — FastMCP server, registers all tools
├── config.py                    # Env var configuration (workspace ID, tenant, etc.)
├── la_client.py                 # Azure Log Analytics query client wrapper
├── schema_registry.py           # Table schemas, time columns, SID column mappings
├── domain_knowledge.py          # SAP runtime error categories, SM21 msg IDs
├── tools/
│   ├── __init__.py
│   ├── system_logs.py           # Tool: query_system_logs  (SM21)
│   ├── short_dumps.py           # Tool: query_short_dumps  (ST22)
│   ├── batch_jobs.py            # Tool: query_batch_jobs   (SM37)
│   ├── os_metrics.py            # Tool: query_os_metrics
│   ├── ha_cluster.py            # Tool: query_ha_cluster
│   ├── availability.py          # Tool: query_system_availability
│   └── rca_orchestrator.py      # Tool: run_full_rca (8-step workflow)
├── requirements.txt
├── .env.example
├── PLAN.md                      # This document
└── README.md                    # Setup, run, and deployment guide
```

---

## 4. MCP Tools — Full Definition

### Tool 1: `query_system_logs`
**Table:** `SapNetweaver_SysLogs_CL` (SM21)  
**Purpose:** Retrieve SAP system log entries filtered by SID, time, and severity.

| Input Parameter    | Type    | Default | Description                                    |
|--------------------|---------|---------|------------------------------------------------|
| `sid`              | string  | —       | SAP System ID (e.g., `CHA`, `PRD`)             |
| `time_range_hours` | int     | 4       | Lookback window in hours                       |
| `severity`         | string  | "1,2"   | Comma-separated: `1`=Very High, `2`=High       |
| `problem_class`    | string  | ""      | Filter: `Security`, `Performance`, `Database`  |
| `limit`            | int     | 200     | Max rows to return                             |

**Output:** JSON list of log entries with timestamp, severity, message, user, program, component.  
**KQL time column:** `TimeGenerated`

---

### Tool 2: `query_short_dumps`
**Table:** `SapNetweaver_ShortDumps_CL` (ST22)  
**Purpose:** Retrieve ABAP short dump (runtime error) records.

| Input Parameter    | Type    | Default | Description                                    |
|--------------------|---------|---------|------------------------------------------------|
| `sid`              | string  | —       | SAP System ID                                  |
| `time_range_hours` | int     | 4       | Lookback window in hours                       |
| `runtime_error`    | string  | ""      | Filter by runtime error code (e.g., `TIME_OUT`)|
| `user`             | string  | ""      | Filter by SAP user (`E2E_USER_s`)              |
| `limit`            | int     | 100     | Max rows to return                             |

**Output:** JSON list of dumps with timestamp, runtime error, error category (classified from domain knowledge), program, user, host.  
**KQL time column:** `timestamp_t`

---

### Tool 3: `query_batch_jobs`
**Table:** `SapNetweaver_BatchJobs_CL` (SM37)  
**Purpose:** Retrieve batch job execution records, focusing on failures.

| Input Parameter    | Type    | Default | Description                                       |
|--------------------|---------|---------|---------------------------------------------------|
| `sid`              | string  | —       | SAP System ID                                     |
| `time_range_hours` | int     | 4       | Lookback window in hours                          |
| `status`           | string  | "A"     | Job status: `F`=Finished, `A`=Cancelled, `Z`=Active, `S`=Released, `all`=all |
| `job_name`         | string  | ""      | Filter by job name (partial match supported)       |
| `user`             | string  | ""      | Filter by scheduling/releasing user               |
| `limit`            | int     | 100     | Max rows to return                                |

**Output:** JSON list of jobs with name, status (decoded), start/end times, server, job class.  
**KQL time column:** `serverTimestamp_t`

---

### Tool 4: `query_os_metrics`
**Table:** `Prometheus_OSExporter_CL`  
**Purpose:** Query OS-level metrics (CPU, memory, disk) for SAP hosts.

| Input Parameter       | Type    | Default | Description                                          |
|-----------------------|---------|---------|------------------------------------------------------|
| `sid`                 | string  | —       | SAP System ID (`sapsid_s`)                           |
| `time_range_hours`    | int     | 4       | Lookback window in hours                             |
| `host`                | string  | "All"   | Specific hostname or `All`                           |
| `metric_type`         | string  | "all"   | `memory`, `disk`, `cpu`, or `all`                   |
| `threshold_percent`   | float   | 80.0    | Alert threshold — only return metrics above this     |
| `limit`               | int     | 500     | Max rows to return                                   |

**Output:** JSON list of metric readings with host, metric name, average/max/min value, and alert classification.  
**KQL time column:** `time_generated_t`

---

### Tool 5: `query_ha_cluster`
**Table:** `Prometheus_HaClusterExporter_CL`  
**Purpose:** Check HA Pacemaker cluster health signals (quorum, STONITH, node status).

| Input Parameter    | Type    | Default | Description                                 |
|--------------------|---------|---------|---------------------------------------------|
| `sid`              | string  | —       | SAP System ID (`sapsid_s`)                  |
| `time_range_hours` | int     | 4       | Lookback window in hours                    |
| `signal_type`      | string  | "all"   | `quorum`, `stonith`, `scrape`, or `all`     |
| `limit`            | int     | 200     | Max rows to return                          |

**Output:** JSON list of HA signals with timestamp, signal type, description, critical flag.  
**KQL time column:** `time_generated_t`

---

### Tool 6: `query_system_availability`
**Tables:** `SapNetweaver_GetSystemInstanceList_CL` + `SapNetweaver_GetProcessList_CL`  
**Purpose:** Check SAP instance and process availability/health status.

| Input Parameter    | Type    | Default | Description                                 |
|--------------------|---------|---------|---------------------------------------------|
| `sid`              | string  | —       | SAP System ID                               |
| `time_range_hours` | int     | 4       | Lookback window in hours                    |
| `limit`            | int     | 100     | Max rows to return                          |

**Output:** JSON summary of SAP instances and processes with status, host, instance numbers.

---

### Tool 7: `execute_kql_query`
**Tables:** Any (flexible)  
**Purpose:** Execute a KQL query directly against the workspace (read-only, validated).

| Input Parameter    | Type    | Description                                             |
|--------------------|---------|--------------------------------------------------------------|
| `kql_query`        | string  | KQL query string (must be read-only; write ops rejected)     |
| `timespan_hours`   | int     | Optional override for query timespan cap (default 24h)       |

**Output:** JSON query results with column names and rows.  
**Security:** Validates query for no write operations before executing.

---

### Tool 8: `run_full_rca`
**Tables:** All 7 tables  
**Purpose:** Execute the complete 8-step RCA workflow automatically for a given SAP alert or issue.

| Input Parameter      | Type    | Default | Description                                          |
|----------------------|---------|---------|------------------------------------------------------|
| `sid`                | string  | —       | SAP System ID                                        |
| `time_range_hours`   | int     | 4       | Investigation time window in hours                   |
| `issue_description`  | string  | ""      | Optional: incident description or alert text         |
| `focus_area`         | string  | "all"   | `availability`, `dumps`, `jobs`, `os`, `ha`, or `all`|

**RCA Steps Executed:**
1. **System Availability** — Check instance/process up/down status
2. **HA Cluster Health** — Check Pacemaker quorum, STONITH, node status
3. **OS Metrics** — Check CPU, memory, disk thresholds
4. **SM21 System Logs** — Severity 1 & 2 log entries (errors, aborts)
5. **ST22 ABAP Dumps** — Runtime errors, classified by category
6. **SM37 Batch Jobs** — Cancelled jobs, job failure patterns
7. **Cross-Correlation** — Match dump timestamps with system log entries, job failures with OS spikes
8. **RCA Summary** — Consolidated findings with likely root cause and recommended actions

**Output:** Structured JSON RCA report with:
- `summary`: High-level root cause statement
- `severity`: `Critical` / `High` / `Medium` / `Low`
- `findings`: Per-step findings with evidence
- `correlations`: Cross-table correlations found
- `recommendations`: Actionable next steps
- `evidence_queries`: KQL queries that produced the findings

---

## 5. Authentication Strategy

```
Local Development:           Azure Deployment:
  az login                    Managed Identity (no secrets)
  DefaultAzureCredential  →   DefaultAzureCredential (auto-picks)
  ↓                           ↓
  azure-identity SDK          azure-identity SDK
  ↓                           ↓
  Log Analytics Query API     Log Analytics Query API
```

**Required permissions on Log Analytics Workspace:**
- Role: `Log Analytics Reader`
- Assigned to: Developer UPN (local) or Managed Identity object ID (Azure)

---

## 6. Dependencies

```
mcp[cli]>=1.0.0              # MCP Python SDK (FastMCP)
azure-monitor-query>=1.2.0   # Azure Log Analytics query client
azure-identity>=1.15.0       # DefaultAzureCredential
python-dotenv>=1.0.0         # .env file loading
pydantic>=2.0.0              # Input validation for tools
```

---

## 7. Configuration (Environment Variables)

| Variable                      | Required | Description                                       |
|-------------------------------|----------|---------------------------------------------------|
| `AZURE_LOG_ANALYTICS_WORKSPACE_ID` | Yes | Log Analytics workspace GUID                  |
| `AZURE_TENANT_ID`             | Dev only | Entra tenant ID (for az login auth)               |
| `AZURE_CLIENT_ID`             | Dev/Prod | Service principal or managed identity client ID   |
| `AZURE_CLIENT_SECRET`         | Dev only | Service principal secret (use Key Vault in prod)  |
| `DEFAULT_SID`                 | No       | Default SAP SID when not provided in tool call    |
| `MAX_QUERY_ROWS`              | No       | Global row limit cap (default: 1000)              |
| `QUERY_TIMEOUT_SECONDS`       | No       | Log Analytics query timeout (default: 60)         |

---

## 8. Transport Modes

### Mode A: stdio (for local agents, Claude Desktop, MCP Inspector)
```bash
python server.py
# or
mcp dev server.py
```

### Mode B: SSE over HTTP (for Azure App Service hosting)
```python
# server.py automatically detects PORT env var
# Run on Azure App Service → exposes: https://<app>.azurewebsites.net/sse
uvicorn server:app --host 0.0.0.0 --port 8000
```

---

## 9. Step-by-Step Build Plan

### Step 1 — Scaffold (config + client)
- `config.py`: Load all env vars with validation
- `la_client.py`: Wrap `LogsQueryClient` with retry, timeout, and read-only enforcement
- `schema_registry.py`: Embed all 7 table schemas (columns, time column, SID column)

### Step 2 — Domain Knowledge Module
- `domain_knowledge.py`: Runtime error → category mapping, SM21 message ID descriptions, job status code labels

### Step 3 — Individual Query Tools
- `tools/system_logs.py` → `query_system_logs`
- `tools/short_dumps.py` → `query_short_dumps`
- `tools/batch_jobs.py` → `query_batch_jobs`
- `tools/os_metrics.py` → `query_os_metrics`
- `tools/ha_cluster.py` → `query_ha_cluster`
- `tools/availability.py` → `query_system_availability`

### Step 4 — Flexible KQL Tool
- `tools/kql_runner.py` → `execute_kql_query` (with write-op guard)

### Step 5 — RCA Orchestrator
- `tools/rca_orchestrator.py` → `run_full_rca` (8-step, correlation engine, structured report)

### Step 6 — Main Server
- `server.py`: Register all tools in FastMCP, configure transport

### Step 7 — Supporting Files
- `requirements.txt`, `.env.example`, `README.md`

---

## 10. How the Agent Uses These Tools

**Example flow — "Investigate alert for SID CHA":**

```
Agent: run_full_rca(sid="CHA", time_range_hours=4, issue_description="Multiple job failures")

MCP Server:
  Step 1: query_system_availability(sid="CHA", time_range_hours=4)
  Step 2: query_ha_cluster(sid="CHA", time_range_hours=4)
  Step 3: query_os_metrics(sid="CHA", time_range_hours=4)
  Step 4: query_system_logs(sid="CHA", time_range_hours=4, severity="1,2")
  Step 5: query_short_dumps(sid="CHA", time_range_hours=4)
  Step 6: query_batch_jobs(sid="CHA", time_range_hours=4, status="A")  ← cancelled jobs
  Step 7: Correlate findings across steps
  Step 8: Build RCA report

Agent: Returns structured JSON RCA report to user
```

Agent can also call individual tools for focused investigation:
```
query_system_logs(sid="CHA", severity="1", problem_class="Database")
query_short_dumps(sid="CHA", runtime_error="TIME_OUT")
query_batch_jobs(sid="CHA", status="A", user="BATCH_USER")
```

---

## 11. Deployment Options (from Design Doc)

| Option                    | Recommendation | Notes                                         |
|---------------------------|---------------|-----------------------------------------------|
| Azure App Service (Python)| ✅ Recommended | Easy SSE deployment, Managed Identity support  |
| Azure Container Apps      | ✅ Good        | More control, scale-to-zero                   |
| Docker locally            | ✅ Dev/Test    | Simple local testing                          |
| stdio (Claude Desktop)    | ✅ Local       | Direct integration with Claude                |

---

## 12. Security Controls

- **No secrets in code** — all credentials via env vars or Managed Identity
- **Read-only enforcement** — `execute_kql_query` validates no write operations
- **Input validation** — Pydantic models validate all tool inputs
- **Row limits** — All queries capped at configurable max rows
- **Query timeout** — Log Analytics client enforced timeout
- **SID injection prevention** — SID values are parameterized, not string-concatenated into KQL

---

## Ready to Build?

Once you confirm, the following files will be created in `C:\Users\padmajat\Documents\AMS-Agentic-RCA\MCP\`:

| File                          | Lines (est.) | Purpose                               |
|-------------------------------|-------------|---------------------------------------|
| `server.py`                   | ~80          | FastMCP entry point, tool registration |
| `config.py`                   | ~50          | Configuration management              |
| `la_client.py`                | ~100         | Log Analytics client wrapper          |
| `schema_registry.py`          | ~150         | Table schemas for all 7 tables        |
| `domain_knowledge.py`         | ~120         | SAP error classification data         |
| `tools/__init__.py`           | ~5           | Package init                          |
| `tools/system_logs.py`        | ~80          | SM21 query tool                       |
| `tools/short_dumps.py`        | ~90          | ST22 query tool                       |
| `tools/batch_jobs.py`         | ~90          | SM37 query tool                       |
| `tools/os_metrics.py`         | ~80          | OS metrics query tool                 |
| `tools/ha_cluster.py`         | ~70          | HA cluster query tool                 |
| `tools/availability.py`       | ~70          | System availability tool              |
| `tools/kql_runner.py`         | ~60          | Flexible KQL execution tool           |
| `tools/rca_orchestrator.py`   | ~200         | Full 8-step RCA workflow tool         |
| `requirements.txt`            | ~10          | Python dependencies                   |
| `.env.example`                | ~20          | Environment variable template         |
| `README.md`                   | ~150         | Setup and deployment guide            |

**Total: ~1,425 lines of production-ready Python code**
