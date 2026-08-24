"""Production entrypoint for the SAP RCA MCP server on Azure Container Apps.

FastMCP 1.x (>=1.0) HTTP transport is 'streamable-http' (POST+GET endpoints).
This replaces the old 'sse' transport name from earlier SDK versions.
"""
import logging
import os
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("run_server")

try:
    log.info("Importing server...")
    from server import mcp
    log.info("Server imported OK. Tools registered: %s", [t.name for t in mcp._tool_manager.list_tools()])
except Exception as e:
    log.exception("Failed to import server: %s", e)
    sys.exit(1)

try:
    log.info("Starting FastMCP with streamable-http transport on 0.0.0.0:8000")
    import uvicorn
    app = mcp.streamable_http_app()
    # proxy_headers=True + forwarded_allow_ips="*" lets uvicorn trust ACA's ingress
    # proxy and fixes the "Invalid Host header" 421 error from Foundry connections
    uvicorn.run(app, host="0.0.0.0", port=8000, proxy_headers=True, forwarded_allow_ips="*")
except Exception as e:
    log.exception("Failed to start server: %s", e)
    sys.exit(1)
