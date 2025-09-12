#!/usr/bin/env python3
"""
Talent Scorer Tool - Evaluate and rank candidates based on multiple criteria
Custom Python tool for the Recruiter subagent
"""

import argparse
import json


def score_candidate(candidate: dict) -> dict:
    """Score a candidate based on weighted criteria"""

    weights = {
        "technical_skills": 0.30,
        "experience_years": 0.20,
        "startup_experience": 0.15,
        "education": 0.10,
        "culture_fit": 0.15,
        "salary_fit": 0.10,
    }

    scores = {}

    # Technical skills (0-100)
    tech_match = candidate.get("tech_skills_match", 70)
    scores["technical_skills"] = min(100, tech_match)

    # Experience (0-100, peaks at 8 years)
    years = candidate.get("years_experience", 5)
    if years <= 2:
        scores["experience_years"] = 40
    elif years <= 5:
        scores["experience_years"] = 70
    elif years <= 8:
        scores["experience_years"] = 90
    else:
        scores["experience_years"] = 85  # Slight decline for overqualified

    # Startup experience (0-100)
    scores["startup_experience"] = 100 if candidate.get("has_startup_exp", False) else 50

    # Education (0-100)
    education = candidate.get("education", "bachelors")
    edu_scores = {"high_school": 40, "bachelors": 70, "masters": 85, "phd": 90}
    scores["education"] = edu_scores.get(education, 70)

    # Culture fit (0-100)
    scores["culture_fit"] = candidate.get("culture_score", 75)

    # Salary fit (0-100, penalize if too high or too low)
    salary = candidate.get("salary_expectation", 150000)
    target = candidate.get("target_salary", 160000)
    diff_pct = abs(salary - target) / target
    scores["salary_fit"] = max(0, 100 - (diff_pct * 200))

    # Calculate weighted total
    total = sum(scores[k] * weights[k] for k in weights)

    return {
        "name": candidate.get("name", "Unknown"),
        "total_score": round(total, 1),
        "scores": scores,
        "recommendation": get_recommendation(total),
        "risk_factors": identify_risks(candidate, scores),
    }


def get_recommendation(score: float) -> str:
    """Generate hiring recommendation based on score"""
    if score >= 85:
        return "STRONG HIRE - Extend offer immediately"
    elif score >= 75:
        return "HIRE - Good candidate, proceed with offer"
    elif score >= 65:
        return "MAYBE - Consider if no better options"
    elif score >= 50:
        return "WEAK - Significant concerns, likely pass"
    else:
        return "NO HIRE - Does not meet requirements"


def identify_risks(candidate: dict, scores: dict) -> list[str]:
    """Identify potential risk factors"""
    risks = []

    if scores["technical_skills"] < 60:
        risks.append("Technical skills below requirement")

    if candidate.get("years_experience", 0) < 2:
        risks.append("Limited experience, will need mentorship")

    if not candidate.get("has_startup_exp", False):
        risks.append("No startup experience, may struggle with ambiguity")

    if scores["salary_fit"] < 50:
        risks.append("Salary expectations misaligned")

    if candidate.get("notice_period_days", 14) > 30:
        risks.append(f"Long notice period: {candidate.get('notice_period_days')} days")

    return risks


def rank_candidates(candidates: list[dict]) -> list[dict]:
    """Rank multiple candidates"""
    scored = [score_candidate(c) for c in candidates]
    return sorted(scored, key=lambda x: x["total_score"], reverse=True)


def main():
    parser = argparse.ArgumentParser(description="Candidate scoring tool")
    parser.add_argument("--input", type=str, help="JSON file with candidate data")
    parser.add_argument("--name", type=str, help="Candidate name")
    parser.add_argument("--years", type=int, default=5, help="Years of experience")
    parser.add_argument("--tech-match", type=int, default=70, help="Technical skills match (0-100)")
    parser.add_argument("--salary", type=int, default=150000, help="Salary expectation")
    parser.add_argument("--startup", action="store_true", help="Has startup experience")
    parser.add_argument("--format", choices=["json", "text"], default="text")

    args = parser.parse_args()

    if args.input:
        # Score multiple candidates from file
        with open(args.input) as f:
            candidates = json.load(f)
        results = rank_candidates(candidates)
    else:
        # Score single candidate from args
        candidate = {
            "name": args.name or "Candidate",
            "years_experience": args.years,
            "tech_skills_match": args.tech_match,
            "salary_expectation": args.salary,
            "has_startup_exp": args.startup,
            "target_salary": 160000,
            "culture_score": 75,
            "education": "bachelors",
        }
        results = [score_candidate(candidate)]

    if args.format == "json":
        print(json.dumps(results, indent=2))
    else:
        # Text output
        print("🎯 CANDIDATE EVALUATION")
        print("=" * 50)

        for i, result in enumerate(results, 1):
            print(f"\n#{i}. {result['name']}")
            print("-" * 30)
            print(f"Overall Score: {result['total_score']}/100")
            print(f"Recommendation: {result['recommendation']}")

            print("\nScores by Category:")
            for category, score in result["scores"].items():
                print(f"  {category.replace('_', ' ').title()}: {score:.0f}/100")

            if result["risk_factors"]:
                print("\n⚠️  Risk Factors:")
                for risk in result["risk_factors"]:
                    print(f"  - {risk}")

        if len(results) > 1:
            print("\n" + "=" * 50)
            print("RANKING SUMMARY:")
            for i, r in enumerate(results[:3], 1):
                print(
                    f"{i}. {r['name']}: {r['total_score']:.1f} - {r['recommendation'].split(' - ')[0]}"
                )


if __name__ == "__main__":
    main()
