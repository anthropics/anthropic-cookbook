"""
Observability Agent - GitHub monitoring with MCP servers.

This agent demonstrates MCP (Model Context Protocol) integration for GitHub
monitoring and CI/CD workflow analysis. It uses the official GitHub MCP server
to interact with the GitHub API.

Key design decisions:
- Uses dontAsk with an MCP-only allowlist so built-in tools fail closed
- Explicitly disallows built-in tools as defense in depth
- Focused on read-only GitHub operations for observability
- Supports multi-turn conversations for deep-dive analysis
"""

import asyncio
import os
from collections.abc import Callable
from typing import Any

from dotenv import load_dotenv
from utils.agent_visualizer import (
    display_agent_response,
    print_activity,
    reset_activity_context,
)

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient, McpServerConfig

load_dotenv()

# Default model for the observability agent
DEFAULT_MODEL = "claude-opus-4-6"

# System prompt optimized for observability tasks
DEFAULT_SYSTEM_PROMPT = """You are an observability agent specialized in monitoring \
GitHub repositories and CI/CD workflows. Provide concise, actionable insights \
suitable for on-call engineers. Focus on identifying issues, assessing severity, \
and recommending next steps."""

MCP_ONLY_DISALLOWED_TOOLS = [
    "Read",
    "Edit",
    "Write",
    "Bash",
    "Task",
    "WebSearch",
    "WebFetch",
]


def get_github_mcp_server() -> dict[str, McpServerConfig]:
    """
    Get the GitHub MCP server configuration.

    Returns:
        MCP server config dict, or empty dict if GITHUB_TOKEN not set.
    """
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        return {}

    return {
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
            "env": {"GITHUB_PERSONAL_ACCESS_TOKEN": token},
        }
    }


async def send_query(
    prompt: str,
    activity_handler: Callable[[Any], None | Any] = print_activity,
    continue_conversation: bool = False,
    mcp_servers: dict[str, McpServerConfig] | None = None,
    use_github: bool = True,
    model: str = DEFAULT_MODEL,
    restrict_to_mcp: bool = True,
    display_result: bool = True,
) -> str | None:
    """
    Send a query to the observability agent with MCP server support.

    Args:
        prompt: The query to send
        activity_handler: Callback for activity updates (default: print_activity)
        continue_conversation: Continue the previous conversation if True
        mcp_servers: Custom MCP servers configuration (merged with GitHub if enabled)
        use_github: Include GitHub MCP server (default: True)
        model: Model to use (default: claude-opus-4-6)
        restrict_to_mcp: If True, allow only configured MCP servers and deny
            built-in tools without prompting. Set to False if you want the agent
            to have fallback options.
        display_result: If True, display the response using display_agent_response()
            after completion. Set to False for programmatic use.

    Returns:
        The final result text or None if no result.
    """
    # Only reset activity context for new conversations, not continuations
    if not continue_conversation:
        reset_activity_context()

    # Build MCP servers config
    servers: dict[str, McpServerConfig] = {}
    if use_github:
        servers.update(get_github_mcp_server())
    if mcp_servers:
        servers.update(mcp_servers)

    # Build allowed tools list based on configured MCP servers
    allowed_tools = [f"mcp__{name}__*" for name in servers]

    # In dontAsk mode, tools outside allowed_tools are denied instead of prompting.
    # Keep an explicit built-in denylist as defense in depth.
    disallowed_tools = MCP_ONLY_DISALLOWED_TOOLS if restrict_to_mcp else []
    permission_mode = "dontAsk" if restrict_to_mcp else "acceptEdits"

    options = ClaudeAgentOptions(
        model=model,
        allowed_tools=allowed_tools,
        disallowed_tools=disallowed_tools,
        continue_conversation=continue_conversation,
        system_prompt=DEFAULT_SYSTEM_PROMPT,
        mcp_servers=servers,  # Empty dict is valid, no need for None
        permission_mode=permission_mode,
    )

    result = None
    messages: list[Any] = []

    try:
        async with ClaudeSDKClient(options=options) as agent:
            await agent.query(prompt=prompt)
            async for msg in agent.receive_response():
                messages.append(msg)
                if asyncio.iscoroutinefunction(activity_handler):
                    await activity_handler(msg)
                else:
                    activity_handler(msg)

                if hasattr(msg, "result"):
                    result = msg.result
    except Exception as e:
        print(f"❌ Query error: {e}")
        raise

    # Display the result using the shared visualization utility
    if display_result and messages:
        display_agent_response(messages)

    return result
