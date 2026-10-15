#!/usr/bin/env python3
"""
SRE Bot - Slack Integration with Claude Agent SDK

This version integrates with Slack for real-time incident response.
It uses the Claude Agent SDK with in-process MCP tools.

Configuration:
    Create a .env file with:
        ANTHROPIC_API_KEY=your-anthropic-key
        SLACK_BOT_TOKEN=xoxb-your-bot-token
        SLACK_APP_TOKEN=xapp-your-app-token

Usage:
    python sre_bot_slack.py
"""

import asyncio
import json
import os
import re
import sys
from pathlib import Path

# Check aiohttp for webhook server
try:
    from aiohttp import ClientSession, web
except ImportError:
    print("❌ aiohttp not installed")
    print("   Run: pip install aiohttp")
    sys.exit(1)

# Path to our subprocess MCP server (lives in the project root, one level up)
MCP_SERVER_PATH = Path(__file__).parent.parent / "sre_mcp_server.py"

# Load environment variables from .env file FIRST
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    print("⚠️  python-dotenv not installed, using environment variables only")
    print("   Run: pip install python-dotenv")

# Webhook server configuration (must be after dotenv loads)
WEBHOOK_PORT = int(os.environ.get("WEBHOOK_PORT", "8585"))
PAGERDUTY_API_KEY = os.environ.get("PAGERDUTY_API_KEY", "")

# Check Slack dependency
try:
    from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
    from slack_bolt.async_app import AsyncApp
except ImportError:
    print("❌ slack-bolt not installed")
    print("   Run: pip install slack-bolt")
    sys.exit(1)

# Check Claude Agent SDK
try:
    from claude_agent_sdk import (
        AssistantMessage,
        ClaudeAgentOptions,
        ResultMessage,
        TextBlock,
        ToolUseBlock,
        query,
    )
except ImportError:
    print("❌ claude-agent-sdk not installed")
    print("   Run: pip install claude-agent-sdk")
    print("")
    print("   Note: The SDK also requires Claude Code CLI:")
    print("   npm install -g @anthropic-ai/claude-code")
    sys.exit(1)

# Validate environment variables
missing_vars = []
for var in ["ANTHROPIC_API_KEY", "SLACK_BOT_TOKEN", "SLACK_APP_TOKEN"]:
    if not os.environ.get(var):
        missing_vars.append(var)

if missing_vars:
    print("❌ Missing required configuration:")
    for var in missing_vars:
        print(f"   - {var}")
    print("")
    print("   Create a .env file in this directory with:")
    print("       ANTHROPIC_API_KEY=your-anthropic-key")
    print("       SLACK_BOT_TOKEN=xoxb-your-bot-token")
    print("       SLACK_APP_TOKEN=xapp-your-app-token")
    sys.exit(1)


# Initialize Slack app
app = AsyncApp(token=os.environ["SLACK_BOT_TOKEN"])

# Slack channel for PagerDuty notifications (set in .env or defaults to #general)
SLACK_INCIDENT_CHANNEL = os.environ.get("SLACK_INCIDENT_CHANNEL", "#general")

# Store reference to Slack client for webhook handler
slack_client = None

# Track threads where the bot has been mentioned (for auto-responding to follow-ups)
# Key: thread_ts, Value: channel_id
MAX_ACTIVE_THREADS = 1000
active_threads: dict[str, str] = {}

# Store the most recent post-mortem URL (created before resolving incident)
pending_postmortem_url: str = ""


# ============================================================================
# PagerDuty Webhook Handler
# ============================================================================


