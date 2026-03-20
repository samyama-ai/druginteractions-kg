#!/usr/bin/env python3
"""Drug Interactions KG MCP Server.

Exposes a drug interactions & pharmacogenomics knowledge graph
(DrugBank, DGIdb, SIDER, ChEMBL, TTD, OpenFDA) as MCP tools.

Usage:
    # Connect to running Samyama server with pre-loaded data:
    python -m mcp_server.server --url http://localhost:8080

    # Embedded mode (loads data on startup):
    python -m mcp_server.server --data-dir data

    # List all tools:
    python -m mcp_server.server --url http://localhost:8080 --list-tools

    # Claude Desktop config:
    # {"mcpServers": {"druginteractions-kg": {
    #     "command": "python", "args": ["-m", "mcp_server.server", "--url", "http://localhost:8080"]}}}
"""

from __future__ import annotations

import argparse
import os
import sys


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="druginteractions-kg-mcp",
        description="Drug Interactions KG MCP Server (powered by samyama-mcp-serve)",
    )
    parser.add_argument("--url", default=None,
                        help="Connect to a running Samyama server.")
    parser.add_argument("--data-dir", default="data",
                        help="Root directory containing downloaded data files.")
    parser.add_argument("--phases", nargs="*", default=None,
                        help="ETL phases to load (default: all).")
    parser.add_argument("--list-tools", action="store_true",
                        help="Print discovered tools and exit.")
    parser.add_argument("--name", default="Drug Interactions KG",
                        help="MCP server name.")

    args = parser.parse_args(argv)

    from samyama import SamyamaClient

    if args.url:
        client = SamyamaClient.connect(args.url)
    else:
        client = SamyamaClient.embedded()
        _load_data(client, args.data_dir, args.phases)

    config_path = os.path.join(os.path.dirname(__file__), "config.yaml")

    from samyama_mcp.config import ToolConfig
    from samyama_mcp.server import SamyamaMCPServer

    config = ToolConfig.from_yaml(config_path)
    server = SamyamaMCPServer(client, server_name=args.name, config=config)

    if args.list_tools:
        tools = server.list_tools()
        print(f"Drug Interactions KG: {len(tools)} tools\n")
        for name in sorted(tools):
            print(f"  - {name}")
        sys.exit(0)

    server.run()


def _load_data(client, data_dir: str, phases: list[str] | None) -> None:
    """Load drug interactions data from downloaded files."""
    if not os.path.isdir(data_dir):
        print(
            f"Warning: data directory '{data_dir}' not found. "
            f"Starting with empty graph.",
            file=sys.stderr,
        )
        return

    from etl.loader import load_druginteractions

    stats = load_druginteractions(client, data_dir=data_dir, phases=phases)
    total_nodes = sum(v for k, v in stats.items() if k.endswith("_nodes"))
    total_edges = sum(v for k, v in stats.items() if k.endswith("_edges"))
    print(
        f"Loaded drug interactions graph: {total_nodes} nodes, {total_edges} edges "
        f"({len(stats.get('phases_loaded', []))} phases)",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
