# Skill Forge Integration Guide

## Overview
This guide shows how to integrate Skill Forge with Anthropic's Claude API for browser automation.

## Prerequisites
- Python 3.12+
- Claude API key
- skill-forge package

## Quick Start
```python
from skill_forge import SkillRegistry

registry = SkillRegistry()
skills = registry.query('navigate to settings page')
print(skills[0].procedure)
```

## Learn More
See the [Skill Forge documentation](https://github.com/anthropics/skill-forge) for details.
