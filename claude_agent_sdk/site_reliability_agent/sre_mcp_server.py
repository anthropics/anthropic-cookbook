#!/usr/bin/env python3
"""
SRE MCP Server - Subprocess-based MCP server for incident investigation.

This server runs as a separate process and communicates via stdio using
the MCP JSON-RPC protocol. This avoids the SDK MCP race condition bug.

Usage:
    python sre_mcp_server.py

The server implements:
- query_metrics: Run PromQL queries against Prometheus
- list_metrics: List available metric names
- get_service_health: Get a comprehensive health summary
"""

import asyncio
import base64
import html
import json
import os
import shlex
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx

# Load environment variables
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

PROMETHEUS_URL = "http://localhost:9090"

# PagerDuty configuration
PAGERDUTY_API_KEY = os.getenv("PAGERDUTY_API_KEY")
PAGERDUTY_SERVICE_ID = os.getenv("PAGERDUTY_SERVICE_ID")
PAGERDUTY_FROM_EMAIL = os.getenv("PAGERDUTY_FROM_EMAIL")
PAGERDUTY_BASE_URL = "https://api.pagerduty.com"

# Confluence configuration
CONFLUENCE_BASE_URL = os.getenv("CONFLUENCE_BASE_URL")
CONFLUENCE_API_TOKEN = os.getenv("CONFLUENCE_API_TOKEN")
CONFLUENCE_USER_EMAIL = os.getenv("CONFLUENCE_USER_EMAIL")
CONFLUENCE_SPACE_KEY = os.getenv("CONFLUENCE_SPACE_KEY", "SRE")
CONFLUENCE_PARENT_PAGE_ID = os.getenv("CONFLUENCE_PARENT_PAGE_ID")

# Track when the server started (for incident simulation timing)
START_TIME = time.time()

# Tool definitions for MCP
TOOLS = [
    {
        "name": "query_metrics",
        "description": """Query Prometheus metrics using PromQL.

Use this to investigate incidents by checking error rates, latency, and resource usage.

Common investigation queries:
- Error rate by service: rate(http_requests_total{status="500"}[1m])
- Error ratio:
  sum(rate(http_requests_total{status="500"}[1m])) by (service)
  / sum(rate(http_requests_total[1m])) by (service)
- DB connections: db_connections_active or db_connections_waiting
- Latency P99: histogram_quantile(0.99,
  rate(http_request_duration_milliseconds_bucket[1m]))
- CPU usage: container_cpu_usage_ratio
- Memory usage: container_memory_usage_ratio

Investigation workflow:
1. Start with error rates to identify affected services
2. Check latency to see if it's a slowdown vs failures
3. Look at db_connections if you see timeout-related errors
4. Check CPU/memory if services are resource-constrained""",
        "inputSchema": {
            "type": "object",
            "properties": {
                "promql": {
                    "type": "string",
                    "description": "The PromQL query to execute",
                }
            },
            "required": ["promql"],
        },
    },
    {
        "name": "list_metrics",
        "description": """List all available metric names in Prometheus.

Use this first if you're unsure what metrics exist.
Returns metric names grouped by category for easier discovery.""",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_service_health",
        "description": """Quick health check across all services.

Returns a summary of:
- Error rates per service
- Current latency (P99)
- Database connection status
- Service up/down status

Use this as a starting point for incident investigation to quickly
identify which services are affected.""",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_logs",
        "description": """Fetch recent application logs from services.

Returns the most recent log entries for a specified service.
Useful for investigating errors, timeouts, and application behavior.

Available services: api-server, payment-svc, auth-svc, postgres""",
        "inputSchema": {
            "type": "object",
            "properties": {
                "service": {
                    "type": "string",
                    "description": (
                        "The service to fetch logs from"
                        " (api-server, payment-svc,"
                        " auth-svc, postgres)"
                    ),
                },
                "level": {
                    "type": "string",
                    "description": (
                        "Filter by log level: all,"
                        " error, warn, info"
                        " (default: all)"
                    ),
                    "enum": ["all", "error", "warn", "info"],
                },
                "lines": {
                    "type": "integer",
                    "description": (
                        "Number of log lines to return"
                        " (default: 20, max: 100)"
                    ),
                },
            },
            "required": ["service"],
        },
    },
    {
        "name": "get_alerts",
        "description": """Get currently firing and pending alerts from AlertManager.

Returns all active alerts with their severity, duration, and details.
Use this to understand what automated monitoring has already detected.""",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_recent_deployments",
        "description": """List recent deployments across all services.

Returns deployment history with timestamps, commit SHAs, and authors.
Useful for correlating incidents with recent changes.""",
        "inputSchema": {
            "type": "object",
            "properties": {
                "service": {
                    "type": "string",
                    "description": "Filter to a specific service (optional)",
                }
            },
            "required": [],
        },
    },
    {
        "name": "execute_runbook",
        "description": """Execute a documented runbook for a known issue type.

Runbooks provide structured investigation and
remediation procedures for common incidents.
Use this when you've identified a specific type of issue and want to follow the standard
operating procedure.

Available runbooks:
- database_connection_exhaustion: For DB pool exhaustion, "too many connections" errors
- high_latency_cascade: For P99 latency spikes cascading across services
- elevated_error_rates: For 5xx error rate increases

Each runbook has two phases:
- investigate: Returns diagnostic steps and queries to run
- remediate: Returns remediation actions (requires investigation first)

Always run the investigate phase first to confirm the issue before remediation.""",
        "inputSchema": {
            "type": "object",
            "properties": {
                "runbook": {
                    "type": "string",
                    "enum": [
                        "database_connection_exhaustion",
                        "high_latency_cascade",
                        "elevated_error_rates",
                    ],
                    "description": "Which runbook to execute",
                },
                "phase": {
                    "type": "string",
                    "enum": ["investigate", "remediate"],
                    "description": (
                        "Phase to execute:"
                        " 'investigate' for diagnosis,"
                        " 'remediate' for fixes"
                    ),
                },
            },
            "required": ["runbook", "phase"],
        },
    },
    {
        "name": "read_config_file",
        "description": """Read a configuration file from the project.

Use this to inspect current configuration values, especially when investigating
configuration-related incidents.

Common files:
- config/api-server.env: API server configuration (DB_POOL_SIZE, etc.)
- config/api-server.env.backup: Known good configuration for reference""",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": (
                        "Path to the config file"
                        " relative to project root"
                        " (e.g., 'config/api-server.env')"
                    ),
                }
            },
            "required": ["path"],
        },
    },
    {
        "name": "edit_config_file",
        "description": """Edit a configuration file by replacing a value.

Use this to fix configuration issues during incident remediation.
The edit is performed by finding and replacing the old value with the new value.

Example: To fix DB_POOL_SIZE from 1 to 20:
- path: config/api-server.env
- old_value: DB_POOL_SIZE=1
- new_value: DB_POOL_SIZE=20""",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the config file relative to project root",
                },
                "old_value": {
                    "type": "string",
                    "description": "The exact text to find and replace",
                },
                "new_value": {
                    "type": "string",
                    "description": "The new text to replace it with",
                },
            },
            "required": ["path", "old_value", "new_value"],
        },
    },
    {
        "name": "run_shell_command",
        "description": """Run a shell command for remediation actions.

Use this to execute commands like restarting services, checking container status, etc.

Common commands:
- docker-compose -f config/docker-compose.yml up -d api-server
  (REQUIRED after config changes — recreates container)
- docker-compose -f config/docker-compose.yml ps
- docker-compose -f config/docker-compose.yml logs \
  api-server --tail=50

IMPORTANT: After editing config files, you MUST
use 'up -d' (not 'restart') to apply changes.
'restart' does NOT reload env files — only 'up -d'
recreates the container with new config.""",
        "inputSchema": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The shell command to execute",
                }
            },
            "required": ["command"],
        },
    },
    {
        "name": "get_container_logs",
        "description": """Get logs from a Docker container.

Use this to investigate application errors and behavior.
Returns the most recent log lines from the specified container.

Available containers: api-server, postgres, traffic-generator""",
        "inputSchema": {
            "type": "object",
            "properties": {
                "container": {
                    "type": "string",
                    "description": (
                        "Container name (api-server,"
                        " postgres, traffic-generator)"
                    ),
                },
                "lines": {
                    "type": "integer",
                    "description": (
                        "Number of log lines to return"
                        " (default: 50, max: 200)"
                    ),
                },
            },
            "required": ["container"],
        },
    },
    {
        "name": "write_postmortem",
        "description": """Write an incident post-mortem report to
the postmortems/ directory.

Use this after resolving an incident to document what happened, the root cause,
the remediation steps taken, and follow-up action items.

The report is saved as a markdown file with a timestamp-based filename.""",
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": (
                        "Incident title "
                        "(e.g., 'DB Connection Pool Exhaustion')"
                    ),
                },
                "summary": {
                    "type": "string",
                    "description": "Brief summary of the incident",
                },
                "root_cause": {"type": "string", "description": "Root cause analysis"},
                "timeline": {"type": "string", "description": "Timeline of events"},
                "remediation": {
                    "type": "string",
                    "description": "Steps taken to fix the issue",
                },
                "action_items": {
                    "type": "string",
                    "description": "Follow-up action items to prevent recurrence",
                },
            },
            "required": ["title", "summary", "root_cause"],
        },
    },
]

