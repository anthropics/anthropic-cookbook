"""
Research Agent - Using Claude SDK with built-in session management
"""

import asyncio
from collections.abc import Callable
from typing import Any

from dotenv import load_dotenv

from claude_code_sdk import ClaudeCodeOptions, ClaudeSDKClient

load_dotenv()


def get_activity_text(msg) -> str | None:
    """Extract activity text from a message"""
    try:
        if "Assistant" in msg.__class__.__name__:
            # Check if content exists and has items
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


async def send_query(
    prompt: str,
    activity_handler: Callable[[Any], None | Any] = print_activity,
    continue_conversation: bool = False,
) -> str | None:
    """
    Send a query using the Claude SDK with minimal overhead.

    Args:
        prompt: The query to send
        activity_handler: Callback for activity updates
        continue_conversation: Continue the previous conversation if True

    Note:
        For the activity_handler - we support both sync and async handlers
        to make the module work in different contexts:
            - Sync handlers (like print_activity) for simple console output
            - Async handlers for web apps that need WebSocket/network I/O
        In production, you'd typically use just one type based on your needs

    Returns:
        The final result text or None if no result
    """
    options = ClaudeCodeOptions(
        model="claude-sonnet-4-20250514",
        allowed_tools=["WebSearch", "Read"],
        continue_conversation=continue_conversation,
        system_prompt="You are a research agent specialized in AI",
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
