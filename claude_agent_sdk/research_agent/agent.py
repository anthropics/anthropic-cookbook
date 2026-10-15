"""
Research Agent - Using Claude SDK with built-in session management.

This agent demonstrates web search and multimodal research capabilities
using the Claude Agent SDK. It uses WebSearch for information gathering
and Read for analyzing images and documents.

Key design decisions:
- Uses shared visualization utilities for consistent display
- Includes citation requirements in system prompt for verifiable research
- Supports multi-turn conversations for iterative research
"""

import asyncio
from collections.abc import Callable
from typing import Any

from dotenv import load_dotenv
from utils.agent_visualizer import (
    display_agent_response,
    print_activity,
    reset_activity_context,
)

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient

load_dotenv()

# Default model for the research agent
DEFAULT_MODEL = "claude-opus-5-5"

# System prompt with citation requirements for research quality
RESEARCH_SYSTEM_PROMPT = """You are a research agent specialized in AI.

When providing research findings:
- Always include source URLs as citations
- Format citations as markdown links: [Source Title](URL)
- Group sources in a "Sources:" section at the end of your response"""


def get_activity_text(msg: Any) -> str | None:
    """
    Extract activity text from a message for custom logging/monitoring.

    This function is provided for users who want to implement custom
    activity handlers (e.g., for logging, WebSocket streaming, etc.)

    Args:
        msg: A message object from the agent response stream

    Returns:
        A formatted activity string, or None if not applicable
    """
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


async def send_query(
    prompt: str,
    activity_handler: Callable[[Any], None | Any] = print_activity,
    continue_conversation: bool = False,
    model: str = DEFAULT_MODEL,
    display_result: bool = True,
) -> str | None:
    """
    Send a query to the research agent with web search and multimodal support.

    Args:
        prompt: The query to send
        activity_handler: Callback for activity updates (default: print_activity)
        continue_conversation: Continue the previous conversation if True
        model: Model to use (default: claude-opus-5-5)
        display_result: If True, display the response using display_agent_response()
            after completion. Set to False for programmatic use.

    Note:
        For the activity_handler - we support both sync and async handlers
        to make the module work in different contexts:
            - Sync handlers (like print_activity) for simple console output
            - Async handlers for web apps that need WebSocket/network I/O
        In production, you'd typically use just one type based on your needs

    Returns:
        The final result text or None if no result
    """
    # Only reset activity context for new conversations, not continuations
    if not continue_conversation:
        reset_activity_context()

    options = ClaudeAgentOptions(
        model=model,
        allowed_tools=["WebSearch", "Read"],
        continue_conversation=continue_conversation,
        system_prompt=RESEARCH_SYSTEM_PROMPT,
        max_buffer_size=10 * 1024 * 1024,  # 10MB buffer for handling images and large responses
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
