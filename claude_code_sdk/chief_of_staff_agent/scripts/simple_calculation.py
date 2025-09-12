#!/usr/bin/env python3
"""
Simple script to demonstrate Bash tool usage from an agent.
Calculates basic metrics that an AI Chief of Staff might need.
"""

import json
import sys


def calculate_metrics(total_runway, monthly_burn):
    """Calculate key financial metrics."""
    runway_months = total_runway / monthly_burn
    quarterly_burn = monthly_burn * 3

    metrics = {
        "monthly_burn": monthly_burn,
        "runway_months": runway_months,
        "total_runway_dollars": total_runway,
        "quarterly_burn": quarterly_burn,
        "burn_rate_daily": round(monthly_burn / 30, 2),
    }

    return metrics


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python simple_calculation.py <total_runway> <monthly_burn>")
        sys.exit(1)

    try:
        runway = float(sys.argv[1])
        burn = float(sys.argv[2])

        results = calculate_metrics(runway, burn)

        print(json.dumps(results, indent=2))

    except ValueError:
        print("Error: Arguments must be numbers")
        sys.exit(1)