# PagerDuty tools — only registered when PAGERDUTY_API_KEY is set
if PAGERDUTY_API_KEY:
    TOOLS.extend(
        [
            {
                "name": "pagerduty_create_incident",
                "description": """Create a new PagerDuty incident.
    Use this when an investigation reveals a critical
    issue requiring immediate oncall attention.
    The incident will page the oncall for the specified service.
    Returns the incident ID and URL for tracking.""",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "title": {
                            "type": "string",
                            "description": (
                                "Brief incident title"
                                " (e.g., 'API Server -"
                                " DB Connection Pool Exhaustion')"
                            ),
                        },
                        "description": {
                            "type": "string",
                            "description": (
                                "Detailed description of the incident"
                                " including symptoms and initial findings"
                            ),
                        },
                        "urgency": {
                            "type": "string",
                            "enum": ["high", "low"],
                            "description": (
                                "Incident urgency:"
                                " 'high' for immediate page," 
                                " 'low' for non-urgent"
                            ),
                        },
                        "service_id": {
                            "type": "string",
                            "description": (
                                "PagerDuty service ID"
                                " (optional, uses default if not specified)"
                            ),
                        },
                    },
                    "required": ["title", "description"],
                },
            },
            {
                "name": "pagerduty_update_incident",
                "description": """Update a PagerDuty incident status.
    Use to acknowledge or resolve incidents during remediation.
    Can also add notes to document investigation progress.""",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "incident_id": {
                            "type": "string",
                            "description": "The PagerDuty incident ID to update",
                        },
                        "status": {
                            "type": "string",
                            "enum": ["acknowledged", "resolved"],
                            "description": "New status for the incident",
                        },
                        "resolution_note": {
                            "type": "string",
                            "description": (
                                "Note explaining the resolution"
                                " (required for 'resolved' status)"
                            ),
                        },
                    },
                    "required": ["incident_id", "status"],
                },
            },
            {
                "name": "pagerduty_get_incident",
                "description": """Get details of a specific PagerDuty incident.
    Returns incident status, assignments, timeline, and notes.
    Use to check current state before taking action.""",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "incident_id": {
                            "type": "string",
                            "description": "The PagerDuty incident ID",
                        }
                    },
                    "required": ["incident_id"],
                },
            },
            {
                "name": "pagerduty_list_incidents",
                "description": """List current PagerDuty incidents.
    Returns triggered and acknowledged incidents across all services.
    Use at start of investigation to see if incident already exists.""",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "status": {
                            "type": "string",
                            "enum": ["triggered", "acknowledged", "resolved", "all"],
                            "description": (
                                "Filter by status (default: 'all'"
                                " for triggered + acknowledged)"
                            ),
                        },
                        "service_id": {
                            "type": "string",
                            "description": "Filter to a specific service (optional)",
                        },
                    },
                    "required": [],
                },
            },
        ]
    )

# Confluence tools — only registered when
# CONFLUENCE_BASE_URL and CONFLUENCE_API_TOKEN are set
if CONFLUENCE_BASE_URL and CONFLUENCE_API_TOKEN:
    TOOLS.extend(
        [
            {
                "name": "confluence_create_postmortem",
                "description": """Create a post-mortem page in Confluence.
    IMPORTANT: Only call this AFTER the user confirms they want to publish.
    The bot should OFFER to create a post-mortem and wait for user confirmation.
    Workflow:
    1. Bot offers: "I can create a post-mortem page"
       " in Confluence. Reply 'yes' to proceed."
    2. User replies: "yes"
    3. Bot calls this tool with incident details
    The page is created from a template with sections for:
    - Incident Summary
    - Timeline
    - Root Cause
    - Impact
    - Remediation Steps
    - Action Items""",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "title": {
                            "type": "string",
                            "description": (
                                "Page title (e.g., 'Post-Mortem:"
                                " 2025-01-15 API Server Outage')"
                            ),
                        },
                        "incident_summary": {
                            "type": "string",
                            "description": "Brief summary of what happened",
                        },
                        "timeline": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": (
                                "List of timestamped events"
                                " (e.g., ['14:23 - Alert fired'"
                                ", '14:25 - Investigation"
                                " started'])"
                            ),
                        },
                        "root_cause": {
                            "type": "string",
                            "description": "Technical explanation of the root cause",
                        },
                        "impact": {
                            "type": "string",
                            "description": "Description of user/business impact",
                        },
                        "remediation_steps": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of actions taken to resolve",
                        },
                        "action_items": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "task": {"type": "string"},
                                    "owner": {"type": "string"},
                                    "due_date": {"type": "string"},
                                },
                            },
                            "description": "Follow-up action items with owners",
                        },
                        "pagerduty_incident_id": {
                            "type": "string",
                            "description": (
                                "Associated PagerDuty incident"
                                " ID (optional, for linking)"
                            ),
                        },
                    },
                    "required": ["title", "incident_summary", "root_cause"],
                },
            },
            {
                "name": "confluence_get_page",
                "description": """Get a Confluence page by ID or title.
    Use to retrieve existing post-mortems or check if
    one already exists for an incident.""",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "page_id": {
                            "type": "string",
                            "description": "Confluence page ID",
                        },
                        "title": {
                            "type": "string",
                            "description": (
                                "Search by page title"
                                " (alternative to page_id)"
                            ),
                        },
                    },
                    "required": [],
                },
            },
            {
                "name": "confluence_list_postmortems",
                "description": """List recent post-mortem pages in the SRE space.
    Returns post-mortems from the last N days for reference during investigation.
    Useful to check for similar past incidents.""",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "days": {
                            "type": "integer",
                            "description": "Look back N days (default: 30)",
                        },
                        "search_term": {
                            "type": "string",
                            "description": (
                                "Search post-mortems containing"
                                " this term (e.g., 'database'"
                                ", 'api-server')"
                            ),
                        },
                    },
                    "required": [],
                },
            },
        ]
    )

# Project root directory (for config file operations)
PROJECT_ROOT = Path(__file__).resolve().parent


async def query_metrics(promql: str) -> dict[str, Any]:
    """Query Prometheus with a PromQL expression."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{PROMETHEUS_URL}/api/v1/query",
                params={"query": promql},
                timeout=10.0,
            )
            response.raise_for_status()
            data = response.json()

        if data["status"] != "success":
            return {
                "content": [
                    {
                        "type": "text",
                        "text": (
                            f"Query failed: {data.get('error', 'Unknown error')}"
                            f"\nQuery: {promql}"
                        ),
                    }
                ],
                "isError": True,
            }

        results = data["data"]["result"]

        if not results:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": (
                            f"No data returned for query: {promql}\n"
                            "Check if metric name is correct"
                            " or try a broader time range."
                        ),
                    }
                ]
            }

        # Format results for readability
        formatted_lines = [f"Query: {promql}", f"Results ({len(results)} series):", ""]

        for r in results:
            labels = r.get("metric", {})
            if "value" in r:
                timestamp, value = r["value"]
                label_str = ", ".join(
                    f"{k}={v}" for k, v in labels.items() if k != "__name__"
                )
                formatted_lines.append(f"  {label_str or 'value'}: {value}")
            elif "values" in r:
                label_str = ", ".join(
                    f"{k}={v}" for k, v in labels.items() if k != "__name__"
                )
                latest_value = r["values"][-1][1] if r["values"] else "N/A"
                formatted_lines.append(
                    f"  {label_str or 'value'}: {latest_value} (latest)"
                )

        return {"content": [{"type": "text", "text": "\n".join(formatted_lines)}]}

    except httpx.ConnectError:
        return {
            "content": [
                {
                    "type": "text",
                    "text": (
                        "Cannot connect to Prometheus"
                        " at localhost:9090.\n"
                        "Make sure to run: docker-compose up"
                    ),
                }
            ],
            "isError": True,
        }
    except Exception as e:
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Error executing query: {str(e)}\nQuery: {promql}",
                }
            ],
            "isError": True,
        }


async def list_metrics() -> dict[str, Any]:
    """List available metrics in Prometheus."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{PROMETHEUS_URL}/api/v1/label/__name__/values", timeout=10.0
            )
            response.raise_for_status()
            data = response.json()

        metrics = data.get("data", [])

        # Group metrics by prefix for easier reading
        grouped = {
            "http": [m for m in metrics if m.startswith("http_")],
            "db": [m for m in metrics if m.startswith("db_")],
            "container": [m for m in metrics if m.startswith("container_")],
            "other": [
                m
                for m in metrics
                if not any(
                    m.startswith(p)
                    for p in ["http_", "db_", "container_", "go_", "promhttp_", "up"]
                )
            ],
        }

        lines = [f"Available metrics ({len(metrics)} total):", ""]
        for category, metric_list in grouped.items():
            if metric_list:
                lines.append(f"{category.upper()}:")
                for m in metric_list:
                    lines.append(f"  - {m}")
                lines.append("")

        lines.append("Use query_metrics() with these metric names to get values.")

        return {"content": [{"type": "text", "text": "\n".join(lines)}]}

    except httpx.ConnectError:
        return {
            "content": [
                {"type": "text", "text": "Cannot connect to Prometheus. Is it running?"}
            ],
            "isError": True,
        }
    except Exception as e:
        return {
            "content": [{"type": "text", "text": f"Error listing metrics: {str(e)}"}],
            "isError": True,
        }


