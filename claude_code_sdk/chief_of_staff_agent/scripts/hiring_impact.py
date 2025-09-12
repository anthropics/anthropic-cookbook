#!/usr/bin/env python3
"""
Hiring Impact Calculator for TechStart Inc
Calculates the financial impact of hiring engineers
"""

import json
import sys


def calculate_hiring_impact(num_engineers, salary_per_engineer=200000):
    """
    Calculate the financial impact of hiring engineers.

    Args:
        num_engineers: Number of engineers to hire
        salary_per_engineer: Annual salary per engineer (default: $200K)

    Returns:
        Dictionary with financial impact metrics
    """
    # Current financials (from CLAUDE.md)
    CURRENT_BURN_MONTHLY = 500000  # $500K/month
    CURRENT_RUNWAY_MONTHS = 20  # 20 months
    CASH_IN_BANK = 10000000  # $10M

    # Calculate loaded cost (salary + benefits + taxes = salary * 1.3)
    annual_loaded_cost_per_engineer = salary_per_engineer * 1.3
    monthly_cost_per_engineer = annual_loaded_cost_per_engineer / 12

    # Total monthly cost increase
    total_monthly_increase = monthly_cost_per_engineer * num_engineers

    # New burn rate
    new_burn_monthly = CURRENT_BURN_MONTHLY + total_monthly_increase

    # New runway
    new_runway_months = CASH_IN_BANK / new_burn_monthly
    runway_reduction_months = CURRENT_RUNWAY_MONTHS - new_runway_months

    # Calculate potential revenue impact (assumption: engineers increase velocity by 15%)
    velocity_increase = 0.15 * num_engineers / 5  # Assuming 5 engineers = 15% increase

    # Recommendation
    if runway_reduction_months > 3:
        recommendation = "HIGH RISK: Significant runway reduction. Consider phased hiring."
    elif runway_reduction_months > 1.5:
        recommendation = "MODERATE RISK: Manageable if revenue growth accelerates."
    else:
        recommendation = "LOW RISK: Minimal impact on runway. Proceed if talent is available."

    return {
        "num_engineers": num_engineers,
        "salary_per_engineer": salary_per_engineer,
        "monthly_cost_per_engineer": round(monthly_cost_per_engineer, 2),
        "total_monthly_increase": round(total_monthly_increase, 2),
        "current_burn_monthly": CURRENT_BURN_MONTHLY,
        "new_burn_monthly": round(new_burn_monthly, 2),
        "current_runway_months": CURRENT_RUNWAY_MONTHS,
        "new_runway_months": round(new_runway_months, 2),
        "runway_reduction_months": round(runway_reduction_months, 2),
        "velocity_increase_percent": round(velocity_increase * 100, 1),
        "recommendation": recommendation,
    }


def main():
    # Parse command line arguments
    if len(sys.argv) < 2:
        print("Usage: python hiring_impact.py <num_engineers> [salary_per_engineer]")
        sys.exit(1)

    num_engineers = int(sys.argv[1])
    salary = int(sys.argv[2]) if len(sys.argv) > 2 else 200000

    # Calculate impact
    impact = calculate_hiring_impact(num_engineers, salary)

    # Output as JSON for easy parsing
    print(json.dumps(impact, indent=2))

    # Also print summary
    print("\n=== HIRING IMPACT SUMMARY ===")
    print(f"Hiring {impact['num_engineers']} engineers at ${impact['salary_per_engineer']:,}/year")
    print(f"Monthly burn increase: ${impact['total_monthly_increase']:,.0f}")
    print(f"New burn rate: ${impact['new_burn_monthly']:,.0f}/month")
    print(
        f"Runway change: {impact['current_runway_months']:.1f} → {impact['new_runway_months']:.1f} months"
    )
    print(f"Velocity increase: +{impact['velocity_increase_percent']}%")
    print(f"\n{impact['recommendation']}")


if __name__ == "__main__":
    main()
