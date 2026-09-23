"""Azure Function App entry point — ASGI adapter for the MCP server.

Bridges Azure Functions HTTP trigger to the FastMCP streamable-http ASGI app.
All MCP server logic (server.py, tools/, analyzers/) is unchanged.
Auth is handled by EasyAuth at the platform level (AuthLevel.ANONYMOUS here).
"""
import logging
import os
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("function_app")

import azure.functions as func
from server import mcp

log.info("MCP server imported. Tools: %s", [t.name for t in mcp._tool_manager.list_tools()])


class FoundryTransportShim:
    """Adapt the streamable-HTTP transport to the Azure Functions + Foundry combination.

    1. GET/DELETE -> 405. The Functions ASGI bridge buffers a response until the ASGI
       app finishes, so an open-ended SSE stream never returns and the client times out
       during initialization. The MCP spec permits 405 to signal no server-initiated
       stream, and stateless mode does not need one.
    2. Accept header is rewritten to list both media types. Foundry Agent Service sends
       only "text/event-stream", but the MCP transport rejects (406) any request that
       does not accept both application/json and text/event-stream.
    """

    _BODY = (
        b'{"jsonrpc":"2.0","id":null,"error":{"code":-32601,'
        b'"message":"Server-initiated streaming is not supported; use POST."}}'
    )
    _ACCEPT = b"application/json, text/event-stream"

    def __init__(self, asgi_app):
        self._app = asgi_app

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            await self._app(scope, receive, send)
            return

        if scope.get("method") in ("GET", "DELETE"):
            await send({
                "type": "http.response.start",
                "status": 405,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"allow", b"POST"),
                    (b"content-length", str(len(self._BODY)).encode()),
                ],
            })
            await send({"type": "http.response.body", "body": self._BODY})
            return

        scope = dict(scope)
        scope["headers"] = [
            (k, v) for k, v in scope.get("headers", []) if k.lower() != b"accept"
        ] + [(b"accept", self._ACCEPT)]

        await self._app(scope, receive, send)


# ANONYMOUS because Entra ID EasyAuth validates tokens at the platform layer
app = func.AsgiFunctionApp(
    app=FoundryTransportShim(mcp.streamable_http_app()),
    http_auth_level=func.AuthLevel.ANONYMOUS,
)
