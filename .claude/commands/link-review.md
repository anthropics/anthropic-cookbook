---
allowed-tools: Bash(gh pr comment:*),Bash(gh pr diff:*),Bash(gh pr view:*)
description: Review links in changed files for quality and security issues
---

Review the links in the changed files and check for potential issues:

## Link Quality Checks
1. **Broken Links**: Identify any links that might be broken or malformed
2. **Outdated Links**: Check for links to deprecated resources or old documentation
3. **Security**: Ensure no links to suspicious or potentially harmful sites
4. **Best Practices**: 
   - Links should use HTTPS where possible
   - Internal links should use relative paths
   - External links should be to stable, reputable sources

## Specific Checks for Anthropic Content
- Links to Claude documentation should point to the latest versions
- API documentation links should be current
- Model documentation should reference current models, not deprecated ones
- GitHub links should use the correct repository paths

## Report Format
Provide a clear summary with:
- ✅ Valid and well-formed links
- ⚠️ Links that might need attention (e.g., HTTP instead of HTTPS)
- ❌ Broken or problematic links that must be fixed

If all links look good, provide a brief confirmation.

**IMPORTANT: Post your review as a comment on the pull request using the command: `gh pr comment $PR_NUMBER --body "your review content"`**