async def handle_pagerduty_webhook(request: web.Request) -> web.Response:
    """Handle incoming PagerDuty webhook events (V3 format).

    NOTE: Production deployments should verify the X-PagerDuty-Signature header
    to authenticate that requests originate from PagerDuty. See:
    https://developer.pagerduty.com/docs/db0fa8c8984fc-verifying-signatures
    """
    try:
        payload = await request.json()
    except json.JSONDecodeError:
        return web.Response(status=400, text="Invalid JSON")

    print("📥 Received PagerDuty webhook")

    # PagerDuty V3 webhook format
    event = payload.get("event", {})
    event_type = event.get("event_type", "")
    incident = event.get("data", {})

    print(f"   Event type: {event_type}")

    # Handle incident.triggered events
    if event_type == "incident.triggered":
        incident_id = incident.get("id", "unknown")
        title = incident.get("title", "No title")
        service_name = incident.get("service", {}).get("summary", "Unknown service")
        urgency = incident.get("urgency", "unknown")
        html_url = incident.get("html_url", "")

        # Format Slack message
        urgency_emoji = "🔴" if urgency == "high" else "🟡"
        slack_message = (
            f"{urgency_emoji} *PagerDuty Incident Triggered*\n\n"
            f"*Title:* {title}\n"
            f"*Service:* {service_name}\n"
            f"*Urgency:* {urgency}\n"
            f"*ID:* `{incident_id}`\n"
            f"*Link:* {html_url}"
        )

        # Post to Slack channel
        if slack_client:
            try:
                await slack_client.chat_postMessage(
                    channel=SLACK_INCIDENT_CHANNEL,
                    text=slack_message,
                    unfurl_links=False,
                )
                print(f"📢 Posted PagerDuty incident to Slack: {incident_id}")
            except Exception as e:
                print(f"❌ Failed to post to Slack: {e}")
        else:
            print("❌ Slack client not initialized")
    elif event_type == "incident.resolved":
        incident_id = incident.get("id", "unknown")
        title = incident.get("title", "No title")
        html_url = incident.get("html_url", "")

        # Fetch full incident details from PagerDuty API to get accurate timestamps
        duration_str = "Unknown"
        resolution = ""
        if PAGERDUTY_API_KEY and incident_id != "unknown":
            try:
                async with ClientSession() as session:
                    async with session.get(
                        f"https://api.pagerduty.com/incidents/{incident_id}",
                        headers={
                            "Authorization": f"Token token={PAGERDUTY_API_KEY}",
                            "Content-Type": "application/json",
                        },
                    ) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            full_incident = data.get("incident", {})
                            created_at = full_incident.get("created_at", "")
                            resolved_at = full_incident.get("last_status_change_at", "")
                            resolution = full_incident.get("resolution", "") or ""

                            if created_at and resolved_at:
                                from datetime import datetime

                                created = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                                resolved = datetime.fromisoformat(
                                    resolved_at.replace("Z", "+00:00")
                                )
                                duration = resolved - created
                                total_minutes = int(duration.total_seconds() / 60)
                                if total_minutes < 60:
                                    duration_str = f"{total_minutes} minutes"
                                else:
                                    hours = total_minutes // 60
                                    minutes = total_minutes % 60
                                    duration_str = f"{hours}h {minutes}m"
            except Exception as e:
                print(f"⚠️ Could not fetch incident details: {e}")

        # Get root cause from resolution note
        root_cause = resolution if resolution else "See post-mortem for details"

        # Check for pending post-mortem URL (created before resolving)
        global pending_postmortem_url
        if pending_postmortem_url:
            print(f"📝 Including post-mortem URL in resolved message: {pending_postmortem_url}")
            postmortem_value = pending_postmortem_url
            pending_postmortem_url = ""
        else:
            postmortem_value = "_Pending_"

        slack_message = (
            f"✅ *PagerDuty Incident Resolved*\n\n"
            f"*Title:* {title}\n"
            f"*Root Cause:* {root_cause}\n"
            f"*Duration:* {duration_str}\n"
            f"*Link:* {html_url}\n"
            f"*Post-mortem:* {postmortem_value}"
        )

        # Post to Slack channel
        if slack_client:
            try:
                await slack_client.chat_postMessage(
                    channel=SLACK_INCIDENT_CHANNEL,
                    text=slack_message,
                    unfurl_links=False,
                )
                print(f"📢 Posted PagerDuty resolution to Slack: {incident_id}")
            except Exception as e:
                print(f"❌ Failed to post to Slack: {e}")
        else:
            print("❌ Slack client not initialized")
    else:
        print(f"   Ignoring event type: {event_type}")

    return web.Response(status=200, text="OK")


async def handle_health(request: web.Request) -> web.Response:
    """Health check endpoint."""
    return web.Response(status=200, text="OK")


