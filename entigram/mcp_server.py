import sys
from typing import Optional

from entigram.mcp_service import EntigramMCPService


def create_mcp_server(target_dir: str = ".", host: Optional[str] = None, port: Optional[int] = None):
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:
        raise RuntimeError(
            "The MCP SDK is required for `etg serve`. "
            "Install project dependencies, including `mcp`, and retry."
        ) from exc

    kwargs = {}
    if host is not None:
        kwargs["host"] = host
    if port is not None:
        kwargs["port"] = port

    mcp = FastMCP("entigram", **kwargs)
    service = EntigramMCPService(target_dir)

    @mcp.tool()
    def etg_get_schemas() -> str:
        """Return local LDS schemas and parsed entity boundaries."""
        try:
            return service.get_schemas()
        except Exception as exc:
            return f"Error: Failed to read schemas - {exc}"

    @mcp.tool()
    def etg_propose_alignment(payload: str) -> str:
        """Validate and record a proposed semantic alignment."""
        try:
            return service.propose_alignment(payload)
        except Exception as exc:
            return f"Error: Invalid Schema Alignment - {exc}"

    @mcp.tool()
    def etg_log_conflict(payload: str) -> str:
        """Validate and log a deterministic conflict for human review."""
        try:
            return service.log_conflict(payload)
        except Exception as exc:
            return f"Error: Invalid Conflict - {exc}"

    return mcp


def run_mcp_server(
    target_dir: str = ".",
    *,
    transport: str = "stdio",
    host: str = "127.0.0.1",
    port: int = 8080,
):
    if transport not in {"stdio", "sse"}:
        raise ValueError("transport must be 'stdio' or 'sse'")

    try:
        server = create_mcp_server(
            target_dir,
            host=host if transport == "sse" else None,
            port=port if transport == "sse" else None,
        )
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc

    server.run(transport=transport)
