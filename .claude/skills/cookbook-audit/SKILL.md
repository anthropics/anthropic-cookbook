---
name: cookbook-audit
description: Audit an Anthropic Cookbook notebook based on a rubric. Use whenever a notebook review or audit is requested.
---

# Cookbook Audit

## Instructions

Review the requested Cookbook notebook using the guidelines and rubrics in `style_guide.md`. Provide a score based on scoring guidelines and recommendations on improving the cookbook.

The style guide provides detailed templates and examples for:
- Problem-focused introductions with Terminal Learning Objectives (TLOs) and Enabling Learning Objectives (ELOs)
- Prerequisites and setup patterns
- Core content structure
- Conclusions that map back to learning objectives

**IMPORTANT**: Always read `style_guide.md` first before conducting an audit. The style guide contains the canonical templates and good/bad examples to reference.

## Workflow

Follow these steps for a comprehensive audit:

1. **Read the style guide**: First review `style_guide.md` to understand current best practices
2. **Identify the notebook**: Ask user for path if not provided
3. **Run automated checks**: Use `python3 validate_notebook.py <path>` to catch technical issues and generate markdown
   - The script automatically runs detect-secrets to scan for hardcoded API keys and credentials
   - Uses custom patterns defined in `scripts/detect-secrets/plugins.py`
   - Checks against baseline at `scripts/detect-secrets/.secrets.baseline`
4. **Review markdown output**: The script generates a markdown file in the `tmp/` folder for easier review (saves context vs raw .ipynb)
   - The tmp/ folder is gitignored to avoid committing review artifacts
   - Markdown includes code cells but excludes outputs for cleaner review
5. **Manual review**: Read through the markdown version evaluating against style guide and rubric
6. **Score each dimension**: Apply scoring guidelines objectively
7. **Generate report**: Follow the audit report format below
8. **Provide specific examples**: Show concrete improvements with line references using the style guide templates

## Audit Report Format

Present your audit using this structure:

### Executive Summary
- **Overall Score**: X/20
- **Key Strengths** (2-3 bullet points)
- **Critical Issues** (2-3 bullet points)

### Detailed Scoring

#### 1. Narrative Quality: X/5
[Brief justification with specific examples]

#### 2. Code Quality: X/5
[Brief justification with specific examples]

#### 3. Technical Accuracy: X/5
[Brief justification with specific examples]

#### 4. Actionability & Understanding: X/5
[Brief justification with specific examples]

### Specific Recommendations

[Prioritized, actionable list of improvements with references to specific sections]

### Examples & Suggestions

[Show specific excerpts from the notebook with concrete suggestions for improvement]

## Quick Reference Checklist

Use this to ensure comprehensive coverage:

**Introduction** (See style_guide.md Section 1)
- [ ] Hooks with the problem being solved (1-2 sentences)
- [ ] Explains why it matters (1-2 sentences)
- [ ] Lists learning objectives as bullet points (2-4 TLOs/ELOs)
- [ ] Focuses on value delivered, not machinery built
- [ ] Optional: mentions broader applications (1 sentence)

**Prerequisites & Setup** (See style_guide.md Section 2)
- [ ] Lists required knowledge clearly
- [ ] Lists required tools (Python version, API keys)
- [ ] Mentions recommended background if applicable
- [ ] Uses %%capture for pip install to suppress output
- [ ] Uses dotenv.load_dotenv() not os.environ
- [ ] Defines MODEL constant at top
- [ ] Groups related installs in single command

**Structure & Organization**
- [ ] Has logical section progression
- [ ] Each section teaches through demonstration
- [ ] Code blocks have explanatory text before them
- [ ] Includes what we learned after code blocks
- [ ] Uses headers to break up sections

**Conclusion** (See style_guide.md Section 4)
- [ ] Maps back to learning objectives
- [ ] Summarizes what was accomplished
- [ ] Suggests ways to apply lessons to user's context
- [ ] Points to next steps or related resources

