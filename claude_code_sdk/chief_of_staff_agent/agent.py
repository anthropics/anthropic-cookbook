"""
Chief of Staff Agent
"""

import asyncio
import json
import os
from collections.abc import Callable
from typing import Any, Literal

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


async def send_query(
    prompt: str,
    continue_conversation: bool = False,
    permission_mode: Literal["default", "plan", "acceptEdits"] = "default",
    output_style: str | None = None,
    activity_handler: Callable[[Any], None | Any] = print_activity,
) -> tuple[str | None, list]:
    """
    Send a query to the Chief of Staff agent with all features integrated.

    Args:
        prompt: The query to send (can include slash commands like /budget-impact)
        activity_handler: Callback for activity updates (default: print_activity)
        continue_conversation: Continue the previous conversation if True
        permission_mode: "default" (execute), "plan" (think only), or "acceptEdits"
        output_style: Override output style (e.g., "executive", "technical", "board-report")

    Returns:
        Tuple of (result, messages) - result is the final text, messages is the full conversation

    Features automatically included/leveraged:
        - Memory: CLAUDE.md context loaded from chief_of_staff/CLAUDE.md
        - Subagents: financial-analyst and recruiter via Task tool (defined in .claude/agents)
        - Custom scripts: Python scripts in tools/ via Bash
        - Slash commands: Expanded from .claude/commands/
        - Output styles: Custom output styles defined in .claude/output-styles
        - Hooks: Triggered based on settings.local.json, defined in .claude/hooks
    """

    system_prompt = """You are the Chief of Staff for TechStart Inc, a 50-person startup.

        Apart from your tools and two subagents, you also have custom Python scripts in the scripts/ directory you can run with Bash:
        - python scripts/financial_forecast.py: Advanced financial modeling
        - python scripts/talent_scorer.py: Candidate scoring algorithm
        - python scripts/decision_matrix.py: Strategic decision framework

        You have access to company data in the financial_data/ directory.
        """

    # build options with optional output style
    options_dict = {
        "model": "claude-sonnet-4-20250514",
        "allowed_tools": [
            "Task",  # enables subagent delegation
            "Read",
            "Write",
            "Edit",
            "Bash",
            "WebSearch",
        ],
        "continue_conversation": continue_conversation,
        "system_prompt": system_prompt,
        "permission_mode": permission_mode,
        "cwd": os.path.dirname(os.path.abspath(__file__)),
    }

    # add output style if specified
    if output_style:
        options_dict["settings"] = json.dumps({"outputStyle": output_style})

    options = ClaudeCodeOptions(**options_dict)

    result = None
    messages = []  # this is to append the messages ONLY for this agent turn

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

    return result, messages
