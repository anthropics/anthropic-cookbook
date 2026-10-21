"""
batch_classifier.py — Batch item classifier using Claude API

Reads a list of items from a CSV file, visits each website (optional),
and uses Claude to classify each item based on configurable criteria.
Returns a structured JSON output with priority and custom fields.

Use cases:
    - Classify leads by business opportunity
    - Score job candidates by profile match
    - Filter products by market fit
    - Prioritize any list with custom criteria

Usage:
    python batch_classifier.py                        # classify all items
    python batch_classifier.py --limit 10             # test with 10 items
    python batch_classifier.py --input my_list.csv    # custom input file

Input CSV format (minimum required columns):
    name, website

Output:
    classified_output.json
"""

import os
import csv
import json
import time
import argparse
import requests
from bs4 import BeautifulSoup
from anthropic import Anthropic

# ── Configuration ──────────────────────────────────────────────────────────────

PAUSE_BETWEEN_ITEMS = 1   # seconds between API calls (be polite to websites)
WEBSITE_TIMEOUT     = 8   # seconds to wait for a website response
MAX_WEB_CHARS       = 2000  # characters of web content sent to Claude

client = Anthropic()  # reads ANTHROPIC_API_KEY from environment

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; research-bot/1.0)",
    "Accept-Language": "en-US,en;q=0.9",
}

# ── Criteria — customize these for your use case ───────────────────────────────

# These are the questions Claude will answer for each item.
# Modify them to match your classification goal.
CLASSIFICATION_CRITERIA = """
1. What is the main product or service? (one sentence)
2. Who is their target customer?
3. What is the biggest gap or opportunity you see? (be specific)
4. Can they afford a premium solution? (look for signals: quality website, clear pricing, active reviews)
"""

SYSTEM_PROMPT = """You are a business analyst. Your job is to evaluate companies objectively:
what they do, who they serve, and where there is a clear gap or opportunity.
Be specific and concise. Never be vague."""


# ── Web scraping ───────────────────────────────────────────────────────────────

def fetch_website_text(url: str) -> str:
    """Visit a website and return clean text content (up to MAX_WEB_CHARS)."""
    if not url or not url.startswith("http"):
        return ""
    try:
        response = requests.get(url, headers=HEADERS, timeout=WEBSITE_TIMEOUT)
        if response.status_code != 200:
            return ""
        soup = BeautifulSoup(response.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer"]):
            tag.decompose()
        return soup.get_text(separator=" ", strip=True)[:MAX_WEB_CHARS]
    except requests.RequestException:
        return ""


# ── Classification with Claude ─────────────────────────────────────────────────

def classify_item(name: str, website: str, extra_context: str = "") -> dict:
    """
    Send one item to Claude and get back a structured classification.

    Args:
        name: The name of the item (company, product, candidate, etc.)
        website: URL to scrape for context (optional)
        extra_context: Any additional information from your CSV columns

    Returns:
        dict with classification fields and a priority score
    """
    web_content = fetch_website_text(website)

    prompt = f"""Analyze this company and answer the 4 questions below.

COMPANY:
- Name: {name}
- Website: {website if website else "Not available"}
- Additional info: {extra_context if extra_context else "None"}
- Website content: {web_content if web_content else "Could not retrieve"}

QUESTIONS:
{CLASSIFICATION_CRITERIA}

Respond ONLY with valid JSON using this exact structure:
{{
  "main_product": "what they do in one sentence",
  "target_customer": "who they sell to",
  "gap_or_opportunity": "specific gap or opportunity — be concrete, not generic",
  "can_afford_premium": "yes or no",
  "affordability_signals": "what signals from the website suggest their budget level",
  "priority": "high, medium, or low — based on clear opportunity + ability to pay",
  "notes": "any additional relevant observation, or empty string"
}}

JSON only. No explanations."""

    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=400,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}]
        )

        text = response.content[0].text.strip()

        # Handle cases where Claude wraps the JSON in markdown code blocks
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]

        return json.loads(text)

    except (json.JSONDecodeError, Exception):
        return {
            "main_product":         "Classification error",
            "target_customer":      "",
            "gap_or_opportunity":   "",
            "can_afford_premium":   "no",
            "affordability_signals":"",
            "priority":             "low",
            "notes":                "Error processing this item with Claude"
        }


# ── CSV input ──────────────────────────────────────────────────────────────────

def load_items_from_csv(filepath: str) -> list[dict]:
    """
    Load items from a CSV file.
    Required columns: name, website
    Any additional columns are passed to Claude as extra context.
    """
    items = []
    with open(filepath, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            items.append(row)
    return items


# ── Arguments ──────────────────────────────────────────────────────────────────

def parse_args():
    parser = argparse.ArgumentParser(
        description="Batch item classifier using Claude API"
    )
    parser.add_argument(
        "--input",
        type=str,
        default="items.csv",
        help="Path to input CSV file (default: items.csv)"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="classified_output.json",
        help="Path to output JSON file (default: classified_output.json)"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Max number of items to classify (useful for testing)"
    )
    return parser.parse_args()


# ── Main ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    args = parse_args()

    print("Batch Classifier — powered by Claude API")
    print(f"Input:  {args.input}")
    print(f"Output: {args.output}")
    if args.limit:
        print(f"Limit:  {args.limit} items (test mode)")
    print("=" * 60)

    items = load_items_from_csv(args.input)
    if args.limit:
        items = items[:args.limit]

    total = len(items)
    print(f"Items to classify: {total}")
    print("-" * 60)

    results = []
    high_priority = 0

    for i, item in enumerate(items, start=1):
        name    = item.get("name", "Unknown")
        website = item.get("website", "")

        # All columns except name and website become extra context
        extra = {k: v for k, v in item.items() if k not in ("name", "website")}
        extra_context = ", ".join(f"{k}: {v}" for k, v in extra.items() if v)

        print(f"[{i}/{total}] {name[:50]}", end=" ... ", flush=True)

        classification = classify_item(name, website, extra_context)

        results.append({
            "name":           name,
            "website":        website,
            **classification
        })

        if classification.get("priority") == "high":
            high_priority += 1

        print(f"{classification.get('priority', '?').upper()} — {classification.get('gap_or_opportunity', '')[:50]}")

        time.sleep(PAUSE_BETWEEN_ITEMS)

    # Save results
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 60)
    print("CLASSIFICATION COMPLETE")
    print(f"Total processed:  {len(results)}")
    print(f"High priority:    {high_priority}")
    print(f"Output saved to:  {args.output}")
    print("=" * 60)