**Code Quality**
- [ ] All code blocks have explanatory text before them
- [ ] No hardcoded API keys (automatically checked by detect-secrets)
- [ ] Meaningful variable names
- [ ] Comments explain "why" not "what"
- [ ] Follows language best practices
- [ ] Model name defined as constant at top of notebook

**Output Management**
- [ ] pip install logs suppressed with %%capture
- [ ] No verbose debug output
- [ ] Shows relevant API responses
- [ ] Stack traces only when demonstrating error handling

**Content Quality**
- [ ] Explains why approaches work
- [ ] Discusses when to use this approach
- [ ] Mentions limitations/considerations
- [ ] Provides transferable knowledge
- [ ] Appropriate model selection

**Technical Requirements**
- [ ] Executable without modification (except API keys)
- [ ] Uses non-deprecated API patterns
- [ ] Uses the latest model in each family (claude-opus-5-5, claude-sonnet-5-5, claude-fable-5-1, claude-haiku-4-5); a superseded-but-still-served ID (e.g. claude-opus-5, claude-sonnet-5) is a warning unless pinned on purpose, a retired ID (e.g. claude-3-*) is blocking
- [ ] Uses non-dated model aliases (never dated IDs like claude-sonnet-4-5-20250929)
- [ ] Model name defined as constant at top of notebook
- [ ] Includes dependency specifications
- [ ] Assigned to primary category
- [ ] Has relevant tags

### Content Philosophy: Action + Understanding

Cookbooks are primarily action-oriented but strategically incorporate understanding and informed by Diataxis framework.

**Core Principles:**
- **Practical focus**: Show users how to accomplish specific tasks with working code
- **Problem-first framing**: Lead with the problem being solved and value delivered, not the machinery
- **Builder's perspective**: Written from the user's point of view, solving real problems
- **Agency-building**: Help users understand why approaches work, not just how
- **Transferable knowledge**: Teach patterns and principles that apply beyond the specific example
- **Critical thinking**: Encourage users to question outputs, recognize limitations, make informed choices
- **Learning contracts**: State learning objectives upfront, then map back to them in conclusions

### What Makes a Good Cookbook

A good cookbook doesn't just help users solve today's problem, it also helps them understand the underlying principles behind the solutions, encouraging them to recognize when and how to adapt approaches. Users will be able to make more informed decisions about AI system design, develop judgement about model outputs, and build skills that transfer to future AI systems.

### What Cookbooks Are NOT

Cookbooks are not pure tutorials: We assume users have basic technical skills and API familiarity. We clearly state prerequisites in our cookbooks, and direct users to the Academy to learn more on topics.
They are not comprehensive explanations: We don't teach transformer architecture or probability theory. We need to understand that our users are following our cookbooks to solve problems they are facing today. They are busy, in the midst of learning or building, and want to be able to use what they learn to solve their immediate needs.
Cookbooks are not reference docs: We don't exhaustively document every parameter, we link to appropriate resources in our documentation as needed.
Cookbooks are not simple tips and tricks: We don't teach "hacks" that only work for the current model generation. We don't over-promise and under-deliver.
Cookbooks are not production-ready code: They showcase use cases and capabilities, not production patterns. Excessive error handling is not required.

### Style Guidelines

#### Voice & Tone
- Educational and agency-building
- Professional but approachable
- Respectful of user intelligence and time
- Either second person ("you") or first person plural ("we") - be consistent within a notebook

#### Writing Quality
- Clear, concise explanations
- Active voice preferred
- Short paragraphs (3-5 sentences)
- Avoid jargon without definition
- Use headers to break up sections

#### Code Presentation
- **Always explain before showing**: Every code block should be preceded by explanatory text
- **Explain after running**: Include what we learned after code blocks execute
- **Comments explain why, not what**: Use meaningful variable names
- **Use constants**: Define MODEL as a constant at the top
- **Good habits**: Use `dotenv.load_dotenv()` instead of `os.environ`

