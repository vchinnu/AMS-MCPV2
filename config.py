"""Configuration — loads environment variables from .env or the process environment.

The workspace ID can be either:
  - An ARM resource ID:  /subscriptions/<sub>/resourcegroups/<rg>/providers/...
  - A workspace GUID:    xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
Both formats are accepted by the Azure Monitor Query SDK.

To switch to a different Log Analytics workspace, update AZURE_LOG_ANALYTICS_WORKSPACE_ID
in .env. Alternatively, pass workspace_id directly to execute_query() or run_full_rca().
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from the same directory as this file, regardless of CWD
load_dotenv(dotenv_path=Path(__file__).parent / ".env")

# Primary workspace — read from environment. Can be overridden per-call in any tool.
WORKSPACE_ID: str = os.environ.get("AZURE_LOG_ANALYTICS_WORKSPACE_ID", "")
TENANT_ID: str = os.environ.get("AZURE_TENANT_ID", "")
CLIENT_ID: str = os.environ.get("AZURE_CLIENT_ID", "")
CLIENT_SECRET: str = os.environ.get("AZURE_CLIENT_SECRET", "")
BEARER_TOKEN: str = os.environ.get("AZURE_BEARER_TOKEN", "")  # Short-lived token fallback (expires ~1h)
DEFAULT_SID: str = os.environ.get("DEFAULT_SID", "")
MAX_QUERY_ROWS: int = int(os.environ.get("MAX_QUERY_ROWS", "1000"))
QUERY_TIMEOUT_SECONDS: int = int(os.environ.get("QUERY_TIMEOUT_SECONDS", "60"))
DEFAULT_TIMESPAN_HOURS: int = int(os.environ.get("DEFAULT_TIMESPAN_HOURS", "24"))

# SID-to-workspace mapping: SID1:workspace-guid-1,SID2:workspace-guid-2
_sid_map_raw: str = os.environ.get("SID_WORKSPACE_MAP", "")
SID_WORKSPACE_MAP: dict[str, str] = {}
if _sid_map_raw.strip():
    for entry in _sid_map_raw.split(","):
        entry = entry.strip()
        if ":" in entry:
            sid_key, ws_value = entry.split(":", 1)
            SID_WORKSPACE_MAP[sid_key.strip().upper()] = ws_value.strip()


def validate() -> None:
    """Raise ValueError if required configuration is missing."""
    if not WORKSPACE_ID:
        raise ValueError(
            "AZURE_LOG_ANALYTICS_WORKSPACE_ID is not set. "
            "Fill in the value in .env (ARM resource ID or workspace GUID)."
        )


def resolve_workspace(override: str | None = None, sid: str | None = None) -> str:
    """Return the effective workspace ID for a query.

    Resolution order:
        1. Explicit *override* (non-empty) — highest priority.
        2. SID_WORKSPACE_MAP lookup (if *sid* is provided and has a mapping).
        3. AZURE_LOG_ANALYTICS_WORKSPACE_ID from .env — default fallback.
    """
    if override and override.strip():
        return override.strip()

    if sid and sid.strip().upper() in SID_WORKSPACE_MAP:
        return SID_WORKSPACE_MAP[sid.strip().upper()]

    ws = WORKSPACE_ID.strip()
    if not ws:
        raise ValueError(
            "No Log Analytics workspace ID provided. "
            "Set AZURE_LOG_ANALYTICS_WORKSPACE_ID in .env, add a SID_WORKSPACE_MAP entry, "
            "or pass workspace_id to the tool call."
        )
    return ws
