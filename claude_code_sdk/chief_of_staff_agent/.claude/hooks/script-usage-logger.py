#!/usr/bin/env python3
"""
PostToolUse hook: Logs when Python scripts are executed via the Bash tool
Distinguishes between:
- Tools: The Claude SDK tools (Bash, Write, Edit, etc.)
- Scripts: Python scripts executed through the Bash tool
"""

import json
import os
import sys
from datetime import datetime


def log_script_usage(tool_name, tool_input, tool_response):
    """Log execution of Python scripts via Bash tool"""

    # Only track Bash tool (which is used to execute scripts)
    if tool_name != "Bash":
        return

    # Get the command from tool input
    command = tool_input.get("command", "")

    # Check if it's executing a Python script from scripts/ directory
    # Support both: "python scripts/file.py" and "./scripts/file.py"
    import re

    # Try to match either pattern: python scripts/... or ./scripts/... or scripts/...
    script_match = re.search(r"(?:python\s+)?(?:\./)?scripts/(\w+\.py)", command)
    if not script_match:
        return

    # Only proceed if it's a scripts/ directory execution
    if "scripts/" not in command:
        return

    script_file = script_match.group(1)

    # Prepare log file path
    log_file = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "../../audit/script_usage_log.json"
    )

    try:
        # Load existing log or create new
        if os.path.exists(log_file):
            with open(log_file) as f:
                log_data = json.load(f)
        else:
            log_data = {"script_executions": []}

        # Create log entry
        entry = {
            "timestamp": datetime.now().isoformat(),
            "script": script_file,
            "command": command,
            "description": tool_input.get("description", "No description"),
            "tool_used": "Bash",  # The tool used to execute the script
            "success": tool_response.get("success", True) if tool_response else True,
        }

        # Add to log
        log_data["script_executions"].append(entry)

        # Keep only last 100 entries
        log_data["script_executions"] = log_data["script_executions"][-100:]

        # Save updated log
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        with open(log_file, "w") as f:
            json.dump(log_data, f, indent=2)

        print(f"📜 Script executed: {script_file}")

    except Exception as e:
        print(f"Script logging error: {e}", file=sys.stderr)


# Main execution
if __name__ == "__main__":
    try:
        # Read input from stdin
        input_data = json.load(sys.stdin)

        tool_name = input_data.get("tool_name", "")
        tool_input = input_data.get("tool_input", {})
        tool_response = input_data.get("tool_response", {})

        # Log the script usage (when executed via Bash tool)
        log_script_usage(tool_name, tool_input, tool_response)

        # Always exit successfully
        sys.exit(0)

    except Exception as e:
        print(f"Hook error: {e}", file=sys.stderr)
        sys.exit(0)
