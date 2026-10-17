"""CLI command to run the Easy Convert MCP Server."""

from src.interfaces.cli.ui import print_info
from src.interfaces.mcp.server import main as run_mcp_server


def mcp() -> None:
    """Start the Model Context Protocol (MCP) server over standard I/O (stdio)."""
    # Note: Stdio server must keep stdout clean for JSON-RPC messages; messages go to stderr
    print_info("Starting Easy Convert MCP Server on stdio...", title="MCP Server")
    run_mcp_server()