async def get_service_health() -> dict[str, Any]:
    """Get a comprehensive health summary across all services."""
    health_lines = ["=== Service Health Summary ===", ""]
    issues = []

    async with httpx.AsyncClient() as client:
        # Check error rates
        try:
            response = await client.get(
                f"{PROMETHEUS_URL}/api/v1/query",
                params={
                    "query": (
                        'sum(rate(http_requests_total'
                        '{status="500"}[1m]))'
                        ' by (service)'
                    )
                },
                timeout=10.0,
            )
            if response.status_code == 200:
                data = response.json()
                if data["status"] == "success" and data["data"]["result"]:
                    health_lines.append("ERROR RATES (errors/sec):")
                    for r in data["data"]["result"]:
                        service = r["metric"].get("service", "unknown")
                        rate = float(r["value"][1])
                        status = (
                            "[CRITICAL]"
                            if rate > 5
                            else "[WARNING]"
                            if rate > 1
                            else "[OK]"
                        )
                        health_lines.append(f"  {status} {service}: {rate:.2f}/sec")
                        if rate > 5:
                            issues.append(
                                f"High error rate on {service}: {rate:.1f}/sec"
                            )
                    health_lines.append("")
        except Exception as e:
            health_lines.append(f"ERROR RATES: unable to query ({e})")
            health_lines.append("")

        # Check latency
        try:
            response = await client.get(
                f"{PROMETHEUS_URL}/api/v1/query",
                params={
                    "query": (
                        "histogram_quantile(0.99,"
                        " rate(http_request_duration"
                        "_milliseconds_bucket[1m]))"
                    )
                },
                timeout=10.0,
            )
            if response.status_code == 200:
                data = response.json()
                if data["status"] == "success" and data["data"]["result"]:
                    health_lines.append("LATENCY P99:")
                    for r in data["data"]["result"]:
                        service = r["metric"].get("service", "unknown")
                        latency = float(r["value"][1])
                        status = (
                            "[CRITICAL]"
                            if latency > 1000
                            else "[WARNING]"
                            if latency > 500
                            else "[OK]"
                        )
                        health_lines.append(f"  {status} {service}: {latency:.0f}ms")
                        if latency > 1000:
                            issues.append(f"High latency on {service}: {latency:.0f}ms")
                    health_lines.append("")
        except Exception as e:
            health_lines.append(f"LATENCY P99: unable to query ({e})")
            health_lines.append("")

        # Check DB connections
        try:
            response = await client.get(
                f"{PROMETHEUS_URL}/api/v1/query",
                params={"query": "db_connections_active"},
                timeout=10.0,
            )
            if response.status_code == 200:
                data = response.json()
                if data["status"] == "success" and data["data"]["result"]:
                    active = float(data["data"]["result"][0]["value"][1])
                    status = (
                        "[CRITICAL]"
                        if active > 90
                        else "[WARNING]"
                        if active > 70
                        else "[OK]"
                    )
                    health_lines.append("DATABASE CONNECTIONS:")
                    health_lines.append(f"  {status}: {active:.0f}/100 active")
                    if active > 90:
                        issues.append(
                            f"DB connection pool near exhaustion: {active:.0f}/100"
                        )
                    health_lines.append("")
        except Exception as e:
            health_lines.append(f"DATABASE CONNECTIONS: unable to query ({e})")
            health_lines.append("")

        # Check service up status
        try:
            response = await client.get(
                f"{PROMETHEUS_URL}/api/v1/query",
                params={"query": "up"},
                timeout=10.0,
            )
            if response.status_code == 200:
                data = response.json()
                if data["status"] == "success" and data["data"]["result"]:
                    health_lines.append("SERVICE STATUS:")
                    for r in data["data"]["result"]:
                        service = r["metric"].get(
                            "service", r["metric"].get("job", "unknown")
                        )
                        is_up = int(float(r["value"][1])) == 1
                        status = "[UP]" if is_up else "[DOWN]"
                        health_lines.append(f"  {status}: {service}")
                        if not is_up:
                            issues.append(f"Service down: {service}")
                    health_lines.append("")
        except Exception as e:
            health_lines.append(f"SERVICE STATUS: unable to query ({e})")
            health_lines.append("")

    # Add summary
    health_lines.append("=== SUMMARY ===")
    if issues:
        health_lines.append("ISSUES DETECTED:")
        for issue in issues:
            health_lines.append(f"  - {issue}")
    else:
        health_lines.append("All systems healthy")

    return {"content": [{"type": "text", "text": "\n".join(health_lines)}]}


async def get_logs(service: str, level: str = "all", lines: int = 20) -> dict[str, Any]:
    """Fetch real logs from Docker containers."""
    lines = min(lines, 100)  # Cap at 100

    # Map service names to container names
    service_to_container = {
        "api-server": "api-server",
        "user-svc": "api-server",  # user-svc runs in api-server container
        "payment-svc": "api-server",  # payment-svc runs in api-server container
        "auth-svc": "api-server",  # auth-svc runs in api-server container
        "postgres": "postgres",
    }

    container = service_to_container.get(service)
    if not container:
        return {
            "content": [
                {
                    "type": "text",
                    "text": (
                        f"Unknown service: {service}\n"
                        "Valid services: "
                        f"{', '.join(service_to_container.keys())}"
                    ),
                }
            ],
            "isError": True,
        }

    # Use get_container_logs to fetch real logs
    return await get_container_logs(container, lines)


async def get_alerts() -> dict[str, Any]:
    """Get currently firing alerts. Simulated — no AlertManager running in demo."""
    elapsed = time.time() - START_TIME
    incident_active = elapsed > 15

    alerts = []

    if incident_active:
        incident_duration = int(elapsed - 15)
        alerts = [
            {
                "status": "FIRING",
                "severity": "critical",
                "name": "HighErrorRate",
                "service": "api-server",
                "description": "Error rate is 23.4% (threshold: 5%)",
                "duration": f"{incident_duration}s",
            },
            {
                "status": "FIRING",
                "severity": "critical",
                "name": "DBConnectionPoolExhausted",
                "service": "postgres",
                "description": "Connection pool at 98/100 (threshold: 90%)",
                "duration": f"{incident_duration}s",
            },
            {
                "status": "FIRING",
                "severity": "warning",
                "name": "HighLatencyP99",
                "service": "api-server",
                "description": "P99 latency is 2847ms (threshold: 500ms)",
                "duration": f"{incident_duration - 5}s",
            },
            {
                "status": "PENDING",
                "severity": "warning",
                "name": "HighCPUUsage",
                "service": "api-server",
                "description": "CPU usage is 87% (threshold: 80%)",
                "duration": "pending for 45s",
            },
        ]
    else:
        # Healthy - no alerts or just resolved ones
        alerts = [
            {
                "status": "RESOLVED",
                "severity": "info",
                "name": "HighLatencyP99",
                "service": "payment-svc",
                "description": "P99 latency returned to normal",
                "duration": "resolved 12m ago",
            },
        ]

    lines = ["=== Active Alerts ===", ""]

    firing = [a for a in alerts if a["status"] == "FIRING"]
    pending = [a for a in alerts if a["status"] == "PENDING"]
    resolved = [a for a in alerts if a["status"] == "RESOLVED"]

    if firing:
        lines.append("🔴 FIRING:")
        for alert in firing:
            lines.append(
                f"  [{alert['severity'].upper()}] {alert['name']} ({alert['service']})"
            )
            lines.append(f"      {alert['description']}")
            lines.append(f"      Duration: {alert['duration']}")
            lines.append("")

    if pending:
        lines.append("🟡 PENDING:")
        for alert in pending:
            lines.append(
                f"  [{alert['severity'].upper()}] {alert['name']} ({alert['service']})"
            )
            lines.append(f"      {alert['description']}")
            lines.append(f"      {alert['duration']}")
            lines.append("")

    if resolved and not firing:
        lines.append("✅ RECENTLY RESOLVED:")
        for alert in resolved:
            lines.append(
                f"  {alert['name']} ({alert['service']}) - {alert['duration']}"
            )
            lines.append("")

    if not firing and not pending:
        lines.append("✅ No active alerts")

    return {"content": [{"type": "text", "text": "\n".join(lines)}]}