SYSTEM_PROMPT = """You are an expert SRE incident response bot deployed
in Slack. Your job is to investigate production incidents quickly and
thoroughly.

## Your Investigation Approach

1. Start with get_service_health - Get a quick overview of all services
2. Drill into error rates - Check which services have elevated errors
3. Check latency - High latency often precedes errors
4. Investigate resources - Check DB connections, CPU, memory
5. Correlate and conclude - Connect symptoms to root cause

Note: The api-server has baseline error noise
(~0.1-0.2 errors/sec). Focus on significant spikes above
this level.

## Available Tools

*Investigation Tools:*
- mcp__sre__get_service_health: Quick health summary across all services
- mcp__sre__query_metrics: Run any PromQL query against Prometheus
- mcp__sre__list_metrics: Discover available metric names
- mcp__sre__get_logs: Fetch recent application logs from services
- mcp__sre__get_alerts: Get currently firing alerts from AlertManager
- mcp__sre__get_recent_deployments: List recent deployments to correlate with incidents
- mcp__sre__execute_runbook: Execute documented runbooks for known incident types

*PagerDuty Tools:*
- mcp__sre__pagerduty_list_incidents: Check for existing
incidents before creating new ones
- mcp__sre__pagerduty_create_incident: Create a new incident to page oncall
- mcp__sre__pagerduty_update_incident: Acknowledge or resolve incidents
- mcp__sre__pagerduty_get_incident: Get details of a specific incident

*Confluence Tools:*
- mcp__sre__confluence_create_postmortem: Create a post-mortem page
- mcp__sre__confluence_get_page: Retrieve an existing post-mortem
- mcp__sre__confluence_list_postmortems: Search for similar past incidents

## Your Capabilities

You have full access to remediate issues, including:
- Database management (connection pools, kill queries, tune settings)
- Kubernetes/infrastructure (restart pods, scale deployments, adjust resources)
- Core monorepo (deploy hotfixes, rollback changes, feature flags)
- Configuration management (update env vars, secrets, limits)

## Communication Style

You're chatting in Slack. Be natural and conversational:
- Concise: Get to the point quickly
- Clear: Use specific numbers and service names
- Helpful: Offer to take action when appropriate
- Natural: Respond appropriately to what the user asks -
don't force a rigid structure

For investigations, share your findings and offer
remediation options. *Always wait for explicit user
confirmation before executing any remediation action.*
For simple requests (like creating a PagerDuty incident),
just do it and confirm.

## PagerDuty Integration

You can create and manage PagerDuty incidents:

**Direct Incident Creation:**
When a user explicitly asks you to create a PagerDuty
incident (e.g., "create a PagerDuty incident",
"page oncall", "open an incident"),
do NOT investigate first. Simply:
1. Use pagerduty_create_incident immediately with the context they provided
2. Confirm the incident was created with the incident ID and URL
3. Keep it brief - no investigation needed

**During Investigations:**
1. Check pagerduty_list_incidents first to see if an incident already exists
2. If critical issue found, offer to create a PagerDuty incident
3. After remediation, offer to resolve the PagerDuty incident

## Post-Incident Workflow

After you have applied the fix and verified the issue
is resolved:
1. *Offer to close out the incident* - Ask the user:
"The fix has been applied and verified. Would you like
me to resolve the PagerDuty incident and create a
post-mortem?"
2. *Wait for user confirmation* - Do NOT proceed until
the user confirms (e.g., "yes", "go ahead", "do it")
3. Once confirmed, perform actions IN THIS ORDER:
   a. FIRST create the post-mortem using
   confluence_create_postmortem
   b. Share the Confluence URL with the channel
   c. THEN resolve the PagerDuty incident using
   pagerduty_update_incident with status "resolved"

The post-mortem should document:
- *Summary:* Brief description of what happened
- *Root Cause:* The identified cause from your investigation
- *Resolution:* What was done to fix it
- *Duration:* How long the incident lasted
- *Action Items:* Follow-up tasks to prevent recurrence

IMPORTANT: Always create the post-mortem BEFORE resolving
the PagerDuty incident. This ensures the post-mortem link
is available when the incident resolved notification is
sent.

## Slack Formatting Rules

You MUST use Slack's mrkdwn format, NOT standard Markdown:
- Bold: Use *bold* (single asterisks), NOT **bold**
- Italic: Use _italic_ (underscores)
- Strikethrough: Use ~strikethrough~
- Code: Use `code` for inline, ```code``` for blocks
- Links: Use <URL|text>
- NO HEADERS: Slack does not support # headers. Use *Bold Text* on its own line instead.
- Lists: Use bullet points (•) or dashes (-) or numbers (1.)

Be thorough but efficient. Always explain your reasoning.
"""


def convert_markdown_to_slack(text: str) -> str:
    """Convert standard Markdown to Slack mrkdwn format."""
    # Remove ### headers - replace with bold text
    text = re.sub(r"^###\s*(.+)$", r"*\1*", text, flags=re.MULTILINE)
    text = re.sub(r"^##\s*(.+)$", r"*\1*", text, flags=re.MULTILINE)
    text = re.sub(r"^#\s*(.+)$", r"*\1*", text, flags=re.MULTILINE)

    # Convert **bold** to *bold* (but not inside code blocks)
    # This is a simplified conversion - handles most cases
    text = re.sub(r"\*\*([^*]+)\*\*", r"*\1*", text)

    return text