#### Output Handling
**Remove extraneous output** with %%capture:
- pip install logs (always suppress these)
- Verbose debug statements
- Lengthy stack traces (unless demonstrating error handling)

**Show relevant output**:
- API responses that demonstrate functionality
- Examples of successful execution

### Structural Requirements

**See style_guide.md for detailed templates and examples**

#### 1. Introduction (Required)
Must include:
- **Problem hook** (1-2 sentences): What problem are we solving?
- **Why it matters** (1-2 sentences): Why is this important?
- **Learning objectives** (2-4 bullet points): "By the end of this cookbook, you'll be able to..."
  - Use action verbs (Build, Implement, Deploy, etc.)
  - Be specific about capabilities
  - Include context/constraints
- **Optional**: Broader applications (1 sentence)

❌ **Avoid**: Leading with machinery ("We will build a research agent...")
✅ **Do**: Lead with problem/value ("Your team spends hours triaging CI failures...")

#### 2. Prerequisites & Setup (Required)
Must include:
- **Required Knowledge**: Technical skills needed
- **Required Tools**: Python version, API keys with links
- **Recommended**: Optional background that helps
- **Setup**: Step-by-step with explanations
  - Use `%%capture` for pip installs
  - Use `dotenv.load_dotenv()` not `os.environ`
  - Define `MODEL` constant at top

#### 3. Main Content (Required)
Organized by logical steps or phases, each with:
- Clear section headers
- **Explanatory text before code blocks** (what we're about to do)
- Code examples
- **Explanatory text after code blocks** (what we learned)
- Expected outputs (where relevant)
- Optional: Understanding callouts (why it works, when to use, limitations)

#### 4. Conclusion (Recommended)
Must include:
- **Recap**: Map back to learning objectives
- **What was accomplished**: Summary of key points
- **Application guidance**: How to apply lessons to user's context
- **Next steps**: Related resources or ideas to pursue

❌ **Avoid**: Generic summaries ("We've demonstrated how the SDK enables...")
✅ **Do**: Actionable guidance ("Consider applying this to X... Next, try Y...")

#### Optional Sections
- **How It Works**: Brief explanation of underlying mechanism
- **When to Use This**: Appropriate use cases and contexts
- **Limitations & Considerations**: Caveats, failure modes, constraints
- **Troubleshooting**: Common issues and solutions
- **Variations**: Alternative approaches or extensions
- **Performance Notes**: Optimization considerations
- **Further Reading**: Links to relevant docs, papers, or deeper explanations

### Common Anti-Patterns to Flag

Refer to style_guide.md for detailed good/bad examples. Watch for these issues:

#### Introduction Anti-Patterns
❌ Leading with machinery: "We will build a research agent using the Claude SDK..."
❌ Feature dumps: Listing SDK methods or tool capabilities
❌ Vague learning objectives: "Learn about agents" or "Understand the API"
✅ Problem-first framing with specific, actionable learning objectives

#### Setup Anti-Patterns
❌ Noisy pip install output without `%%capture`
❌ Multiple separate pip install commands
❌ Using `os.environ["API_KEY"] = "your_key"` instead of dotenv
❌ Hardcoding model names throughout instead of using a MODEL constant
✅ Clean setup with grouped installs, dotenv, and constants

#### Code Presentation Anti-Patterns
❌ Code blocks without explanatory text before them
❌ No explanation of what we learned after running code
❌ Comments that explain "what" the code does (code should be self-documenting)
❌ Over-explaining obvious code
✅ Context before code, insights after code, comments explain "why"

#### Conclusion Anti-Patterns
❌ Generic summaries: "We've demonstrated how the SDK enables..."
❌ Simply restating what the notebook did without guidance
❌ Not mapping back to the stated learning objectives
✅ Actionable guidance on applying lessons to user's specific context