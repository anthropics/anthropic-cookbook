#!/usr/bin/env python3
"""
Financial Forecast Tool - Advanced financial modeling for strategic decisions
Custom Python tool executed via Bash by the Chief of Staff agent
"""

import argparse
import json


def forecast_financials(current_arr, growth_rate, months, burn_rate):
    """Generate financial forecast with multiple scenarios"""

    forecasts = {"base_case": [], "optimistic": [], "pessimistic": [], "metrics": {}}

    # Base case
    arr = current_arr
    for month in range(1, months + 1):
        arr = arr * (1 + growth_rate)
        monthly_revenue = arr / 12
        net_burn = burn_rate - monthly_revenue
        runway = -1 if net_burn <= 0 else (10_000_000 / net_burn)  # Assuming $10M in bank

        forecasts["base_case"].append(
            {
                "month": month,
                "arr": round(arr),
                "monthly_revenue": round(monthly_revenue),
                "net_burn": round(net_burn),
                "runway_months": round(runway, 1) if runway > 0 else "infinite",
            }
        )

    # Optimistic (1.5x growth)
    arr = current_arr
    for month in range(1, months + 1):
        arr = arr * (1 + growth_rate * 1.5)
        forecasts["optimistic"].append({"month": month, "arr": round(arr)})

    # Pessimistic (0.5x growth)
    arr = current_arr
    for month in range(1, months + 1):
        arr = arr * (1 + growth_rate * 0.5)
        forecasts["pessimistic"].append({"month": month, "arr": round(arr)})

    # Key metrics
    forecasts["metrics"] = {
        "months_to_profitability": calculate_profitability_date(forecasts["base_case"]),
        "cash_required": calculate_cash_needed(forecasts["base_case"]),
        "break_even_arr": burn_rate * 12,
        "current_burn_multiple": round(burn_rate / (current_arr / 12), 2),
    }

    return forecasts


def calculate_profitability_date(forecast):
    """Find when company becomes profitable"""
    for entry in forecast:
        if entry["net_burn"] <= 0:
            return entry["month"]
    return -1  # Not profitable in forecast period


def calculate_cash_needed(forecast):
    """Calculate total cash needed until profitability"""
    total_burn = 0
    for entry in forecast:
        if entry["net_burn"] > 0:
            total_burn += entry["net_burn"]
        else:
            break
    return round(total_burn)


def main():
    parser = argparse.ArgumentParser(description="Financial forecasting tool")
    parser.add_argument("--arr", type=float, default=2400000, help="Current ARR")
    parser.add_argument("--growth", type=float, default=0.15, help="Monthly growth rate")
    parser.add_argument("--months", type=int, default=12, help="Forecast period")
    parser.add_argument("--burn", type=float, default=500000, help="Monthly burn rate")
    parser.add_argument("--format", choices=["json", "text"], default="text", help="Output format")

    args = parser.parse_args()

    forecast = forecast_financials(args.arr, args.growth, args.months, args.burn)

    if args.format == "json":
        print(json.dumps(forecast, indent=2))
    else:
        # Text output for human reading
        print("📊 FINANCIAL FORECAST")
        print("=" * 50)
        print(f"Current ARR: ${args.arr:,.0f}")
        print(f"Growth Rate: {args.growth * 100:.1f}% monthly")
        print(f"Burn Rate: ${args.burn:,.0f}/month")
        print()

        print("BASE CASE PROJECTION:")
        print("-" * 30)
        for i in [2, 5, 11]:  # Show months 3, 6, 12
            if i < len(forecast["base_case"]):
                m = forecast["base_case"][i]
                print(f"Month {m['month']:2}: ARR ${m['arr']:,} | Runway {m['runway_months']}")

        print()
        print("KEY METRICS:")
        print("-" * 30)
        metrics = forecast["metrics"]
        if metrics["months_to_profitability"] > 0:
            print(f"Profitability: Month {metrics['months_to_profitability']}")
        else:
            print("Profitability: Not in forecast period")
        print(f"Cash Needed: ${metrics['cash_required']:,}")
        print(f"Burn Multiple: {metrics['current_burn_multiple']}x")

        print()
        print("SCENARIO ANALYSIS:")
        print("-" * 30)
        last_base = forecast["base_case"][-1]["arr"]
        last_opt = forecast["optimistic"][-1]["arr"]
        last_pess = forecast["pessimistic"][-1]["arr"]
        print(f"12-Month ARR: ${last_pess:,} to ${last_opt:,}")
        print(f"Range: {((last_opt - last_pess) / last_base * 100):.0f}% variance")


if __name__ == "__main__":
    main()