async def process_investigation(
    incident_text: str,
    channel: str,
    thread_ts: str,
    say,
    is_followup: bool = False,
    is_investigation: bool = False,
):
    """Process the investigation in the background, streaming output to Slack.

    Args:
        incident_text: The incident description or follow-up request
        channel: Slack channel ID
        thread_ts: Thread timestamp for replies
        say: Slack say function
        is_followup: If True, skip verbose tool messages
            (for post-mortems, confirmations, etc.)
        is_investigation: If True, this is an actual
            investigation (show completion message)
    """
    # Get the Python executable path (use the venv python)
    python_path = sys.executable

    # Configure the agent with subprocess-based MCP server
    # This avoids the SDK MCP race condition bug
    options = ClaudeAgentOptions(
        system_prompt=SYSTEM_PROMPT,
        mcp_servers={
            "sre": {
                "command": python_path,
                "args": [str(MCP_SERVER_PATH)],
            }
        },
        allowed_tools=[
            # Investigation tools
            "mcp__sre__query_metrics",
            "mcp__sre__list_metrics",
            "mcp__sre__get_service_health",
            "mcp__sre__get_logs",
            "mcp__sre__get_alerts",
            "mcp__sre__get_recent_deployments",
            "mcp__sre__execute_runbook",
            # PagerDuty tools
            "mcp__sre__pagerduty_create_incident",
            "mcp__sre__pagerduty_update_incident",
            "mcp__sre__pagerduty_get_incident",
            "mcp__sre__pagerduty_list_incidents",
            # Confluence tools
            "mcp__sre__confluence_create_postmortem",
            "mcp__sre__confluence_get_page",
            "mcp__sre__confluence_list_postmortems",
            # Remediation tools
            "mcp__sre__read_config_file",
            "mcp__sre__edit_config_file",
            "mcp__sre__run_shell_command",
            "mcp__sre__get_container_logs",
        ],
        permission_mode="acceptEdits",
        model="claude-opus-5-5",
    )

    # Stream responses to Slack as they arrive
    # Track last tool to avoid duplicate "Checking X..." messages
    last_tool_posted = None

    try:
        async for message in query(prompt=incident_text, options=options):
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock) and block.text.strip():
                        # Post text blocks immediately as they arrive
                        # Convert any standard Markdown to Slack mrkdwn format
                        text = convert_markdown_to_slack(block.text.strip())

                        # Check for Confluence post-mortem URL
                        # and store it for the webhook
                        confluence_match = re.search(
                            r"(https://[^/]+\.atlassian"
                            r"\.net/wiki/[^\s<>]+)",
                            block.text,
                        )
                        if confluence_match:
                            global pending_postmortem_url
                            pending_postmortem_url = confluence_match.group(1)
                            print(f"📝 Stored post-mortem URL: {pending_postmortem_url}")

                        # Reset tool tracking when we get actual content
                        last_tool_posted = None
                        # Split long messages to respect Slack's 4000 char limit
                        if len(text) > 3900:
                            chunks = [text[i : i + 3900] for i in range(0, len(text), 3900)]
                            for chunk in chunks:
                                await say(text=chunk, thread_ts=thread_ts)
                                await asyncio.sleep(0.3)
                        else:
                            await say(text=text, thread_ts=thread_ts)
                            await asyncio.sleep(0.3)
                    elif isinstance(block, ToolUseBlock):
                        # Show which tool is being used, but skip consecutive duplicates
                        # Skip tool messages for follow-up actions (post-mortems, etc.)
                        if not is_followup:
                            tool_name = block.name.replace("mcp__sre__", "")
                            if tool_name != last_tool_posted:
                                await say(
                                    text=f"🔧 *Checking {tool_name}...*",
                                    thread_ts=thread_ts,
                                )
                                await asyncio.sleep(0.2)
                                last_tool_posted = tool_name
            elif isinstance(message, ResultMessage):
                if message.is_error:
                    await say(text=f"❌ Error: {message.result}", thread_ts=thread_ts)
                # No completion message - let the response stand on its own

    except Exception as e:
        await say(text=f"❌ Failed: {str(e)}", thread_ts=thread_ts)
        raise


