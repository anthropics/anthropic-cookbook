"""Ephemeral mode: run the research agent once on ``$PROMPT`` and exit.

This is what ``entrypoint.sh`` invokes when the container is run without
``serve``. It's the smallest possible deployment — no server, no sessions,
just one prompt in and one result out.
"""

from __future__ import annotations

import asyncio
import os
import sys

from research_agent.agent import send_query

# Same default as server.py: Sonnet keeps test runs cheap. Override with
# MODEL=claude-opus-5-5 to match notebook 00's DEFAULT_MODEL.
DEFAULT_MODEL = "claude-sonnet-5-5"

# Unlike server.py, this path keeps notebook 00's default tools (including Read):
# the caller controls $PROMPT and the container holds no other sessions' state,
# so there is nothing sensitive for a hostile web result to point Read at.


async def _main() -> int:
    prompt = os.environ.get("PROMPT")
    if not prompt:
        print("error: PROMPT env var is required", file=sys.stderr)
        return 2
    result = await send_query(
        prompt,
        model=os.environ.get("MODEL", DEFAULT_MODEL),
        display_result=False,
    )
    if result:
        print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
