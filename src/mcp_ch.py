"""ClickHouse access via the official ClickHouse MCP server (mcp-clickhouse).

The domain tools in tools.py talk to ClickHouse directly through
clickhouse_connect (src/ch.py) -- fast, and enough for the agent's polished,
purpose-built questions. This module is a separate path: it launches the
official mcp-clickhouse server as a subprocess and calls its `run_query` tool
over the real MCP protocol, so the agent can also answer ad-hoc questions the
six domain tools don't cover, by writing its own SQL against the schema.
"""
import os
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

import config


def _server_params() -> StdioServerParameters:
    env = os.environ.copy()
    env.update(
        {
            "CLICKHOUSE_HOST": config.CH_HOST,
            "CLICKHOUSE_PORT": str(config.CH_PORT),
            "CLICKHOUSE_USER": config.CH_USER,
            "CLICKHOUSE_PASSWORD": config.CH_PASSWORD,
            "CLICKHOUSE_DATABASE": config.CH_DATABASE,
            "CLICKHOUSE_SECURE": "true",
        }
    )
    return StdioServerParameters(
        command=sys.executable, args=["-m", "mcp_clickhouse.main"], env=env
    )


async def run_sql_via_mcp(query: str) -> str:
    """Run a read-only SQL SELECT against ClickHouse via the official
    ClickHouse MCP server, for questions the other tools don't cover.

    The schema: scenes(project_id, scene_number, page_number, page_eighths,
    int_ext, time_of_day, location, set_name, synopsis, cast_members,
    background_actors, props, vehicles, wardrobe, makeup_hair, stunts, vfx,
    special_equipment, animals, minors, complexity_score, batch_id) and
    scene_elements(project_id, scene_number, category, element, int_ext,
    time_of_day, set_name, page_eighths, batch_id) -- category is one of
    cast, prop, vehicle, wardrobe, stunt, vfx, equipment, animal, minor.
    Always filter on project_id = 'demo_feature'. Only SELECT queries work.
    """
    async with stdio_client(_server_params()) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool("run_query", {"query": query})
            return "\n".join(
                part.text for part in result.content if hasattr(part, "text")
            )
