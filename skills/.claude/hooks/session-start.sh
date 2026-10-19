#!/bin/bash
# SessionStart Hook - Skills Cookbook Environment Check
# This hook runs at the start of each Claude Code session to verify environment setup

set -e

echo "🔍 Skills Cookbook - Environment Check"
echo "======================================"

# Check if we're in a virtual environment
if [[ -z "$VIRTUAL_ENV" ]]; then
    echo "⚠️  WARNING: No virtual environment detected!"
    echo "   Run: source venv/bin/activate"
    echo ""
fi

# Check if Anthropic SDK is installed and get version
if python -c "import anthropic" 2>/dev/null; then
    SDK_VERSION=$(python -c "import anthropic; print(anthropic.__version__)" 2>/dev/null || echo "unknown")
    echo "✅ Anthropic SDK: $SDK_VERSION"
    # Check for minimum version for Skills support (sort -V compares versions, not strings)
    MIN_SDK_VERSION="0.124.0"
    if [[ "$(printf '%s\n' "$MIN_SDK_VERSION" "$SDK_VERSION" | sort -V | head -1)" != "$MIN_SDK_VERSION" ]]; then
        echo "⚠️  SDK version $SDK_VERSION may be too old (minimum 0.124.0 for the GA Skills and Files APIs)"
        echo "   Run: pip install -U \"anthropic>=0.124.0\""
        echo ""
    fi
else
    echo "❌ Anthropic SDK not installed"
    echo "   Run: pip install -r requirements.txt"
    echo ""
fi

# Check for API key
if [[ -f ".env" ]]; then
    if grep -q "^ANTHROPIC_API_KEY=sk-" .env 2>/dev/null; then
        echo "✅ API key configured in .env"
    else
        echo "⚠️  .env exists but API key may not be set"
        echo "   Check ANTHROPIC_API_KEY in .env"
        echo ""
    fi
else
    echo "⚠️  .env file not found"
    echo "   Run: cp .env.example .env"
    echo "   Then add your ANTHROPIC_API_KEY"
    echo ""
fi

# Check outputs directory
if [[ -d "outputs" ]]; then
    FILE_COUNT=$(find outputs -type f 2>/dev/null | wc -l | tr -d ' ')
    echo "✅ outputs/ directory exists ($FILE_COUNT files)"
else
    echo "ℹ️  Creating outputs/ directory..."
    mkdir -p outputs
fi

# Show current status from plan
if [[ -f "docs/skills_cookbook_plan.md" ]]; then
    echo ""
    echo "📊 Current Status:"
    PHASE_STATUS=$(grep -A1 "^**Phase:**" docs/skills_cookbook_plan.md 2>/dev/null | tail -1 || echo "Unknown")
    echo "   $PHASE_STATUS"
fi

echo ""
echo "======================================"
echo "Ready to work on Skills Cookbook! 🚀"
echo ""
echo "Quick commands:"
echo "  - jupyter notebook              # Launch notebooks"
echo "  - ls outputs/                   # View generated files"
echo "  - cat CLAUDE.md                 # View project guide"