async def get_recent_deployments(service: str | None = None) -> dict[str, Any]:
    """Get recent deployments. Simulated — no deployment tracker running in demo."""
    elapsed = time.time() - START_TIME

    # Generate fake deployment times relative to now
    now = time.time()

    # The key deployment: api-server deployed ~62 seconds before incident
    # This correlates with the incident start time
    deployments = [
        {
            "service": "api-server",
            "timestamp": now
            - elapsed
            - 2,  # ~2 seconds before server started (so ~62s before incident)
            "commit": "a7f3d2e",
            "author": "alice",
            "message": "Reduce DB connection pool size for staging parity",
            "pr": "#1847",
        },
        {
            "service": "api-server",
            "timestamp": now - 3600 * 2,  # 2 hours ago
            "commit": "b8c4a1f",
            "author": "bob",
            "message": "Add retry logic for transient DB errors",
            "pr": "#1842",
        },
        {
            "service": "payment-svc",
            "timestamp": now - 3600 * 5,  # 5 hours ago
            "commit": "c2d9e8f",
            "author": "charlie",
            "message": "Update Stripe SDK to v12.3.0",
            "pr": "#1839",
        },
        {
            "service": "auth-svc",
            "timestamp": now - 3600 * 24,  # 1 day ago
            "commit": "d4e5f6a",
            "author": "diana",
            "message": "Add rate limiting for token refresh endpoint",
            "pr": "#1821",
        },
        {
            "service": "postgres",
            "timestamp": now - 3600 * 24 * 3,  # 3 days ago
            "commit": "e5f6a7b",
            "author": "evan",
            "message": "Upgrade to PostgreSQL 15.2, tune connection settings",
            "pr": "#1798",
        },
    ]

    # Filter by service if specified
    if service:
        deployments = [d for d in deployments if d["service"] == service]
        if not deployments:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"No recent deployments found for service: {service}",
                    }
                ]
            }

    lines = ["=== Recent Deployments ===", ""]

    for deploy in deployments:
        # Calculate relative time
        age_seconds = now - deploy["timestamp"]
        if age_seconds < 60:
            age_str = f"{int(age_seconds)}s ago"
        elif age_seconds < 3600:
            age_str = f"{int(age_seconds / 60)}m ago"
        elif age_seconds < 86400:
            age_str = f"{int(age_seconds / 3600)}h ago"
        else:
            age_str = f"{int(age_seconds / 86400)}d ago"

        time_str = time.strftime(
            "%Y-%m-%d %H:%M:%S", time.localtime(deploy["timestamp"])
        )

        lines.append(f"📦 {deploy['service']} - {age_str}")
        lines.append(f"   Commit: {deploy['commit']} ({deploy['pr']})")
        lines.append(f"   Author: {deploy['author']}")
        lines.append(f"   Message: {deploy['message']}")
        lines.append(f"   Time: {time_str}")
        lines.append("")

    return {"content": [{"type": "text", "text": "\n".join(lines)}]}


# Runbook definitions based on CLAUDE.md
RUNBOOKS = {
    "database_connection_exhaustion": {
        "name": "Database Connection Exhaustion",
        "symptoms": [
            "api-server in CrashLoopBackOff or high error rate",
            '"Connection refused" or "too many connections" in logs',
            "db_connections_active near max (100)",
        ],
        "investigate": {
            "description": "Diagnose database connection pool exhaustion",
            "steps": [
                {
                    "step": 1,
                    "action": "Check current DB connection utilization",
                    "query": "db_connections_active",
                    "threshold": "> 90 indicates critical exhaustion",
                },
                {
                    "step": 2,
                    "action": "Check if connections are queuing",
                    "query": "db_connections_waiting",
                    "threshold": "> 0 indicates connection starvation",
                },
                {
                    "step": 3,
                    "action": "Identify which service is holding connections",
                    "query": "sum(rate(http_requests_total[1m])) by (service)",
                    "note": "High request rate + high connections = likely culprit",
                },
                {
                    "step": 4,
                    "action": "Check for connection leak indicators in logs",
                    "tool": "get_logs",
                    "params": {"service": "postgres", "level": "error"},
                },
                {
                    "step": 5,
                    "action": "Check recent deployments for config changes",
                    "tool": "get_recent_deployments",
                    "note": "Look for connection pool or timeout changes",
                },
            ],
        },
        "remediate": {
            "description": "Remediation steps for DB connection exhaustion",
            "immediate_actions": [
                {
                    "priority": 1,
                    "action": "Restart affected service pods",
                    "command": (
                        "kubectl rollout restart"
                        " deployment/api-server"
                        " -n production"
                    ),
                    "effect": "Releases held connections, temporary fix",
                    "risk": "Brief service interruption during restart",
                },
                {
                    "priority": 2,
                    "action": "Scale down affected service to release connections",
                    "command": (
                        "kubectl scale"
                        " deployment/api-server"
                        " --replicas=1 -n production"
                    ),
                    "effect": "Reduces connection pressure immediately",
                    "risk": "Reduced capacity during incident",
                },
            ],
            "long_term_fixes": [
                {
                    "action": "Review and fix connection pool configuration",
                    "details": "Check pool size, idle timeout, max lifetime settings",
                },
                {
                    "action": "Add connection pool metrics and alerts",
                    "details": "Alert at 70% utilization before hitting limits",
                },
                {
                    "action": "Implement connection retry with backoff",
                    "details": "Prevents thundering herd on recovery",
                },
            ],
            "escalation": {
                "team": "Database team",
                "channel": "#dba-oncall",
                "when": "If connections don't recover after restart, or if this recurs",
            },
        },
    },
    "high_latency_cascade": {
        "name": "High Latency Cascade",
        "symptoms": [
            "P99 latency > 1000ms on api-server",
            "Downstream services (payment-svc) also slow",
            "Error rate increasing as timeouts occur",
        ],
        "investigate": {
            "description": "Diagnose latency cascade across services",
            "steps": [
                {
                    "step": 1,
                    "action": "Check P99 latency across all services",
                    "query": 'http_request_duration_milliseconds{quantile="0.99"}',
                    "threshold": "> 500ms warning, > 2000ms critical",
                },
                {
                    "step": 2,
                    "action": "Identify where latency originates",
                    "query": (
                        'topk(5, http_request_duration'
                        '_milliseconds{quantile="0.99"})'
                    ),
                    "note": "Service with highest latency is likely the source",
                },
                {
                    "step": 3,
                    "action": "Check database query times",
                    "query": "db_connections_waiting",
                    "note": "Waiting connections indicate DB bottleneck",
                },
                {
                    "step": 4,
                    "action": "Check for resource constraints",
                    "queries": [
                        "container_cpu_usage_ratio",
                        "container_memory_usage_ratio",
                    ],
                    "threshold": (
                        "CPU > 80% or Memory > 90%"
                        " indicates resource pressure"
                    ),
                },
                {
                    "step": 5,
                    "action": "Review error logs for timeout patterns",
                    "tool": "get_logs",
                    "params": {"service": "api-server", "level": "error"},
                },
            ],
        },
        "remediate": {
            "description": "Remediation steps for latency cascade",
            "immediate_actions": [
                {
                    "priority": 1,
                    "action": "If DB-related: Check for long-running queries",
                    "command": (
                        "SELECT * FROM pg_stat_activity"
                        " WHERE state = 'active'"
                        " AND query_start < now()"
                        " - interval '30 seconds'"
                    ),
                    "effect": "Identifies blocking queries",
                },
                {
                    "priority": 2,
                    "action": "If CPU-bound: Scale horizontally",
                    "command": (
                        "kubectl scale"
                        " deployment/api-server"
                        " --replicas=5 -n production"
                    ),
                    "effect": "Distributes load across more pods",
                },
                {
                    "priority": 3,
                    "action": "If memory-bound: Restart to clear potential leaks",
                    "command": (
                        "kubectl rollout restart"
                        " deployment/api-server"
                        " -n production"
                    ),
                    "effect": "Clears memory, resets connections",
                },
            ],
            "long_term_fixes": [
                {
                    "action": "Add circuit breakers between services",
                    "details": "Prevents cascade by failing fast",
                },
                {
                    "action": "Implement request timeouts at each layer",
                    "details": "Ensures requests don't hang indefinitely",
                },
                {
                    "action": "Add caching for frequently accessed data",
                    "details": "Reduces load on downstream services",
                },
            ],
            "escalation": {
                "team": "Platform team",
                "channel": "#platform-oncall",
                "when": (
                    "If latency doesn't improve"
                    " after scaling, or if root"
                    " cause unclear"
                ),
            },
        },
    },
    "elevated_error_rates": {
        "name": "Elevated Error Rates",
        "symptoms": [
            'http_requests_total{status="500"} increasing',
            "Alerts from monitoring",
            "User complaints",
        ],
        "investigate": {
            "description": "Diagnose elevated 5xx error rates",
            "steps": [
                {
                    "step": 1,
                    "action": "Identify which service has errors",
                    "query": (
                        'sum(rate(http_requests_total'
                        '{status="500"}[1m]))'
                        ' by (service)'
                    ),
                    "threshold": "> 1% warning, > 5% critical",
                },
                {
                    "step": 2,
                    "action": "Calculate error ratio percentage",
                    "query": (
                        'sum(rate(http_requests_total'
                        '{status="500"}[1m]))'
                        ' by (service) / '
                        'sum(rate(http_requests_total'
                        '[1m])) by (service)'
                    ),
                    "note": "Shows error percentage per service",
                },
                {
                    "step": 3,
                    "action": "Check if correlated with latency",
                    "query": 'http_request_duration_milliseconds{quantile="0.99"}',
                    "note": "High latency + errors often indicates timeouts",
                },
                {
                    "step": 4,
                    "action": "Check for resource exhaustion",
                    "queries": [
                        "db_connections_active",
                        "container_cpu_usage_ratio",
                        "container_memory_usage_ratio",
                    ],
                },
                {
                    "step": 5,
                    "action": "Check logs for specific error messages",
                    "tool": "get_logs",
                    "params": {"service": "api-server", "level": "error"},
                },
                {
                    "step": 6,
                    "action": "Check for recent deployments",
                    "tool": "get_recent_deployments",
                    "note": "Recent changes are often the cause",
                },
            ],
        },
        "remediate": {
            "description": "Remediation depends on root cause identified above",
            "decision_tree": [
                {
                    "condition": "If caused by DB connection exhaustion",
                    "action": "Follow database_connection_exhaustion runbook",
                },
                {
                    "condition": "If caused by high latency/timeouts",
                    "action": "Follow high_latency_cascade runbook",
                },
                {
                    "condition": "If caused by recent deployment",
                    "action": "Rollback the deployment",
                    "command": (
                        "kubectl rollout undo"
                        " deployment/api-server"
                        " -n production"
                    ),
                },
                {
                    "condition": "If caused by external dependency failure",
                    "action": "Enable circuit breaker / fallback mode",
                },
            ],
            "immediate_actions": [
                {
                    "priority": 1,
                    "action": "If recent deployment suspected, rollback immediately",
                    "command": (
                        "kubectl rollout undo"
                        " deployment/<service>"
                        " -n production"
                    ),
                    "effect": "Reverts to last known good state",
                },
            ],
            "escalation": {
                "team": "Depends on affected service",
                "channels": {
                    "api-server": "#platform-oncall",
                    "payment-svc": "#payments-oncall",
                    "auth-svc": "#identity-oncall",
                },
                "when": (
                    "If root cause cannot be"
                    " identified or errors persist"
                    " after remediation"
                ),
            },
        },
    },
}


