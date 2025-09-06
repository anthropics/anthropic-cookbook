#!/usr/bin/env python3
"""Check for valid Claude model usage in notebooks."""

import json
import re
import sys
from pathlib import Path
from typing import List, Tuple

from allowed_models import ALLOWED_MODEL_IDS, DEPRECATED_MODELS, RECOMMENDED_MODELS


def extract_model_references(notebook_path: Path) -> List[Tuple[int, str, str]]:
    """Extract model references from a notebook.
    
    Returns list of (cell_index, model_name, context) tuples.
    """
    with open(notebook_path) as f:
        nb = json.load(f)
    
    models = []
    model_pattern = r'["\']?(claude-[\w\-\.]+)["\']?'
    
    for i, cell in enumerate(nb.get('cells', [])):
        if cell['cell_type'] == 'code':
            source = ''.join(cell['source'])
            
            # Find model references
            for match in re.finditer(model_pattern, source):
                model = match.group(1)
                # Get surrounding context (±30 chars)
                start = max(0, match.start() - 30)
                end = min(len(source), match.end() + 30)
                context = source[start:end].replace('\n', ' ')
                models.append((i, model, context))
    
    return models


def validate_models(notebook_path: Path) -> dict:
    """Validate models in a notebook."""
    models = extract_model_references(notebook_path)
    
    issues = {
        'invalid': [],
        'deprecated': [],
        'recommendations': []
    }
    
    for cell_idx, model, context in models:
        if model not in ALLOWED_MODEL_IDS and model not in DEPRECATED_MODELS:
            # Check if it's a variable or partial match
            if not re.match(r'^claude-[\w\-]+\d+$', model):
                continue  # Skip variables like "claude-{version}"
            issues['invalid'].append({
                'cell': cell_idx,
                'model': model,
                'context': context,
                'suggestion': RECOMMENDED_MODELS['default']
            })
        elif model in DEPRECATED_MODELS:
            issues['deprecated'].append({
                'cell': cell_idx,
                'model': model,
                'context': context,
                'suggestion': RECOMMENDED_MODELS['default']
            })
    
    # Add general recommendations
    if models and all(m[1] not in ['claude-3-5-haiku-latest', 'claude-3-5-haiku-20241022'] 
                      for m in models):
        issues['recommendations'].append(
            "Consider using 'claude-3-5-haiku-latest' for test examples to minimize costs"
        )
    
    return issues


def main():
    """Check all notebooks for model usage."""
    import argparse
    
    parser = argparse.ArgumentParser()
    parser.add_argument('--github-output', action='store_true',
                       help='Format output for GitHub Actions')
    args = parser.parse_args()
    
    has_issues = False
    
    for notebook in Path('skills').glob('**/*.ipynb'):
        issues = validate_models(notebook)
        
        if any(issues.values()):
            has_issues = True
            print(f"\n📓 {notebook}:")
            
            if issues['invalid']:
                print("  ❌ Invalid models:")
                for issue in issues['invalid']:
                    print(f"    Cell {issue['cell']}: {issue['model']}")
                    print(f"      Suggest: {issue['suggestion']}")
            
            if issues['deprecated']:
                print("  ⚠️  Deprecated models:")
                for issue in issues['deprecated']:
                    print(f"    Cell {issue['cell']}: {issue['model']}")
                    print(f"      Update to: {issue['suggestion']}")
            
            if issues['recommendations']:
                print("  💡 Recommendations:")
                for rec in issues['recommendations']:
                    print(f"    - {rec}")
    
    if args.github_output and has_issues:
        print("::error::Found model validation issues")
    
    return 1 if has_issues else 0


if __name__ == "__main__":
    sys.exit(main())