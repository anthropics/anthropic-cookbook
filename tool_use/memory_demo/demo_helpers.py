"""
Helper functions for memory cookbook demos.

This module provides reusable functions for running conversation loops
with Claude, handling tool execution, and managing context.
"""

from typing import Any

from anthropic import Anthropic
from memory_tool import MemoryToolHandler


def execute_tool(tool_use: Any, memory_handler: MemoryToolHandler) -> str:
    """
    Execute a tool use and return the result.

    Args:
        tool_use: The tool use object from Claude's response
        memory_handler: The memory tool handler instance

    Returns:
        str: The result of the tool execution
    """
    if tool_use.name == "memory":
        result = memory_handler.execute(**tool_use.input)
        return result.get("success") or result.get("error", "Unknown error")
    return f"Unknown tool: {tool_use.name}"


def run_conversation_turn(
    client: Anthropic,
    model: str,
    messages: list[dict[str, Any]],
    memory_handler: MemoryToolHandler,
    system: str,
    context_management: dict[str, Any] | None = None,
    thinking: dict[str, Any] | None = None,
    max_tokens: int = 1024,
    verbose: bool = False,
) -> tuple[Any, list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Run a single conversation turn, handling tool uses.

    Args:
        client: Anthropic client instance
        model: Model to use
        messages: Current conversation messages
        memory_handler: Memory tool handler instance
        system: System prompt
        context_management: Optional context management config
        thinking: Optional thinking config (e.g., {"type": "adaptive"})
        max_tokens: Max tokens for response
        verbose: Whether to print tool operations

    Returns:
        Tuple of (response, assistant_content, tool_results)
    """
    memory_tool: dict[str, Any] = {"type": "memory_20250818", "name": "memory"}

    request_params: dict[str, Any] = {
        "model": model,
        "max_tokens": max_tokens,
        "system": system,
        "messages": messages,
        "tools": [memory_tool],
        "betas": ["context-management-2025-06-27"],
    }

    if thinking:
        request_params["thinking"] = thinking

    if context_management:
        request_params["context_management"] = context_management

    response = client.beta.messages.create(**request_params)

    assistant_content = []
    tool_results = []

    for content in response.content:
        if content.type == "thinking":
            # Include thinking blocks in assistant content (required for tool use with thinking)
            # Must include signature field when passing back to API
            if verbose:
                thinking_preview = (
                    content.thinking[:100] + "..."
                    if len(content.thinking) > 100
                    else content.thinking
                )
                print(f"🧠 Thinking: {thinking_preview}")
            thinking_block = {"type": "thinking", "thinking": content.thinking}
            if hasattr(content, "signature") and content.signature:
                thinking_block["signature"] = content.signature
            assistant_content.append(thinking_block)
        elif content.type == "text":
            if verbose:
                print(f"💬 Claude: {content.text}\n")
            assistant_content.append({"type": "text", "text": content.text})
        elif content.type == "tool_use":
            if verbose:
                cmd = content.input.get("command")
                path = content.input.get("path", "")
                print(f"  🔧 Memory tool: {cmd} {path}")

            result = execute_tool(content, memory_handler)

            if verbose:
                result_preview = result[:80] + "..." if len(result) > 80 else result
                print(f"  ✓ Result: {result_preview}")

            assistant_content.append(
                {"type": "tool_use", "id": content.id, "name": content.name, "input": content.input}
            )
            tool_results.append(
                {"type": "tool_result", "tool_use_id": content.id, "content": result}
            )

    return response, assistant_content, tool_results


def run_conversation_loop(
    client: Anthropic,
    model: str,
    messages: list[dict[str, Any]],
    memory_handler: MemoryToolHandler,
    system: str,
    context_management: dict[str, Any] | None = None,
    thinking: dict[str, Any] | None = None,
    max_tokens: int = 1024,
    max_turns: int = 5,
    verbose: bool = False,
) -> Any:
    """
    Run a complete conversation loop until Claude stops using tools.

    Args:
        client: Anthropic client instance
        model: Model to use
        messages: Current conversation messages (will be modified in-place)
        memory_handler: Memory tool handler instance
        system: System prompt
        context_management: Optional context management config
        thinking: Optional thinking config (e.g., {"type": "adaptive"})
        max_tokens: Max tokens for response
        max_turns: Maximum number of turns to prevent infinite loops
        verbose: Whether to print progress

    Returns:
        The final API response
    """
    turn = 1
    response = None

    while turn <= max_turns:
        if verbose:
            print(f"\n🔄 Turn {turn}:")

        response, assistant_content, tool_results = run_conversation_turn(
            client=client,
            model=model,
            messages=messages,
            memory_handler=memory_handler,
            system=system,
            context_management=context_management,
            thinking=thinking,
            max_tokens=max_tokens,
            verbose=verbose,
        )

        messages.append({"role": "assistant", "content": assistant_content})

        if tool_results:
            messages.append({"role": "user", "content": tool_results})
            turn += 1
        else:
            # No more tool uses, conversation complete
            break

    return response


def print_context_management_info(response: Any) -> tuple[bool, int]:
    """
    Print context management information from response.

    Args:
        response: API response to analyze

    Returns:
        Tuple of (context_cleared, saved_tokens)
    """
    context_cleared = False
    saved_tokens = 0

    if hasattr(response, "context_management") and response.context_management:
        edits = getattr(response.context_management, "applied_edits", []) or []
        if edits:
            context_cleared = True
            print("  ✂️  Context editing triggered!")

            # Process all edits and sum up what was cleared
            total_tokens = 0
            for edit in edits:
                edit_type = getattr(edit, "type", "unknown")
                tokens = getattr(edit, "cleared_input_tokens", 0) or 0
                total_tokens += tokens

                if "thinking" in edit_type:
                    thinking_turns = getattr(edit, "cleared_thinking_turns", 0) or 0
                    if thinking_turns > 0 or tokens > 0:
                        print(
                            f"      • Cleared {thinking_turns} thinking turn(s), saved {tokens:,} tokens"
                        )
                elif "tool_uses" in edit_type:
                    tool_uses = getattr(edit, "cleared_tool_uses", 0) or 0
                    if tool_uses > 0 or tokens > 0:
                        print(f"      • Cleared {tool_uses} tool use(s), saved {tokens:,} tokens")

            saved_tokens = total_tokens
            print(f"      • After clearing: {response.usage.input_tokens:,} tokens")
        else:
            print("  ℹ️  Context below threshold - no clearing triggered")
    else:
        print("  ℹ️  No context management applied")

    return context_cleared, saved_tokens