async def execute_runbook(runbook: str, phase: str) -> dict[str, Any]:
    """Execute a documented runbook for incident response."""
    if runbook not in RUNBOOKS:
        return {
            "content": [
                {
                    "type": "text",
                    "text": (
                        f"Unknown runbook: {runbook}\n"
                        "Available runbooks: "
                        f"{', '.join(RUNBOOKS.keys())}"
                    ),
                }
            ],
            "isError": True,
        }

    rb = RUNBOOKS[runbook]
    lines = [f"=== Runbook: {rb['name']} ===", ""]

    if phase == "investigate":
        # Show symptoms to confirm this is the right runbook
        lines.append("SYMPTOMS (confirm these match your incident):")
        for symptom in rb["symptoms"]:
            lines.append(f"  • {symptom}")
        lines.append("")

        # Show investigation steps
        inv = rb["investigate"]
        lines.append(f"INVESTIGATION: {inv['description']}")
        lines.append("")

        for step in inv["steps"]:
            lines.append(f"Step {step['step']}: {step['action']}")

            if "query" in step:
                lines.append(f"  → Run query: {step['query']}")
            if "queries" in step:
                for q in step["queries"]:
                    lines.append(f"  → Run query: {q}")
            if "tool" in step:
                lines.append(f"  → Use tool: {step['tool']}")
                if "params" in step:
                    params_str = ", ".join(
                        f"{k}={v}" for k, v in step["params"].items()
                    )
                    lines.append(f"     with params: {params_str}")
            if "threshold" in step:
                lines.append(f"  → Threshold: {step['threshold']}")
            if "note" in step:
                lines.append(f"  → Note: {step['note']}")
            lines.append("")

        lines.append(
            "After completing investigation, run this"
            " runbook again with phase='remediate'"
        )

    elif phase == "remediate":
        rem = rb["remediate"]
        lines.append(f"REMEDIATION: {rem['description']}")
        lines.append("")

        # Show decision tree if present
        if "decision_tree" in rem:
            lines.append("DECISION TREE:")
            for decision in rem["decision_tree"]:
                lines.append(f"  IF: {decision['condition']}")
                lines.append(f"  THEN: {decision['action']}")
                if "command" in decision:
                    lines.append(f"       Command: {decision['command']}")
                lines.append("")

        # Show immediate actions
        if "immediate_actions" in rem:
            lines.append("IMMEDIATE ACTIONS:")
            for action in rem["immediate_actions"]:
                lines.append(f"  [{action['priority']}] {action['action']}")
                if "command" in action:
                    lines.append(f"      Command: {action['command']}")
                if "effect" in action:
                    lines.append(f"      Effect: {action['effect']}")
                if "risk" in action:
                    lines.append(f"      Risk: {action['risk']}")
                lines.append("")

        # Show long-term fixes
        if "long_term_fixes" in rem:
            lines.append("LONG-TERM FIXES (for post-incident):")
            for fix in rem["long_term_fixes"]:
                lines.append(f"  • {fix['action']}")
                lines.append(f"    {fix['details']}")
            lines.append("")

        # Show escalation info
        if "escalation" in rem:
            esc = rem["escalation"]
            lines.append("ESCALATION:")
            if "team" in esc:
                lines.append(f"  Team: {esc['team']}")
            if "channel" in esc:
                lines.append(f"  Channel: {esc['channel']}")
            if "channels" in esc:
                for svc, channel in esc["channels"].items():
                    lines.append(f"  {svc}: {channel}")
            if "when" in esc:
                lines.append(f"  When: {esc['when']}")

    return {"content": [{"type": "text", "text": "\n".join(lines)}]}


# ============================================================================
# PagerDuty Integration Handlers
# ============================================================================


async def pagerduty_create_incident(
    title: str, description: str, urgency: str = "high", service_id: str | None = None
) -> dict[str, Any]:
    """Create a PagerDuty incident."""
    if not PAGERDUTY_API_KEY:
        return {
            "content": [
                {
                    "type": "text",
                    "text": "PagerDuty not configured. Set PAGERDUTY_API_KEY in .env",
                }
            ],
            "isError": True,
        }

    service = service_id or PAGERDUTY_SERVICE_ID
    if not service:
        return {
            "content": [
                {
                    "type": "text",
                    "text": (
                        "No service ID provided and"
                        " PAGERDUTY_SERVICE_ID not"
                        " set in .env"
                    ),
                }
            ],
            "isError": True,
        }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{PAGERDUTY_BASE_URL}/incidents",
                headers={
                    "Authorization": f"Token token={PAGERDUTY_API_KEY}",
                    "Content-Type": "application/json",
                    "From": PAGERDUTY_FROM_EMAIL or "sre-bot@example.com",
                },
                json={
                    "incident": {
                        "type": "incident",
                        "title": title,
                        "service": {"id": service, "type": "service_reference"},
                        "urgency": urgency,
                        "body": {"type": "incident_body", "details": description},
                    }
                },
                timeout=10.0,
            )
            response.raise_for_status()
            incident = response.json()["incident"]

            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"Created PagerDuty incident:\n"
                        f"  ID: {incident['id']}\n"
                        f"  URL: {incident['html_url']}\n"
                        f"  Status: {incident['status']}\n"
                        f"  Urgency: {incident['urgency']}",
                    }
                ]
            }
    except httpx.HTTPStatusError as e:
        return {
            "content": [
                {
                    "type": "text",
                    "text": (
                        "PagerDuty API error: "
                        f"{e.response.status_code}"
                        f" - {e.response.text}"
                    ),
                }
            ],
            "isError": True,
        }
    except Exception as e:
        return {
            "content": [{"type": "text", "text": f"Error creating incident: {str(e)}"}],
            "isError": True,
        }


async def pagerduty_update_incident(
    incident_id: str, status: str, resolution_note: str | None = None
) -> dict[str, Any]:
    """Update a PagerDuty incident status."""
    if not PAGERDUTY_API_KEY:
        return {
            "content": [{"type": "text", "text": "PagerDuty not configured"}],
            "isError": True,
        }

    try:
        headers = {
            "Authorization": f"Token token={PAGERDUTY_API_KEY}",
            "Content-Type": "application/json",
            "From": PAGERDUTY_FROM_EMAIL or "sre-bot@example.com",
        }

        async with httpx.AsyncClient() as client:
            response = await client.put(
                f"{PAGERDUTY_BASE_URL}/incidents/{incident_id}",
                headers=headers,
                json={
                    "incident": {
                        "id": incident_id,
                        "type": "incident_reference",
                        "status": status,
                    }
                },
                timeout=10.0,
            )
            response.raise_for_status()
            incident = response.json()["incident"]

            # Add resolution note if provided
            if resolution_note and status == "resolved":
                await client.post(
                    f"{PAGERDUTY_BASE_URL}/incidents/{incident_id}/notes",
                    headers=headers,
                    json={"note": {"content": f"Resolution: {resolution_note}"}},
                    timeout=10.0,
                )

            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"Updated incident {incident_id}:\n"
                        f"  Status: {incident['status']}\n"
                        f"  URL: {incident['html_url']}",
                    }
                ]
            }
    except httpx.HTTPStatusError as e:
        return {
            "content": [
                {
                    "type": "text",
                    "text": (
                        "PagerDuty API error: "
                        f"{e.response.status_code}"
                        f" - {e.response.text}"
                    ),
                }
            ],
            "isError": True,
        }
    except Exception as e:
        return {
            "content": [{"type": "text", "text": f"Error updating incident: {str(e)}"}],
            "isError": True,
        }


