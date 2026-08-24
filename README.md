# SAP RCA MCP Server

Python MCP server that enables AI agents to perform Root Cause Analysis on SAP systems
by querying Azure Log Analytics data.

## Architecture

```
AI Agent (Azure AI Foundry / Claude / Copilot Studio)
    │  MCP Tool Calls
    ▼
FastMCP Server (server.py)
    ├── get_schema        → schema_registry.py  (table/column metadata)
    ├── execute_query     → la_client.py         (validated KQL execution)
    ├── analyze_results   → domain_knowledge.py  (SAP error classification)
    └── run_full_rca      → rca_orchestrator.py  (8-step automated workflow)
    │
    ▼
Azure Log Analytics (read-only KQL queries via Managed Identity)
```

## The 4 Tools

| Tool | Purpose |
|---|---|
| `get_schema` | Returns exact column names, types, time column, SID column, and KQL hints for registered tables. Call this first. |
| `execute_query` | Validates an agent-generated KQL query (read-only guard) then executes it. |
| `analyze_results` | Applies SAP domain knowledge to classify raw rows: error categories, severity, recommendations. |
| `run_full_rca` | Executes all 8 RCA steps automatically and returns a consolidated JSON report. |

## Prerequisites

- Python 3.11+
- Azure CLI (`az`) installed
- Access to the Azure Log Analytics workspace (Workspace ID needed)
- Role `Log Analytics Reader` assigned to your account (or Managed Identity)

## Setup

```bash
# 1. Clone / navigate to this folder
cd C:\Users\padmajat\Documents\AMS-Agentic-RCA\MCP

# 2. Create virtual environment
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # Linux/macOS

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure
copy .env.example .env
# Edit .env and fill in AZURE_LOG_ANALYTICS_WORKSPACE_ID and AZURE_TENANT_ID

# 5. Authenticate (local development)
az login
```

## Configuration (.env)

```
AZURE_LOG_ANALYTICS_WORKSPACE_ID=<your-workspace-guid>
AZURE_TENANT_ID=<your-tenant-id>
```

On Azure with Managed Identity, only the workspace ID is needed — leave all
`AZURE_CLIENT_*` fields blank.

## Running

### stdio mode (Claude Desktop, MCP Inspector, Azure AI Foundry local)

```bash
python server.py
# or:
mcp dev server.py
```

### SSE/HTTP mode (Azure App Service deployment)

```bash
pip install uvicorn
uvicorn server:mcp --host 0.0.0.0 --port 8000
```

The SSE endpoint will be: `http://localhost:8000/sse`

## Connect to Claude Desktop

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "sap-rca": {
      "command": "python",
      "args": ["C:/Users/padmajat/Documents/AMS-Agentic-RCA/MCP/server.py"],
      "env": {
        "AZURE_LOG_ANALYTICS_WORKSPACE_ID": "<your-workspace-id>",
        "AZURE_TENANT_ID": "<your-tenant-id>"
      }
    }
  }
}
```

## Connect to Azure AI Foundry

In Azure AI Foundry, add an MCP connection pointing to:
`https://<your-app-service>.azurewebsites.net/sse`

## Example Agent Conversation

**Focused query workflow:**
```
Agent → get_schema(["SapNetweaver_ShortDumps_CL"])
Agent → execute_query("SapNetweaver_ShortDumps_CL | where serverTimestamp_t > ago(4h) | where SID_s == 'CHA' | take 100")
Agent → analyze_results(results, "short_dumps", context="SID=CHA, last 4h")
```

**Full automated RCA:**
```
Agent → run_full_rca(sid="CHA", time_range_hours=4, issue_description="Multiple batch job failures")
← Returns complete 8-step RCA report
```

## Registered Tables

Currently registered (1 of 7):

| Table | SAP Source | Status |
|---|---|---|
| `SapNetweaver_ShortDumps_CL` | ST22 ABAP Short Dumps | ✅ Registered |
| `SapNetweaver_SysLogs_CL` | SM21 System Log | ⏳ Awaiting schema CSV |
| `SapNetweaver_BatchJobs_CL` | SM37 Batch Jobs | ⏳ Awaiting schema CSV |
| `SapNetweaver_GetSystemInstanceList_CL` | Instance Availability | ⏳ Awaiting schema CSV |
| `SapNetweaver_GetProcessList_CL` | Process Availability | ⏳ Awaiting schema CSV |
| `Prometheus_OSExporter_CL` | OS Metrics | ⏳ Awaiting schema CSV |
| `Prometheus_HaClusterExporter_CL` | HA Cluster | ⏳ Awaiting schema CSV |

## Adding a New Table Schema

1. Provide the schema CSV (columns + description) — same format as `SchemaforMCP-Details.csv`.
2. Add a new entry to `schema_registry.py` following the existing `SapNetweaver_ShortDumps_CL` entry as a template.
3. If the table needs domain-specific analysis logic, add a `_analyze_<type>()` function to `tools/analyze_results.py`.
4. Add a KQL template to `_KQL_TEMPLATES` in `tools/rca_orchestrator.py`.
5. Restart the server — no other changes needed.

## Security Notes

- `execute_query` blocks all KQL management commands (`.ingest`, `.drop`, `.set`, etc.)
- `run_full_rca` uses parameterised KQL templates — SID values are validated before substitution
- All credentials are loaded from environment variables — no secrets in code
- On Azure, use Managed Identity; do not store `AZURE_CLIENT_SECRET` in App Service config

---

## ⚠ Outstanding Questions (Action Required)

Before the server can connect to your workspace, you need to provide:

| # | What | Where to find it | File to update |
|---|---|---|---|
| 1 | **Log Analytics Workspace ID** | Azure Portal → Log Analytics workspace → Overview → Workspace ID | `.env` |
| 2 | **Azure Tenant ID** | Azure Portal → Microsoft Entra ID → Overview → Tenant ID | `.env` |
| 3 | **Time column for `SapNetweaver_ShortDumps_CL`** | The CSV you provided shows `serverTimestamp_t`. Agent docs show `timestamp_t`. Please confirm which column name is correct in your workspace (check Log Analytics → Tables → ShortDumps). | `schema_registry.py` line with `"time_column"` |
| 4 | **SID_s column presence** | Is `SID_s` present in your ShortDumps table? (Some workspaces use `sapsid_s` instead.) | `schema_registry.py` `"sid_column"` field |
| 5 | **Remaining 6 table schemas** | Provide schema CSVs (same format as `SchemaforMCP-Details.csv`) for the remaining tables to enable the full 8-step RCA | `schema_registry.py` entries |
