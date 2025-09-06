"""Allowed Claude model IDs for the cookbook."""

import json
import os
import re
import time
from pathlib import Path
from typing import Set, Optional
import urllib.request
import urllib.error


def fetch_models_from_docs() -> Optional[dict]:
    """Fetch the latest model list from Anthropic docs.
    
    Returns dict with 'allowed' and 'deprecated' sets, or None if fetch fails.
    """
    cache_file = Path(__file__).parent / '.model_cache.json'
    cache_max_age = 86400  # 24 hours
    
    # Check cache first
    if cache_file.exists():
        cache_age = time.time() - cache_file.stat().st_mtime
        if cache_age < cache_max_age:
            with open(cache_file) as f:
                return json.load(f)
    
    try:
        # Fetch the docs page
        url = "https://docs.anthropic.com/en/docs/about-claude/models/overview.md"
        req = urllib.request.Request(url, headers={'User-Agent': 'anthropic-cookbook'})
        with urllib.request.urlopen(req, timeout=10) as response:
            content = response.read().decode('utf-8')
        
        # Extract model IDs using regex
        # Look for patterns like "claude-" followed by version info
        model_pattern = r'"(claude-[\w\-]+(?:\d{8})?)"'
        matches = re.findall(model_pattern, content)
        
        # Filter to valid model formats
        allowed = set()
        for model in matches:
            # Valid patterns: claude-X-Y-latest, claude-X-Y-YYYYMMDD, claude-name-X-Y
            if re.match(r'^claude-[\w\-]+-\d+-\d+(?:-\d{8}|-latest)?$', model) or \
               re.match(r'^claude-[\w]+-\d+-\d+$', model):
                allowed.add(model)
        
        # Identify deprecated models (3.5 sonnet and 3 opus)
        deprecated = {m for m in allowed if 'claude-3-5-sonnet' in m or 'claude-3-opus' in m}
        
        # Cache the results
        result = {
            'allowed': list(allowed),
            'deprecated': list(deprecated),
            'fetched_at': time.time()
        }
        with open(cache_file, 'w') as f:
            json.dump(result, f, indent=2)
        
        return result
        
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
        print(f"Warning: Could not fetch latest models from docs: {e}")
        return None


# Try to fetch latest models, fall back to hardcoded if it fails
_fetched = fetch_models_from_docs()

if _fetched:
    ALLOWED_MODEL_IDS = set(_fetched['allowed'])
    DEPRECATED_MODELS = set(_fetched['deprecated'])
else:
    # Fallback to hardcoded list if fetch fails
    ALLOWED_MODEL_IDS = {
        # Opus 4.1 (Latest)
        "claude-opus-4-1-20250805",
        "claude-opus-4-1",  # Alias
        
        # Opus 4.0
        "claude-opus-4-20250514",
        "claude-opus-4-0",  # Alias
        
        # Sonnet 4.0
        "claude-sonnet-4-20250514",
        "claude-sonnet-4-0",  # Alias
        
        # Sonnet 3.7
        "claude-3-7-sonnet-20250219",
        "claude-3-7-sonnet-latest",  # Alias
        
        # Haiku 3.5
        "claude-3-5-haiku-20241022",
        "claude-3-5-haiku-latest",  # Alias
        
        # Haiku 3.0
        "claude-3-haiku-20240307",
    }
    
    DEPRECATED_MODELS = {
        "claude-3-5-sonnet-20241022",
        "claude-3-5-sonnet-20240620",
        "claude-3-opus-20240229",
        "claude-3-5-sonnet-latest",
        "claude-3-opus-latest",
    }

# Model recommendations for different use cases
RECOMMENDED_MODELS = {
    "default": "claude-3-7-sonnet-latest",
    "fast": "claude-3-5-haiku-latest",
    "powerful": "claude-opus-4-1",
    "testing": "claude-3-5-haiku-latest",
}