async def pagerduty_get_incident(incident_id: str) -> dict[str, Any]:
    """Get PagerDuty incident details."""
    if not PAGERDUTY_API_KEY:
        return {
            "content": [{"type": "text", "text": "PagerDuty not configured"}],
            "isError": True,
        }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{PAGERDUTY_BASE_URL}/incidents/{incident_id}",
                headers={"Authorization": f"Token token={PAGERDUTY_API_KEY}"},
                timeout=10.0,
            )
            response.raise_for_status()
            incident = response.json()["incident"]

            lines = [
                f"=== PagerDuty Incident {incident_id} ===",
                f"Title: {incident['title']}",
                f"Status: {incident['status']}",
                f"Urgency: {incident['urgency']}",
                f"Created: {incident['created_at']}",
                f"Service: {incident['service']['summary']}",
                f"URL: {incident['html_url']}",
            ]

            if incident.get("assignments"):
                assignees = [a["assignee"]["summary"] for a in incident["assignments"]]
                lines.append(f"Assigned to: {', '.join(assignees)}")

            return {"content": [{"type": "text", "text": "\n".join(lines)}]}
    except httpx.HTTPStatusError as e:
        return {
            "content": [
                {
                    "type": "text",
                    "text": (
                        "PagerDuty API error: "
                        f"{e.response.status_code}"
                        f" - {e.response.text}"
                    ),
                }
            ],
            "isError": True,
        }
    except Exception as e:
        return {
            "content": [{"type": "text", "text": f"Error fetching incident: {str(e)}"}],
            "isError": True,
        }


async def pagerduty_list_incidents(
    status: str = "all", service_id: str | None = None
) -> dict[str, Any]:
    """List PagerDuty incidents."""
    if not PAGERDUTY_API_KEY:
        return {
            "content": [{"type": "text", "text": "PagerDuty not configured"}],
            "isError": True,
        }

    try:
        params = {"limit": 25}
        if status == "all":
            params["statuses[]"] = ["triggered", "acknowledged"]
        else:
            params["statuses[]"] = [status]
        if service_id:
            params["service_ids[]"] = [service_id]

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{PAGERDUTY_BASE_URL}/incidents",
                headers={"Authorization": f"Token token={PAGERDUTY_API_KEY}"},
                params=params,
                timeout=10.0,
            )
            response.raise_for_status()
            incidents = response.json()["incidents"]

            if not incidents:
                return {
                    "content": [{"type": "text", "text": "No active incidents found."}]
                }

            lines = [f"=== Active PagerDuty Incidents ({len(incidents)}) ===", ""]
            for inc in incidents:
                status_emoji = {
                    "triggered": "[TRIG]",
                    "acknowledged": "[ACK]",
                    "resolved": "[DONE]",
                }
                lines.append(f"{status_emoji.get(inc['status'], '[?]')} {inc['title']}")
                lines.append(
                    f"    ID: {inc['id']} | Service: {inc['service']['summary']}"
                )
                lines.append(f"    Created: {inc['created_at']}")
                lines.append("")

            return {"content": [{"type": "text", "text": "\n".join(lines)}]}
    except httpx.HTTPStatusError as e:
        return {
            "content": [
                {
                    "type": "text",
                    "text": (
                        "PagerDuty API error: "
                        f"{e.response.status_code}"
                        f" - {e.response.text}"
                    ),
                }
            ],
            "isError": True,
        }
    except Exception as e:
        return {
            "content": [{"type": "text", "text": f"Error listing incidents: {str(e)}"}],
            "isError": True,
        }


# ============================================================================
# Confluence Integration Handlers
# ============================================================================


def get_confluence_auth_header() -> str:
    """Generate Basic auth header for Confluence API."""
    credentials = f"{CONFLUENCE_USER_EMAIL}:{CONFLUENCE_API_TOKEN}"
    encoded = base64.b64encode(credentials.encode()).decode()
    return f"Basic {encoded}"


def generate_postmortem_content(
    incident_summary: str,
    timeline: list[str],
    root_cause: str,
    impact: str,
    remediation_steps: list[str],
    action_items: list[dict],
    pagerduty_incident_id: str | None = None,
) -> str:
    """Generate Confluence Storage Format (XHTML) for post-mortem."""
    esc = html.escape

    # Build timeline section
    timeline_html = ""
    if timeline:
        timeline_html = (
            "<ul>" + "".join(f"<li>{esc(item)}</li>" for item in timeline) + "</ul>"
        )
    else:
        timeline_html = "<p><em>Timeline to be added</em></p>"

    # Build remediation section
    remediation_html = ""
    if remediation_steps:
        remediation_html = (
            "<ul>"
            + "".join(f"<li>{esc(step)}</li>" for step in remediation_steps)
            + "</ul>"
        )
    else:
        remediation_html = "<p><em>Remediation steps to be added</em></p>"

    # Build action items table
    action_items_html = """
    <table>
        <thead><tr><th>Task</th><th>Owner</th>
        <th>Due Date</th><th>Status</th></tr></thead>
        <tbody>
    """
    if action_items:
        for item in action_items:
            action_items_html += f"""
            <tr>
                <td>{esc(item.get("task", "TBD"))}</td>
                <td>{esc(item.get("owner", "TBD"))}</td>
                <td>{esc(item.get("due_date", "TBD"))}</td>
                <td>Open</td>
            </tr>
            """
    else:
        action_items_html += (
            "<tr><td colspan='4'><em>Action items to be added</em></td></tr>"
        )
    action_items_html += "</tbody></table>"

    # PagerDuty link if provided
    pd_link = ""
    if pagerduty_incident_id:
        pd_link = (
            f"<p><strong>PagerDuty Incident:</strong> {esc(pagerduty_incident_id)}</p>"
        )

    return f"""
    <h1>Incident Summary</h1>
    {pd_link}
    <p>{esc(incident_summary)}</p>

    <h1>Timeline</h1>
    {timeline_html}

    <h1>Root Cause</h1>
    <p>{esc(root_cause)}</p>

    <h1>Impact</h1>
    <p>{esc(impact) if impact else "<em>Impact assessment to be added</em>"}</p>

    <h1>Remediation Steps</h1>
    {remediation_html}

    <h1>Action Items</h1>
    {action_items_html}

    <hr/>
    <p><em>Generated by SRE Bot on
    {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</em></p>
    """


async def confluence_create_postmortem(
    title: str,
    incident_summary: str,
    root_cause: str,
    timeline: list[str] | None = None,
    impact: str | None = None,
    remediation_steps: list[str] | None = None,
    action_items: list[dict] | None = None,
    pagerduty_incident_id: str | None = None,
) -> dict[str, Any]:
    """Create a post-mortem page in Confluence."""
    if not CONFLUENCE_API_TOKEN or not CONFLUENCE_BASE_URL:
        return {
            "content": [
                {
                    "type": "text",
                    "text": (
                        "Confluence not configured."
                        " Set CONFLUENCE_* variables"
                        " in .env"
                    ),
                }
            ],
            "isError": True,
        }

    content = generate_postmortem_content(
        incident_summary=incident_summary,
        timeline=timeline or [],
        root_cause=root_cause,
        impact=impact or "",
        remediation_steps=remediation_steps or [],
        action_items=action_items or [],
        pagerduty_incident_id=pagerduty_incident_id,
    )

    page_data = {
        "type": "page",
        "title": title,
        "space": {"key": CONFLUENCE_SPACE_KEY},
        "body": {"storage": {"value": content, "representation": "storage"}},
    }

    if CONFLUENCE_PARENT_PAGE_ID:
        page_data["ancestors"] = [{"id": CONFLUENCE_PARENT_PAGE_ID}]

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{CONFLUENCE_BASE_URL}/rest/api/content",
                headers={
                    "Authorization": get_confluence_auth_header(),
                    "Content-Type": "application/json",
                },
                json=page_data,
                timeout=15.0,
            )
            response.raise_for_status()
            page = response.json()

            page_url = f"{CONFLUENCE_BASE_URL}{page['_links']['webui']}"

            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"Created post-mortem page:\n"
                        f"  Title: {page['title']}\n"
                        f"  ID: {page['id']}\n"
                        f"  URL: {page_url}",
                    }
                ]
            }
    except httpx.HTTPStatusError as e:
        return {
            "content": [
                {
                    "type": "text",
                    "text": (
                        "Confluence API error: "
                        f"{e.response.status_code}"
                        f" - {e.response.text}"
                    ),
                }
            ],
            "isError": True,
        }
    except Exception as e:
        return {
            "content": [
                {"type": "text", "text": f"Error creating post-mortem: {str(e)}"}
            ],
            "isError": True,
        }


