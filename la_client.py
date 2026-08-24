"""Azure Log Analytics query client wrapper.

Authentication priority (first available wins):
  1. AZURE_BEARER_TOKEN in .env — short-lived user token (az account get-access-token)
  2. DefaultAzureCredential   — az login, Managed Identity, service principal

workspace_id can be:
  - ARM resource ID: /subscriptions/.../workspaces/<name>
  - Workspace GUID:  xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
Both are accepted by the Azure Monitor Query SDK.
Pass a different workspace_id to execute_kql() to query a different workspace
without changing environment variables.
"""
from __future__ import annotations

import os
from datetime import timedelta
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from azure.core.credentials import AccessToken, TokenCredential
from azure.identity import DefaultAzureCredential
from azure.monitor.query import LogsQueryClient, LogsQueryStatus

import config


class _StaticTokenCredential(TokenCredential):
    """Wraps a pre-obtained bearer token so it can be used as an Azure credential.

    The token is treated as non-expiring from the SDK's perspective — it will
    fail naturally when the token expires (~1 hour) and the user must refresh it.
    """

    def __init__(self, token: str) -> None:
        self._token = token

    def get_token(self, *scopes, **kwargs) -> AccessToken:  # noqa: ANN002
        # expires_on = far future (SDK won't auto-refresh; fail gracefully on expiry)
        return AccessToken(self._token, 9999999999)


_client: LogsQueryClient | None = None


def _get_client() -> LogsQueryClient:
    global _client
    if _client is None:
        if config.BEARER_TOKEN:
            credential = _StaticTokenCredential(config.BEARER_TOKEN)
        else:
            credential = DefaultAzureCredential()
        _client = LogsQueryClient(credential)
    return _client


def reset_client() -> None:
    """Force re-creation of the LogsQueryClient on next call.

    Call this after updating AZURE_BEARER_TOKEN in .env so the new token is
    picked up without restarting the server process.
    """
    global _client
    _client = None
    # Re-read .env with override=True so the refreshed token replaces the stale one
    load_dotenv(dotenv_path=Path(__file__).parent / ".env", override=True)
    config.BEARER_TOKEN = os.environ.get("AZURE_BEARER_TOKEN", "")


def execute_kql(
    kql: str,
    timespan: "int | tuple" = 24,
    workspace_id: str | None = None,
    sid: str | None = None,
) -> dict[str, Any]:
    """Execute a KQL query and return structured results.

    Args:
        kql:       KQL query string (read-only).
        timespan:  Either an int (hours, relative from now) or a
                   (datetime, datetime) tuple for an absolute time range.
                   Defaults to 24 hours.
        workspace_id:  Optional override — ARM resource ID or workspace GUID.
                       When omitted, uses AZURE_LOG_ANALYTICS_WORKSPACE_ID from .env.
                       Pass a value here to query a different workspace at call time.
        sid:       Optional SAP System ID. Used to auto-resolve the workspace
                   via SID_WORKSPACE_MAP when workspace_id is not provided.

    Returns dict with keys:
      status     : "success" | "partial" | "error"
      rows       : list[dict]  — rows from the first result table
      row_count  : int
      tables     : list of all result tables (for multi-table queries)
      error      : str  — only present when status is "error"
    """
    try:
        effective_workspace = config.resolve_workspace(workspace_id, sid=sid)
    except ValueError as exc:
        return {"status": "error", "error": str(exc), "rows": [], "row_count": 0, "tables": []}

    try:
        response = _get_client().query_workspace(
            workspace_id=effective_workspace,
            query=kql,
            timespan=timedelta(hours=int(timespan)) if isinstance(timespan, int) else timespan,
            server_timeout=config.QUERY_TIMEOUT_SECONDS,
        )

        if response.status not in (LogsQueryStatus.SUCCESS, LogsQueryStatus.PARTIAL):
            error_detail = getattr(response, "partial_error", None)
            return {
                "status": "error",
                "error": str(error_detail) if error_detail else "Query returned an unknown failure status.",
                "rows": [],
                "row_count": 0,
                "tables": [],
            }

        status = "success" if response.status == LogsQueryStatus.SUCCESS else "partial"

        all_tables: list[dict] = []
        for table in response.tables:
            col_names = list(table.columns)
            rows = [dict(zip(col_names, row)) for row in table.rows]
            all_tables.append({"name": table.name, "columns": col_names, "rows": rows, "row_count": len(rows)})

        primary_rows = all_tables[0]["rows"] if all_tables else []
        return {
            "status": status,
            "rows": primary_rows,
            "row_count": len(primary_rows),
            "tables": all_tables,
        }

    except Exception as exc:  # noqa: BLE001
        err_str = str(exc)
        # Give an actionable message for the common bearer-token-expired case
        if config.BEARER_TOKEN and any(k in err_str.lower() for k in ("401", "unauthorized", "token", "expired", "invalid_token")):
            err_str = (
                "Bearer token has expired (tokens last ~1 hour). "
                "Run: .\\MCP\\refresh-token.ps1  — or manually run: "
                "az account get-access-token --resource https://api.loganalytics.io --query accessToken -o tsv "
                "and paste the result into AZURE_BEARER_TOKEN in MCP/.env. "
                f"Original error: {exc}"
            )
        return {"status": "error", "error": err_str, "rows": [], "row_count": 0, "tables": []}
