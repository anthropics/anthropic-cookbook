#!/usr/bin/env python3
"""Validate notebook structure and content."""

import json
import sys
from pathlib import Path


def validate_notebook(path: Path) -> list:
    """Validate a single notebook."""
    issues = []
    
    with open(path) as f:
        nb = json.load(f)
    
    # Check for empty cells
    for i, cell in enumerate(nb['cells']):
        if not cell.get('source'):
            issues.append(f"Cell {i}: Empty cell found")
    
    # Check for error outputs
    for i, cell in enumerate(nb['cells']):
        if cell['cell_type'] == 'code':
            for output in cell.get('outputs', []):
                if output.get('output_type') == 'error':
                    issues.append(f"Cell {i}: Contains error output")
    
    # Check for hardcoded API keys
    for i, cell in enumerate(nb['cells']):
        if cell['cell_type'] == 'code':
            source = ''.join(cell['source'])
            if 'sk-ant-' in source or 'anthropic_api_key=' in source.lower():
                issues.append(f"Cell {i}: Potential hardcoded API key")
            if 'api_key' in source.lower() and 'os.environ' not in source and 'getenv' not in source:
                issues.append(f"Cell {i}: API key not using environment variable")
    
    return issues


def main():
    """Check all notebooks."""
    has_issues = False
    
    for notebook in Path('skills').glob('**/*.ipynb'):
        issues = validate_notebook(notebook)
        if issues:
            has_issues = True
            print(f"\n❌ {notebook}:")
            for issue in issues:
                print(f"  - {issue}")
    
    if not has_issues:
        print("✅ All notebooks validated successfully")
    
    sys.exit(1 if has_issues else 0)


if __name__ == "__main__":
    main()