async def confluence_get_page(
    page_id: str | None = None, title: str | None = None
) -> dict[str, Any]:
    """Get a Confluence page by ID or title."""
    if not CONFLUENCE_API_TOKEN:
        return {
            "content": [{"type": "text", "text": "Confluence not configured"}],
            "isError": True,
        }

    if not page_id and not title:
        return {
            "content": [{"type": "text", "text": "Provide either page_id or title"}],
            "isError": True,
        }

    try:
        async with httpx.AsyncClient() as client:
            if page_id:
                response = await client.get(
                    f"{CONFLUENCE_BASE_URL}/rest/api/content/{page_id}",
                    headers={"Authorization": get_confluence_auth_header()},
                    params={"expand": "body.storage,version"},
                    timeout=10.0,
                )
            else:
                response = await client.get(
                    f"{CONFLUENCE_BASE_URL}/rest/api/content",
                    headers={"Authorization": get_confluence_auth_header()},
                    params={
                        "title": title,
                        "spaceKey": CONFLUENCE_SPACE_KEY,
                        "expand": "body.storage,version",
                    },
                    timeout=10.0,
                )

            response.raise_for_status()
            data = response.json()

            if "results" in data:
                if not data["results"]:
                    return {
                        "content": [
                            {
                                "type": "text",
                                "text": f"No page found with title: {title}",
                            }
                        ]
                    }
                page = data["results"][0]
            else:
                page = data

            page_url = f"{CONFLUENCE_BASE_URL}{page['_links']['webui']}"

            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"=== Confluence Page ===\n"
                        f"Title: {page['title']}\n"
                        f"ID: {page['id']}\n"
                        f"Version: {page['version']['number']}\n"
                        f"URL: {page_url}",
                    }
                ]
            }
    except httpx.HTTPStatusError as e:
        return {
            "content": [
                {
                    "type": "text",
                    "text": (
                        "Confluence API error: "
                        f"{e.response.status_code}"
                        f" - {e.response.text}"
                    ),
                }
            ],
            "isError": True,
        }
    except Exception as e:
        return {
            "content": [{"type": "text", "text": f"Error fetching page: {str(e)}"}],
            "isError": True,
        }


async def confluence_list_postmortems(
    days: int = 30, search_term: str | None = None
) -> dict[str, Any]:
    """List recent post-mortem pages."""
    if not CONFLUENCE_API_TOKEN:
        return {
            "content": [{"type": "text", "text": "Confluence not configured"}],
            "isError": True,
        }

    try:
        # Use CQL (Confluence Query Language) to search
        cql = f'space = "{CONFLUENCE_SPACE_KEY}" AND title ~ "Post-Mortem"'
        cql += f' AND created >= now("-{days}d")'
        if search_term:
            sanitized = search_term.replace('"', '\\"').replace("'", "\\'")
            cql += f' AND text ~ "{sanitized}"'

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{CONFLUENCE_BASE_URL}/rest/api/content/search",
                headers={"Authorization": get_confluence_auth_header()},
                params={"cql": cql, "limit": 20, "expand": "version"},
                timeout=10.0,
            )
            response.raise_for_status()
            results = response.json().get("results", [])

            if not results:
                return {
                    "content": [{"type": "text", "text": "No post-mortem pages found."}]
                }

            lines = [f"=== Recent Post-Mortems ({len(results)}) ===", ""]
            for page in results:
                page_url = f"{CONFLUENCE_BASE_URL}{page['_links']['webui']}"
                lines.append(f"- {page['title']}")
                lines.append(
                    f"  ID: {page['id']}"
                    f" | Last modified: {page['version']['when'][:10]}"
                )
                lines.append(f"  URL: {page_url}")
                lines.append("")

            return {"content": [{"type": "text", "text": "\n".join(lines)}]}
    except httpx.HTTPStatusError as e:
        return {
            "content": [
                {
                    "type": "text",
                    "text": (
                        "Confluence API error: "
                        f"{e.response.status_code}"
                        f" - {e.response.text}"
                    ),
                }
            ],
            "isError": True,
        }
    except Exception as e:
        return {
            "content": [
                {"type": "text", "text": f"Error listing post-mortems: {str(e)}"}
            ],
            "isError": True,
        }


# ========== Config File Tools ==========


async def read_config_file(path: str) -> dict[str, Any]:
    """Read a configuration file from the project directory."""
    try:
        # Security: Only allow reading from config directory
        full_path = (PROJECT_ROOT / path).resolve()
        allowed_root = (PROJECT_ROOT / "config").resolve()
        if not full_path.is_relative_to(allowed_root):
            return {
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "Error: Can only read files"
                            " from config/ directory."
                            f" Got: {path}"
                        ),
                    }
                ],
                "isError": True,
            }

        if not full_path.exists():
            return {
                "content": [{"type": "text", "text": f"File not found: {path}"}],
                "isError": True,
            }

        with open(full_path, "r") as f:
            content = f.read()

        return {"content": [{"type": "text", "text": f"=== {path} ===\n\n{content}"}]}
    except Exception as e:
        return {
            "content": [{"type": "text", "text": f"Error reading file: {str(e)}"}],
            "isError": True,
        }


async def edit_config_file(path: str, old_value: str, new_value: str) -> dict[str, Any]:
    """Edit a configuration file by replacing a value."""
    try:
        # Security: Only allow editing config directory
        full_path = (PROJECT_ROOT / path).resolve()
        allowed_root = (PROJECT_ROOT / "config").resolve()
        if not full_path.is_relative_to(allowed_root):
            return {
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "Error: Can only edit files"
                            " in config/ directory."
                            f" Got: {path}"
                        ),
                    }
                ],
                "isError": True,
            }

        if not full_path.exists():
            return {
                "content": [{"type": "text", "text": f"File not found: {path}"}],
                "isError": True,
            }

        with open(full_path, "r") as f:
            content = f.read()

        if old_value not in content:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": (
                            f"Error: Could not find"
                            f" '{old_value}' in {path}."
                            f"\n\nCurrent content:\n{content}"
                        ),
                    }
                ],
                "isError": True,
            }

        new_content = content.replace(old_value, new_value, 1)

        with open(full_path, "w") as f:
            f.write(new_content)

        return {
            "content": [
                {
                    "type": "text",
                    "text": (
                        f"Successfully updated {path}:\n"
                        f"- Changed: {old_value}\n"
                        f"- To: {new_value}"
                    ),
                }
            ]
        }
    except Exception as e:
        return {
            "content": [{"type": "text", "text": f"Error editing file: {str(e)}"}],
            "isError": True,
        }


async def run_shell_command(command: str) -> dict[str, Any]:
    """Run a shell command in the project directory."""
    try:
        # Parse command into tokens safely (rejects unbalanced quotes)
        try:
            args = shlex.split(command)
        except ValueError as e:
            return {
                "content": [
                    {"type": "text", "text": f"Error: Invalid command syntax: {e}"}
                ],
                "isError": True,
            }

        if not args:
            return {
                "content": [{"type": "text", "text": "Error: Empty command"}],
                "isError": True,
            }

        # Security: Validate the executable and subcommand against an allowlist.
        # "docker-compose" is a single binary; "docker compose/ps/logs" are
        # subcommands of the "docker" binary.
        allowed_commands = {
            "docker-compose": {"up", "down", "ps", "logs", "restart", "build"},
            "docker": {"compose", "ps", "logs"},
        }

        executable = args[0]
        if executable not in allowed_commands:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "Error: Only docker/docker-compose"
                            " commands are allowed."
                            f" Got: {executable}"
                        ),
                    }
                ],
                "isError": True,
            }

        allowed_subs = allowed_commands[executable]
        if allowed_subs is not None:
            subcommand = args[1] if len(args) > 1 else ""
            if subcommand not in allowed_subs:
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                f"Error: '{executable}"
                                f" {subcommand}' is not"
                                " allowed. Allowed: "
                                f"{', '.join(sorted(allowed_subs))}"
                            ),
                        }
                    ],
                    "isError": True,
                }

            # "docker compose <verb>" is the modern plugin-syntax equivalent
            # of docker-compose. Without this check, "docker compose run
            # --privileged ..." passes the check above unmodified (subcommand
            # == "compose") and reopens the exact escape this allowlist
            # exists to prevent.
            if executable == "docker" and subcommand == "compose":
                nested_sub = args[2] if len(args) > 2 else ""
                if nested_sub not in allowed_commands["docker-compose"]:
                    return {
                        "content": [
                            {
                                "type": "text",
                                "text": (
                                    f"Error: 'docker compose {nested_sub}' is"
                                    " not allowed. Allowed: "
                                    f"{', '.join(sorted(allowed_commands['docker-compose']))}"
                                ),
                            }
                        ],
                        "isError": True,
                    }

        # Run using exec (no shell) to prevent injection via metacharacters
        process = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=PROJECT_ROOT,
        )

        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=60.0)

        output = stdout.decode("utf-8", errors="replace")
        error = stderr.decode("utf-8", errors="replace")

        result_text = f"$ {command}\n\n"
        if output:
            result_text += f"STDOUT:\n{output}\n"
        if error:
            result_text += f"STDERR:\n{error}\n"
        result_text += f"\nExit code: {process.returncode}"

        return {
            "content": [{"type": "text", "text": result_text}],
            "isError": process.returncode != 0,
        }
    except asyncio.TimeoutError:
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Command timed out after 60 seconds: {command}",
                }
            ],
            "isError": True,
        }
    except Exception as e:
        return {
            "content": [{"type": "text", "text": f"Error running command: {str(e)}"}],
            "isError": True,
        }


