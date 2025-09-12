"""
Observability Agent - GitHub monitoring with MCP servers
Built on top of the research agent pattern
"""

import asyncio
import os
from collections.abc import Callable
from typing import Any

from dotenv import load_dotenv

from claude_code_sdk import ClaudeCodeOptions, ClaudeSDKClient

load_dotenv()


def get_activity_text(msg) -> str | None:
    """Extract activity text from a message"""
    try:
        if "Assistant" in msg.__class__.__name__:
            if hasattr(msg, "content") and msg.content:
                first_content = msg.content[0] if isinstance(msg.content, list) else msg.content
                if hasattr(first_content, "name"):
                    return f"🤖 Using: {first_content.name}()"
            return "🤖 Thinking..."
        elif "User" in msg.__class__.__name__:
            return "✓ Tool completed"
    except (AttributeError, IndexError):
        pass
    return None


def print_activity(msg) -> None:
    """Print activity to console"""
    activity = get_activity_text(msg)
    if activity:
        print(activity)


# Pre-configured GitHub MCP server
GITHUB_MCP_SERVER = {
    "github": {
        "command": "docker",
        "args": [
            "run",
            "-i",
            "--rm",
            "-e",
            "GITHUB_PERSONAL_ACCESS_TOKEN",
            "ghcr.io/github/github-mcp-server",
        ],
        "env": {"GITHUB_PERSONAL_ACCESS_TOKEN": os.environ.get("GITHUB_TOKEN")},
    }
}


async def send_query(
    prompt: str,
    activity_handler: Callable[[Any], None | Any] = print_activity,
    continue_conversation: bool = False,
    mcp_servers: dict[str, Any] | None = None,
    use_github: bool = True,
) -> str | None:
    """
    Send a query to the observability agent with MCP server support.

    Args:
        prompt: The query to send
        activity_handler: Callback for activity updates
        continue_conversation: Continue the previous conversation if True
        mcp_servers: Custom MCP servers configuration
        use_github: Include GitHub MCP server (default: True)

    Returns:
        The final result text or None if no result
    """
    # Build MCP servers config
    servers = {}
    if use_github and os.environ.get("GITHUB_TOKEN"):
        servers.update(GITHUB_MCP_SERVER)
    if mcp_servers:
        servers.update(mcp_servers)

    options = ClaudeCodeOptions(
        model="claude-sonnet-4-20250514",
        allowed_tools=["mcp__github", "WebSearch", "Read"],
        continue_conversation=continue_conversation,
        system_prompt="You are an observability agent specialized in monitoring GitHub repositories and CI/CD workflows",
        mcp_servers=servers if servers else None,
        permission_mode="acceptEdits",
    )

    result = None

    try:
        async with ClaudeSDKClient(options=options) as agent:
            await agent.query(prompt=prompt)
            async for msg in agent.receive_response():
                if asyncio.iscoroutinefunction(activity_handler):
                    await activity_handler(msg)
                else:
                    activity_handler(msg)

                if hasattr(msg, "result"):
                    result = msg.result
    except Exception as e:
        print(f"❌ Query error: {e}")
        raise

    return result
