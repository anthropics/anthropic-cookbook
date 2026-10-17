"""
Code Review Assistant Demo - Three-session demonstration.

This demo showcases:
1. Session 1: Claude learns debugging patterns
2. Session 2: Claude applies learned patterns (faster!)
3. Session 3: Long session with context editing

Requires:
- .env file with ANTHROPIC_API_KEY and ANTHROPIC_MODEL
- memory_tool.py in the same directory
"""

import os
import sys
from pathlib import Path
from typing import Any

from anthropic import Anthropic
from dotenv import load_dotenv

# Add parent directory to path to import memory_tool
sys.path.insert(0, str(Path(__file__).parent.parent))

from memory_tool import MemoryToolHandler

# Load environment variables
load_dotenv()

API_KEY = os.getenv("ANTHROPIC_API_KEY")
MODEL = os.getenv("ANTHROPIC_MODEL")

if not API_KEY:
    raise ValueError("ANTHROPIC_API_KEY not found. Copy .env.example to .env and add your API key.")

if not MODEL:
    raise ValueError("ANTHROPIC_MODEL not found. Copy .env.example to .env and set the model.")


# Context management configuration
CONTEXT_MANAGEMENT = {
    "edits": [
        {
            "type": "clear_tool_uses_20250919",
            "trigger": {"type": "input_tokens", "value": 30000},
            "keep": {"type": "tool_uses", "value": 3},
            "clear_at_least": {"type": "input_tokens", "value": 5000},
        }
    ]
}


class CodeReviewAssistant:
    """
    Code review assistant with memory and context editing capabilities.

    This assistant:
    - Checks memory for debugging patterns before reviewing code
    - Stores learned patterns for future sessions
    - Automatically clears old tool results when context grows large
    """

    def __init__(self, memory_storage_path: str = "./memory_storage"):
        """
        Initialize the code review assistant.

        Args:
            memory_storage_path: Path for memory storage
        """
        self.client = Anthropic()
        self.memory_handler = MemoryToolHandler(base_path=memory_storage_path)
        self.messages: list[dict[str, Any]] = []

    def _create_system_prompt(self) -> str:
        """Create system prompt with memory instructions."""
        return """You are an expert code reviewer focused on finding bugs and suggesting improvements.

MEMORY PROTOCOL:
1. Check your /memories directory for relevant debugging patterns or insights
2. When you find a bug or pattern, update your memory with what you learned
3. Keep your memory organized - use descriptive file names and clear content

When reviewing code:
- Identify bugs, security issues, and code quality problems
- Explain the issue clearly
- Provide a corrected version
- Store important patterns in memory for future reference

Remember: Your memory persists across conversations. Use it wisely."""

    def _execute_tool_use(self, tool_use: Any) -> str:
        """Execute a tool use and return the result."""
        if tool_use.name == "memory":
            result = self.memory_handler.execute(**tool_use.input)
            return result.get("success") or result.get("error", "Unknown error")
        return f"Unknown tool: {tool_use.name}"

    def review_code(self, code: str, filename: str, description: str = "") -> dict[str, Any]:
        """
        Review code with memory-enhanced analysis.

        Args:
            code: The code to review
            filename: Name of the file being reviewed
            description: Optional description of what to look for

        Returns:
            Dict with review results and metadata
        """
        # Construct user message
        user_message = f"Please review this code from {filename}"
        if description:
            user_message += f"\n\nContext: {description}"
        user_message += f"\n\n```python\n{code}\n```"

        self.messages.append({"role": "user", "content": user_message})

        # Track token usage and context management
        total_input_tokens = 0
        context_edits_applied = []

        # Conversation loop
        turn = 1
        while True:
            print(f"  🔄 Turn {turn}: Calling Claude API...", end="", flush=True)
            response = self.client.beta.messages.create(
                model=MODEL,
                max_tokens=4096,
                system=self._create_system_prompt(),
                messages=self.messages,
                tools=[{"type": "memory_20250818", "name": "memory"}],
                betas=["context-management-2025-06-27"],
                context_management=CONTEXT_MANAGEMENT,
            )

            print(" ✓")

            # Track usage
            total_input_tokens = response.usage.input_tokens

            # Check for context management
            if hasattr(response, "context_management") and response.context_management:
                applied = getattr(response.context_management, "applied_edits", [])
                if applied:
                    context_edits_applied.extend(applied)

            # Process response content
            assistant_content = []
            tool_results = []
            final_text = []

            for content in response.content:
                if content.type == "thinking":
                    # Pass thinking blocks back unchanged (with signature) so the
                    # tool-use loop stays valid when the model emits them.
                    assistant_content.append(
                        {
                            "type": "thinking",
                            "thinking": content.thinking,
                            "signature": content.signature,
                        }
                    )
                elif content.type == "text":
                    assistant_content.append({"type": "text", "text": content.text})
                    final_text.append(content.text)
                elif content.type == "tool_use":
                    cmd = content.input.get("command", "unknown")
                    path = content.input.get("path", "")
                    print(f"    🔧 Memory: {cmd} {path}")

                    # Execute tool
                    result = self._execute_tool_use(content)

                    assistant_content.append(
                        {
                            "type": "tool_use",
                            "id": content.id,
                            "name": content.name,
                            "input": content.input,
                        }
                    )

                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": content.id,
                            "content": result,
                        }
                    )

            # Add assistant message
            self.messages.append({"role": "assistant", "content": assistant_content})

            # If there are tool results, add them and continue
            if tool_results:
                self.messages.append({"role": "user", "content": tool_results})
                turn += 1
            else:
                # No more tool uses, we're done
                print()
                break

        return {
            "review": "\n".join(final_text),
            "input_tokens": total_input_tokens,
            "context_edits": context_edits_applied,
        }

    def start_new_session(self) -> None:
        """Start a new conversation session (memory persists)."""
        self.messages = []


