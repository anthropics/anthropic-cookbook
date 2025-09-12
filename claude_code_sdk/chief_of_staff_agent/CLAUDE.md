# CLAUDE.md - Chief of Staff Context

## Company Overview
- **Company**: TechStart Inc
- **Stage**: Series A (Closed $10M in January 2024)
- **Industry**: B2B SaaS - AI-powered developer tools
- **Founded**: 2022
- **HQ**: San Francisco, CA

## Financial Snapshot
- **Monthly Burn Rate**: $500,000
- **Current Runway**: 20 months (until September 2025)
- **ARR**: $2.4M (growing 15% MoM)
- **Cash in Bank**: $10M
- **Revenue per Employee**: $48K

## Team Structure
- **Total Headcount**: 50
- **Engineering**: 25 (50%)
  - Backend: 12
  - Frontend: 8
  - DevOps/SRE: 5
- **Sales & Marketing**: 12 (24%)
- **Product**: 5 (10%)
- **Operations**: 5 (10%)
- **Executive**: 3 (6%)

## Key Metrics
- **Customer Count**: 120 enterprise customers
- **NPS Score**: 72
- **Monthly Churn**: 2.5%
- **CAC**: $15,000
- **LTV**: $85,000
- **CAC Payback Period**: 10 months

## Current Priorities (Q2 2024)
1. **Hiring**: Add 10 engineers to accelerate product development
2. **Product**: Launch AI code review feature by end of Q2
3. **Sales**: Expand into European market
4. **Fundraising**: Begin Series B conversations (target: $30M)

## Compensation Benchmarks
- **Senior Engineer**: $180K - $220K + 0.1-0.3% equity
- **Junior Engineer**: $100K - $130K + 0.05-0.1% equity
- **Engineering Manager**: $200K - $250K + 0.3-0.5% equity
- **VP Engineering**: $250K - $300K + 0.5-1% equity

## Board Composition
- **CEO**: Sarah Chen (Founder)
- **Investor 1**: Mark Williams (Sequoia Capital)
- **Investor 2**: Jennifer Park (Andreessen Horowitz)
- **Independent**: Michael Torres (Former CTO of GitHub)

## Competitive Landscape
- **Main Competitors**: DevTools AI, CodeAssist Pro, SmartDev Inc
- **Our Differentiation**: Superior AI accuracy, 10x faster processing
- **Market Size**: $5B (growing 25% annually)

## Recent Decisions
- Approved hiring 3 senior backend engineers (March 2024)
- Launched freemium tier (February 2024)
- Opened European entity (January 2024)
- Closed Series A funding (January 2024)

## Upcoming Decisions
- Whether to acquire competitor SmartDev Inc ($8M asking price)
- Hiring plan for Q3 (engineering vs. sales focus)
- Office expansion vs. remote-first strategy
- Stock option refresh for early employees

## Risk Factors
- High dependency on AWS (70% of COGS)
- Key engineer retention (3 critical team members)
- Increasing competition from Big Tech
- Potential economic downturn impact on enterprise sales

## Available Scripts

### simple_calculation.py
Quick financial metrics calculator for runway and burn rate analysis.
Script located at `./scripts/simple_calculation.py`

**Usage:**
```bash
python scripts/simple_calculation.py <total_runway> <monthly_burn>
```

**Example:**
```bash
python scripts/simple_calculation.py 10000000 500000
```

**Output:** JSON with monthly_burn, runway_months, total_runway_dollars, quarterly_burn, and burn_rate_daily

Remember: As Chief of Staff, you have access to financial data in the financial_data/ directory and can delegate specialized analysis to your subagents (financial-analyst and recruiter).