@app.event("app_mention")
async def handle_mention(event, say, client):
    """Handle @mentions in Slack channels."""

    channel = event["channel"]
    thread_ts = event.get("thread_ts", event["ts"])
    incident_text = event["text"]

    # Track this thread so we respond to follow-ups without needing @mention.
    # Evict oldest entries to prevent unbounded growth in long-running bots.
    if len(active_threads) >= MAX_ACTIVE_THREADS:
        for old_key in list(active_threads)[: len(active_threads) // 2]:
            del active_threads[old_key]
    active_threads[thread_ts] = channel

    # Remove the bot mention from the text
    incident_text = re.sub(r"<@[A-Z0-9]+>\s*", "", incident_text).strip()

    if not incident_text:
        await say(
            text=(
                "👋 I'm the SRE bot! Mention me with an"
                " incident description and I'll"
                " investigate.\n\nExample:"
                " `@SRE Bot API errors are spiking`"
            ),
            thread_ts=thread_ts,
        )
        return

    # If this is a reply in a thread, fetch thread history for context
    thread_context = ""
    if event.get("thread_ts") and client:
        try:
            result = await client.conversations_replies(
                channel=channel, ts=event["thread_ts"], limit=50
            )
            messages = result.get("messages", [])
            if len(messages) > 1:  # More than just the current message
                thread_context = "\n\n--- PREVIOUS CONVERSATION IN THIS THREAD ---\n"
                for msg in messages[:-1]:  # Exclude the current message
                    sender = "Bot" if msg.get("bot_id") else "User"
                    text = msg.get("text", "")[:2000]  # Limit each message
                    thread_context += f"\n{sender}: {text}\n"
                thread_context += "\n--- END OF PREVIOUS CONVERSATION ---\n\n"
        except Exception as e:
            print(f"Could not fetch thread history: {e}")

    # Combine context with current request
    full_prompt = (
        thread_context + "Current request: " + incident_text if thread_context else incident_text
    )

    # Detect if this is a short confirmation
    # (skip tool messages for brief yes/no responses)
    lower_text = incident_text.lower().strip()
    is_followup = len(lower_text) < 30 and any(
        keyword in lower_text
        for keyword in [
            "yes",
            "proceed",
            "go ahead",
            "do it",
            "approve",
            "confirmed",
            "sounds good",
            "ok",
            "sure",
        ]
    )

    # Schedule the task as a background task so handler returns quickly
    asyncio.create_task(process_investigation(full_prompt, channel, thread_ts, say, is_followup))


@app.event("message")
async def handle_message(event, say, client):
    """Handle direct messages and follow-ups in active threads."""
    # Ignore bot messages
    if event.get("bot_id"):
        return

    # Ignore message_changed events (edits)
    if event.get("subtype") == "message_changed":
        return

    channel = event.get("channel", "")
    thread_ts = event.get("thread_ts")
    text = event.get("text", "").strip()

    if not text:
        return

    # Check if this is a DM
    is_dm = channel.startswith("D")

    # Check if this is a follow-up in an active thread
    is_active_thread = thread_ts and thread_ts in active_threads

    if is_dm or is_active_thread:
        # Pass to handle_mention (it will handle thread tracking)
        await handle_mention(
            {
                "channel": channel,
                "ts": event["ts"],
                "thread_ts": thread_ts,
                "text": text,
                "user": event.get("user"),
            },
            say,
            client,
        )


async def start_webhook_server():
    """Start the webhook server for PagerDuty events."""
    webhook_app = web.Application()
    webhook_app.router.add_post("/webhooks/pagerduty", handle_pagerduty_webhook)
    webhook_app.router.add_get("/health", handle_health)

    runner = web.AppRunner(webhook_app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", WEBHOOK_PORT)  # noqa: S104 - webhook listener must be reachable
    await site.start()
    print(f"🌐 Webhook server listening on http://0.0.0.0:{WEBHOOK_PORT}")
    print(f"   PagerDuty webhook URL: http://<your-host>:{WEBHOOK_PORT}/webhooks/pagerduty")

    # Keep the server running
    while True:
        await asyncio.sleep(3600)


async def main():
    """Start the Slack bot and webhook server."""
    global slack_client

    print("=" * 50)
    print("🤖 SRE Bot - Slack Mode (Claude Agent SDK)")
    print("=" * 50)
    print("Bot is starting...")
    print(f"Webhook server will listen on port {WEBHOOK_PORT}")
    print(f"PagerDuty alerts will post to: {SLACK_INCIDENT_CHANNEL}")
    print("Mention @SRE Bot in any channel to investigate")
    print("Press Ctrl+C to stop")
    print("=" * 50)

    # Initialize Slack client for webhook handler
    from slack_sdk.web.async_client import AsyncWebClient

    slack_client = AsyncWebClient(token=os.environ["SLACK_BOT_TOKEN"])

    # Start both the Slack bot and webhook server
    handler = AsyncSocketModeHandler(app, os.environ["SLACK_APP_TOKEN"])

    await asyncio.gather(handler.start_async(), start_webhook_server())


if __name__ == "__main__":
    asyncio.run(main())