def run_session_1() -> None:
    """Session 1: Learn debugging patterns."""
    print("=" * 80)
    print("SESSION 1: Learning from First Code Review")
    print("=" * 80)

    assistant = CodeReviewAssistant()

    # Read sample code
    with open("memory_demo/sample_code/web_scraper_v1.py") as f:
        code = f.read()

    print("\n📋 Reviewing web_scraper_v1.py...")
    print("\nMulti-threaded web scraper that sometimes loses results.\n")

    result = assistant.review_code(
        code=code,
        filename="web_scraper_v1.py",
        description="This scraper sometimes returns fewer results than expected. "
        "The count is inconsistent across runs. Can you find the issue?",
    )

    print("\n🤖 Claude's Review:\n")
    print(result["review"])
    print(f"\n📊 Input tokens used: {result['input_tokens']:,}")

    if result["context_edits"]:
        print(f"\n🧹 Context edits applied: {result['context_edits']}")

    print("\n✅ Session 1 complete - Claude learned debugging patterns!\n")


def run_session_2() -> None:
    """Session 2: Apply learned patterns."""
    print("=" * 80)
    print("SESSION 2: Applying Learned Patterns (New Conversation)")
    print("=" * 80)

    # New assistant instance (new conversation, but memory persists)
    assistant = CodeReviewAssistant()

    # Read different sample code with similar bug
    with open("memory_demo/sample_code/api_client_v1.py") as f:
        code = f.read()

    print("\n📋 Reviewing api_client_v1.py...")
    print("\nAsync API client with concurrent requests.\n")

    result = assistant.review_code(
        code=code,
        filename="api_client_v1.py",
        description="Review this async API client. "
        "It fetches multiple endpoints concurrently. Are there any issues?",
    )

    print("\n🤖 Claude's Review:\n")
    print(result["review"])
    print(f"\n📊 Input tokens used: {result['input_tokens']:,}")

    print("\n✅ Session 2 complete - Claude applied learned patterns faster!\n")


def run_session_3() -> None:
    """Session 3: Long session with context editing."""
    print("=" * 80)
    print("SESSION 3: Long Session with Context Editing")
    print("=" * 80)

    assistant = CodeReviewAssistant()

    # Read data processor code (has multiple issues)
    with open("memory_demo/sample_code/data_processor_v1.py") as f:
        code = f.read()

    print("\n📋 Reviewing data_processor_v1.py...")
    print("\nLarge file with multiple concurrent processing classes.\n")

    result = assistant.review_code(
        code=code,
        filename="data_processor_v1.py",
        description="This data processor handles files concurrently. "
        "There's also a SharedCache class. Review all components for issues.",
    )

    print("\n🤖 Claude's Review:\n")
    print(result["review"])
    print(f"\n📊 Input tokens used: {result['input_tokens']:,}")

    if result["context_edits"]:
        print("\n🧹 Context Management Applied:")
        for edit in result["context_edits"]:
            print(f"  - Type: {getattr(edit, 'type', 'unknown')}")
            print(f"  - Cleared tool uses: {getattr(edit, 'cleared_tool_uses', 0)}")
            print(f"  - Tokens saved: {getattr(edit, 'cleared_input_tokens', 0):,}")

    print("\n✅ Session 3 complete - Context editing kept conversation manageable!\n")


def main() -> None:
    """Run all three demo sessions."""
    print("\n🚀 Code Review Assistant Demo\n")
    print("This demo shows:")
    print("1. Session 1: Claude learns debugging patterns")
    print("2. Session 2: Claude applies learned patterns (new conversation)")
    print("3. Session 3: Long session with context editing\n")

    input("Press Enter to start Session 1...")
    run_session_1()

    input("Press Enter to start Session 2...")
    run_session_2()

    input("Press Enter to start Session 3...")
    run_session_3()

    print("=" * 80)
    print("🎉 Demo Complete!")
    print("=" * 80)
    print("\nKey Takeaways:")
    print("- Memory tool enabled cross-conversation learning")
    print("- Claude got faster at recognizing similar bugs")
    print("- Context editing handled long sessions gracefully")
    print("\n💡 For production GitHub PR reviews, check out:")
    print("   https://github.com/anthropics/claude-code-action\n")


if __name__ == "__main__":
    main()
