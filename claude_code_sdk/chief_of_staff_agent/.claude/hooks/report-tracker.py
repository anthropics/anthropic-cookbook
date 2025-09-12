#!/usr/bin/env python3
"""
PostToolUse hook: Tracks ALL file writes and edits
Maintains history of all document changes for compliance
"""

import json
import os
import sys
from datetime import datetime


def track_report(tool_name, tool_input, tool_response):
    """Log ALL file creation/modification for audit trail"""

    # Debug: Log that hook was called
    print(f"🔍 Hook called for tool: {tool_name}", file=sys.stderr)

    # Get file path from tool input
    file_path = tool_input.get("file_path", "")

    if not file_path:
        print("⚠️ No file_path in tool_input", file=sys.stderr)
        return

    print(f"📝 Tracking file: {file_path}", file=sys.stderr)

    # Track ALL file writes/edits (no filtering)

    # Prepare history file path
    history_file = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "../../audit/report_history.json"
    )

    try:
        # Load existing history or create new
        if os.path.exists(history_file):
            with open(history_file) as f:
                history = json.load(f)
        else:
            history = {"reports": []}

        # Determine action type
        action = "created" if tool_name == "Write" else "modified"

        # Calculate word count if content available
        content = tool_input.get("content", "") or tool_input.get("new_string", "")
        word_count = len(content.split()) if content else 0

        # Create history entry
        entry = {
            "timestamp": datetime.now().isoformat(),
            "file": os.path.basename(file_path),
            "path": file_path,
            "action": action,
            "word_count": word_count,
            "tool": tool_name,
        }

        # Add to history
        history["reports"].append(entry)

        # Keep only last 50 entries
        history["reports"] = history["reports"][-50:]

        # Save updated history
        os.makedirs(os.path.dirname(history_file), exist_ok=True)
        with open(history_file, "w") as f:
            json.dump(history, f, indent=2)

        print(f"📊 File tracked: {os.path.basename(file_path)} ({action})")

    except Exception as e:
        print(f"Report tracking error: {e}", file=sys.stderr)


# Main execution
if __name__ == "__main__":
    try:
        # Read input from stdin
        input_data = json.load(sys.stdin)

        tool_name = input_data.get("tool_name", "")
        tool_input = input_data.get("tool_input", {})
        tool_response = input_data.get("tool_response", {})

        # Track the report
        track_report(tool_name, tool_input, tool_response)

        # Always exit successfully
        sys.exit(0)

    except Exception as e:
        print(f"Hook error: {e}", file=sys.stderr)
        sys.exit(0)