async def get_container_logs(container: str, lines: int = 50) -> dict[str, Any]:
    """Get logs from a Docker container."""
    try:
        # Validate container name
        valid_containers = [
            "api-server",
            "postgres",
            "traffic-generator",
            "prometheus",
            "grafana",
        ]
        if container not in valid_containers:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": (
                            f"Invalid container: {container}."
                            " Valid options: "
                            f"{', '.join(valid_containers)}"
                        ),
                    }
                ],
                "isError": True,
            }

        # Limit lines
        lines = min(max(1, lines), 200)

        # Get logs using docker-compose
        args = [
            "docker-compose",
            "-f",
            "config/docker-compose.yml",
            "logs",
            container,
            f"--tail={lines}",
        ]

        process = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=PROJECT_ROOT,
        )

        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=30.0)

        output = stdout.decode("utf-8", errors="replace")
        error = stderr.decode("utf-8", errors="replace")

        if process.returncode != 0:
            return {
                "content": [{"type": "text", "text": f"Error getting logs: {error}"}],
                "isError": True,
            }

        return {
            "content": [
                {
                    "type": "text",
                    "text": (
                        f"=== Logs from {container}"
                        f" (last {lines} lines)"
                        f" ===\n\n{output}"
                    ),
                }
            ]
        }
    except asyncio.TimeoutError:
        return {
            "content": [
                {"type": "text", "text": f"Timeout getting logs from {container}"}
            ],
            "isError": True,
        }
    except Exception as e:
        return {
            "content": [
                {"type": "text", "text": f"Error getting container logs: {str(e)}"}
            ],
            "isError": True,
        }


async def write_postmortem(
    title: str,
    summary: str,
    root_cause: str,
    timeline: str = "",
    remediation: str = "",
    action_items: str = "",
) -> dict[str, Any]:
    """Write a post-mortem report to the postmortems/ directory."""

    postmortems_dir = PROJECT_ROOT / "postmortems"
    postmortems_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"postmortem_{timestamp}.md"
    filepath = postmortems_dir / filename

    content = f"# Post-Mortem: {title}\n\n"
    content += f"**Date**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    content += f"## Summary\n\n{summary}\n\n"
    content += f"## Root Cause\n\n{root_cause}\n\n"
    if timeline:
        content += f"## Timeline\n\n{timeline}\n\n"
    if remediation:
        content += f"## Remediation\n\n{remediation}\n\n"
    if action_items:
        content += f"## Action Items\n\n{action_items}\n\n"

    with open(filepath, "w") as f:
        f.write(content)

    return {
        "content": [{"type": "text", "text": f"Post-mortem written to {filename}"}],
        "isError": False,
    }


async def handle_tool_call(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Route tool calls to the appropriate handler."""
    if name == "query_metrics":
        return await query_metrics(arguments.get("promql", ""))
    elif name == "list_metrics":
        return await list_metrics()
    elif name == "get_service_health":
        return await get_service_health()
    elif name == "get_logs":
        return await get_logs(
            service=arguments.get("service", ""),
            level=arguments.get("level", "all"),
            lines=arguments.get("lines", 20),
        )
    elif name == "get_alerts":
        return await get_alerts()
    elif name == "get_recent_deployments":
        return await get_recent_deployments(service=arguments.get("service"))
    elif name == "execute_runbook":
        return await execute_runbook(
            runbook=arguments.get("runbook", ""),
            phase=arguments.get("phase", "investigate"),
        )
    elif name == "write_postmortem":
        return await write_postmortem(
            title=arguments.get("title", ""),
            summary=arguments.get("summary", ""),
            root_cause=arguments.get("root_cause", ""),
            timeline=arguments.get("timeline", ""),
            remediation=arguments.get("remediation", ""),
            action_items=arguments.get("action_items", ""),
        )
    # PagerDuty tools
    elif name == "pagerduty_create_incident":
        return await pagerduty_create_incident(
            title=arguments.get("title", ""),
            description=arguments.get("description", ""),
            urgency=arguments.get("urgency", "high"),
            service_id=arguments.get("service_id"),
        )
    elif name == "pagerduty_update_incident":
        return await pagerduty_update_incident(
            incident_id=arguments.get("incident_id", ""),
            status=arguments.get("status", ""),
            resolution_note=arguments.get("resolution_note"),
        )
    elif name == "pagerduty_get_incident":
        return await pagerduty_get_incident(
            incident_id=arguments.get("incident_id", "")
        )
    elif name == "pagerduty_list_incidents":
        return await pagerduty_list_incidents(
            status=arguments.get("status", "all"),
            service_id=arguments.get("service_id"),
        )
    # Confluence tools
    elif name == "confluence_create_postmortem":
        return await confluence_create_postmortem(
            title=arguments.get("title", ""),
            incident_summary=arguments.get("incident_summary", ""),
            root_cause=arguments.get("root_cause", ""),
            timeline=arguments.get("timeline"),
            impact=arguments.get("impact"),
            remediation_steps=arguments.get("remediation_steps"),
            action_items=arguments.get("action_items"),
            pagerduty_incident_id=arguments.get("pagerduty_incident_id"),
        )
    elif name == "confluence_get_page":
        return await confluence_get_page(
            page_id=arguments.get("page_id"), title=arguments.get("title")
        )
    elif name == "confluence_list_postmortems":
        return await confluence_list_postmortems(
            days=arguments.get("days", 30), search_term=arguments.get("search_term")
        )
    # Config and infrastructure tools
    elif name == "read_config_file":
        return await read_config_file(path=arguments.get("path", ""))
    elif name == "edit_config_file":
        return await edit_config_file(
            path=arguments.get("path", ""),
            old_value=arguments.get("old_value", ""),
            new_value=arguments.get("new_value", ""),
        )
    elif name == "run_shell_command":
        return await run_shell_command(command=arguments.get("command", ""))
    elif name == "get_container_logs":
        return await get_container_logs(
            container=arguments.get("container", ""), lines=arguments.get("lines", 50)
        )
    else:
        return {
            "content": [{"type": "text", "text": f"Unknown tool: {name}"}],
            "isError": True,
        }


def send_response(response: dict[str, Any]) -> None:
    """Send a JSON-RPC response to stdout."""
    json_str = json.dumps(response)
    sys.stdout.write(json_str + "\n")
    sys.stdout.flush()


def send_error(id: Any, code: int, message: str) -> None:
    """Send a JSON-RPC error response."""
    send_response(
        {"jsonrpc": "2.0", "id": id, "error": {"code": code, "message": message}}
    )


async def handle_request(request: dict[str, Any]) -> None:
    """Handle an incoming JSON-RPC request."""
    method = request.get("method", "")
    req_id = request.get("id")
    params = request.get("params", {})

    if method == "initialize":
        # MCP initialization
        send_response(
            {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "sre-tools", "version": "1.0.0"},
                },
            }
        )
    elif method == "notifications/initialized":
        # No response needed for notifications
        pass
    elif method == "tools/list":
        send_response({"jsonrpc": "2.0", "id": req_id, "result": {"tools": TOOLS}})
    elif method == "tools/call":
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})
        result = await handle_tool_call(tool_name, arguments)
        send_response({"jsonrpc": "2.0", "id": req_id, "result": result})
    else:
        send_error(req_id, -32601, f"Method not found: {method}")


async def main():
    """Main event loop - read JSON-RPC requests from stdin."""
    # Disable buffering for stdin
    loop = asyncio.get_running_loop()
    reader = asyncio.StreamReader()
    protocol = asyncio.StreamReaderProtocol(reader)
    await loop.connect_read_pipe(lambda: protocol, sys.stdin)

    while True:
        try:
            line = await reader.readline()
            if not line:
                break

            line = line.decode("utf-8").strip()
            if not line:
                continue

            try:
                request = json.loads(line)
                await handle_request(request)
            except json.JSONDecodeError as e:
                send_error(None, -32700, f"Parse error: {e}")

        except Exception as e:
            # Log to stderr so it doesn't interfere with JSON-RPC
            print(f"Error: {e}", file=sys.stderr)
            break


if __name__ == "__main__":
    asyncio.run(main())
