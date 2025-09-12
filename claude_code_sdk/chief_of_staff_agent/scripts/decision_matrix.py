#!/usr/bin/env python3
"""
Decision Matrix Tool - Strategic decision framework for complex choices
Custom Python script for the Chief of Staff agent
"""

import argparse
import json


def create_decision_matrix(options: list[dict], criteria: list[dict]) -> dict:
    """Create a weighted decision matrix for strategic choices"""

    results = {"options": [], "winner": None, "analysis": {}}

    for option in options:
        option_scores = {
            "name": option["name"],
            "scores": {},
            "weighted_scores": {},
            "total": 0,
            "pros": [],
            "cons": [],
            "verdict": "",
        }

        # Calculate scores for each criterion
        for criterion in criteria:
            crit_name = criterion["name"]
            weight = criterion["weight"]

            # Get score for this option on this criterion (1-10)
            score = option.get(crit_name, 5)
            weighted = score * weight

            option_scores["scores"][crit_name] = score
            option_scores["weighted_scores"][crit_name] = round(weighted, 2)
            option_scores["total"] += weighted

            # Track pros and cons
            if score >= 8:
                option_scores["pros"].append(f"Excellent {crit_name}")
            elif score >= 6:
                option_scores["pros"].append(f"Good {crit_name}")
            elif score <= 3:
                option_scores["cons"].append(f"Poor {crit_name}")
            elif score <= 5:
                option_scores["cons"].append(f"Weak {crit_name}")

        option_scores["total"] = round(option_scores["total"], 2)

        # Generate verdict
        if option_scores["total"] >= 8:
            option_scores["verdict"] = "STRONGLY RECOMMENDED"
        elif option_scores["total"] >= 6.5:
            option_scores["verdict"] = "RECOMMENDED"
        elif option_scores["total"] >= 5:
            option_scores["verdict"] = "ACCEPTABLE"
        else:
            option_scores["verdict"] = "NOT RECOMMENDED"

        results["options"].append(option_scores)

    # Find winner
    results["options"].sort(key=lambda x: x["total"], reverse=True)
    results["winner"] = results["options"][0]["name"]

    # Generate analysis
    results["analysis"] = generate_analysis(results["options"])

    return results


def generate_analysis(options: list[dict]) -> dict:
    """Generate strategic analysis of the decision"""

    analysis = {
        "clear_winner": False,
        "margin": 0,
        "recommendation": "",
        "key_differentiators": [],
        "risks": [],
    }

    if len(options) >= 2:
        margin = options[0]["total"] - options[1]["total"]
        analysis["margin"] = round(margin, 2)
        analysis["clear_winner"] = margin > 1.5

        if analysis["clear_winner"]:
            analysis["recommendation"] = (
                f"Strongly recommend {options[0]['name']} with {margin:.1f} point advantage"
            )
        elif margin > 0.5:
            analysis["recommendation"] = (
                f"Recommend {options[0]['name']} but consider {options[1]['name']} as viable alternative"
            )
        else:
            analysis["recommendation"] = (
                f"Close decision between {options[0]['name']} and {options[1]['name']} - consider additional factors"
            )

        # Find key differentiators
        top = options[0]
        for criterion in top["scores"]:
            if top["scores"][criterion] >= 8:
                analysis["key_differentiators"].append(criterion)

        # Identify risks
        if top["total"] < 6:
            analysis["risks"].append("Overall score below recommended threshold")
        if len(top["cons"]) > len(top["pros"]):
            analysis["risks"].append("More weaknesses than strengths")

    return analysis


def main():
    parser = argparse.ArgumentParser(description="Strategic decision matrix tool")
    parser.add_argument("--scenario", type=str, help="Predefined scenario")
    parser.add_argument("--input", type=str, help="JSON file with options and criteria")
    parser.add_argument("--format", choices=["json", "text"], default="text")

    args = parser.parse_args()

    # Default scenario: Build vs Buy vs Partner
    if args.scenario == "build-buy-partner":
        options = [
            {
                "name": "Build In-House",
                "cost": 3,  # 1-10, higher is better (so 3 = high cost)
                "time_to_market": 2,  # 2 = slow
                "control": 10,  # 10 = full control
                "quality": 8,  # 8 = high quality potential
                "scalability": 9,  # 9 = very scalable
                "risk": 3,  # 3 = high risk
            },
            {
                "name": "Buy Solution",
                "cost": 5,
                "time_to_market": 9,
                "control": 4,
                "quality": 7,
                "scalability": 6,
                "risk": 7,
            },
            {
                "name": "Strategic Partnership",
                "cost": 7,
                "time_to_market": 7,
                "control": 6,
                "quality": 7,
                "scalability": 8,
                "risk": 5,
            },
        ]

        criteria = [
            {"name": "cost", "weight": 0.20},
            {"name": "time_to_market", "weight": 0.25},
            {"name": "control", "weight": 0.15},
            {"name": "quality", "weight": 0.20},
            {"name": "scalability", "weight": 0.10},
            {"name": "risk", "weight": 0.10},
        ]
    elif args.input:
        with open(args.input) as f:
            data = json.load(f)
            options = data["options"]
            criteria = data["criteria"]
    else:
        # Default hiring scenario
        options = [
            {
                "name": "Hire 3 Senior Engineers",
                "cost": 4,
                "productivity": 9,
                "time_to_impact": 8,
                "team_growth": 7,
                "runway_impact": 3,
            },
            {
                "name": "Hire 5 Junior Engineers",
                "cost": 7,
                "productivity": 5,
                "time_to_impact": 4,
                "team_growth": 9,
                "runway_impact": 5,
            },
        ]
        criteria = [
            {"name": "cost", "weight": 0.25},
            {"name": "productivity", "weight": 0.30},
            {"name": "time_to_impact", "weight": 0.20},
            {"name": "team_growth", "weight": 0.15},
            {"name": "runway_impact", "weight": 0.10},
        ]

    matrix = create_decision_matrix(options, criteria)

    if args.format == "json":
        print(json.dumps(matrix, indent=2))
    else:
        # Text output
        print("🎯 STRATEGIC DECISION MATRIX")
        print("=" * 60)

        print("\nOPTIONS EVALUATED:")
        for i, opt in enumerate(matrix["options"], 1):
            print(f"\n{i}. {opt['name']}")
            print("-" * 40)
            print(f"   Total Score: {opt['total']}/10 - {opt['verdict']}")

            print("   Strengths:")
            for pro in opt["pros"][:3]:
                print(f"   ✓ {pro}")

            if opt["cons"]:
                print("   Weaknesses:")
                for con in opt["cons"][:3]:
                    print(f"   ✗ {con}")

        print("\n" + "=" * 60)
        print("RECOMMENDATION:")
        print("-" * 40)
        analysis = matrix["analysis"]
        print(f"Winner: {matrix['winner']}")
        print(f"Margin: {analysis['margin']} points")
        print(f"\n{analysis['recommendation']}")

        if analysis["key_differentiators"]:
            print(f"\nKey advantages: {', '.join(analysis['key_differentiators'])}")

        if analysis["risks"]:
            print("\n⚠️  Risks to consider:")
            for risk in analysis["risks"]:
                print(f"   - {risk}")


if __name__ == "__main__":
    main()
