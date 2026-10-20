#!/usr/bin/env python3
"""
Brand Validation Script
Validates content against brand guidelines including colors, fonts, tone, and messaging.
"""

import json
import re
from dataclasses import asdict, dataclass


@dataclass
class BrandGuidelines:
    """Brand guidelines configuration"""

    brand_name: str
    primary_colors: list[str]
    secondary_colors: list[str]
    fonts: list[str]
    tone_keywords: list[str]
    prohibited_words: list[str]
    tagline: str | None = None
    logo_usage_rules: dict | None = None


@dataclass
class ValidationResult:
    """Result of brand validation"""

    passed: bool
    score: float
    violations: list[str]
    warnings: list[str]
    suggestions: list[str]


def normalize_color(color: str) -> str:
    """Return a color as uppercase #RRGGBB so equivalent notations compare equal.

    Handles #RGB, #RRGGBB and rgb(r, g, b); anything else is returned uppercased.
    """
    color = color.strip()
    if re.fullmatch(r"#[0-9A-Fa-f]{3}", color):
        return "#" + "".join(ch * 2 for ch in color[1:]).upper()
    rgb = re.fullmatch(
        r"rgb\s*\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*\)", color, re.IGNORECASE
    )
    if rgb and all(int(v) <= 255 for v in rgb.groups()):
        return "#{:02X}{:02X}{:02X}".format(*(int(v) for v in rgb.groups()))
    return color.upper()


class BrandValidator:
    """Validates content against brand guidelines"""

    def __init__(self, guidelines: BrandGuidelines):
        self.guidelines = guidelines

    def validate_colors(self, content: str) -> tuple[list[str], list[str]]:
        """
        Validate color usage in content (hex codes, RGB, color names)
        Returns: (violations, warnings)
        """
        violations = []
        warnings = []

        # Find hex colors
        hex_pattern = r"#[0-9A-Fa-f]{6}|#[0-9A-Fa-f]{3}"
        found_colors = re.findall(hex_pattern, content)

        # Find RGB colors
        rgb_pattern = r"rgb\s*\(\s*\d{1,3}\s*,\s*\d{1,3}\s*,\s*\d{1,3}\s*\)"
        found_colors.extend(re.findall(rgb_pattern, content, re.IGNORECASE))

        approved_colors = self.guidelines.primary_colors + self.guidelines.secondary_colors

        approved_normalized = {normalize_color(c) for c in approved_colors}

        for color in found_colors:
            if normalize_color(color) not in approved_normalized:
                violations.append(f"Unapproved color used: {color}")

        return violations, warnings

    def validate_fonts(self, content: str) -> tuple[list[str], list[str]]:
        """
        Validate font usage in content
        Returns: (violations, warnings)
        """
        violations = []
        warnings = []

        # Common font specification patterns
        font_patterns = [
            r'font-family\s*:\s*["\']?([^;"\']+)["\']?',
            r"font:\s*[^;]*\s+([A-Za-z][A-Za-z\s]+)(?:,|;|\s+\d)",
        ]

        found_fonts = []
        for pattern in font_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            found_fonts.extend(matches)

        for font in found_fonts:
            font_clean = font.strip().lower()
            # Check if any approved font is in the found font string
            if not any(approved.lower() in font_clean for approved in self.guidelines.fonts):
                violations.append(f"Unapproved font used: {font}")

        return violations, warnings

    def validate_tone(self, content: str) -> tuple[list[str], list[str]]:
        """
        Validate tone and messaging
        Returns: (violations, warnings)
        """
        violations = []
        warnings = []

        # Check for prohibited words
        content_lower = content.lower()
        for word in self.guidelines.prohibited_words:
            if word.lower() in content_lower:
                violations.append(f"Prohibited word/phrase used: '{word}'")

        # Check for tone keywords (should have at least some)
        tone_matches = sum(
            1 for keyword in self.guidelines.tone_keywords if keyword.lower() in content_lower
        )

        if tone_matches == 0 and len(content) > 100:
            warnings.append(
                f"Content may not align with brand tone. "
                f"Consider using terms like: {', '.join(self.guidelines.tone_keywords[:5])}"
            )

        return violations, warnings

    def validate_brand_name(self, content: str) -> tuple[list[str], list[str]]:
        """
        Validate brand name usage and capitalization
        Returns: (violations, warnings)
        """
        violations = []
        warnings = []

        # Find all variations of the brand name
        brand_pattern = re.compile(re.escape(self.guidelines.brand_name), re.IGNORECASE)
        matches = brand_pattern.findall(content)

        for match in matches:
            if match != self.guidelines.brand_name:
                violations.append(
                    f"Incorrect brand name capitalization: '{match}' "
                    f"should be '{self.guidelines.brand_name}'"
                )

        return violations, warnings

    def calculate_score(self, violations: list[str], warnings: list[str]) -> float:
        """Calculate compliance score (0-100)"""
        violation_penalty = len(violations) * 10
        warning_penalty = len(warnings) * 3

        score = max(0, 100 - violation_penalty - warning_penalty)
        return round(score, 2)

    def generate_suggestions(self, violations: list[str], warnings: list[str]) -> list[str]:
        """Generate helpful suggestions based on violations and warnings"""
        suggestions = []

        if any("color" in v.lower() for v in violations):
            suggestions.append(
                f"Use approved colors: Primary: {', '.join(self.guidelines.primary_colors[:3])}"
            )

        if any("font" in v.lower() for v in violations):
            suggestions.append(f"Use approved fonts: {', '.join(self.guidelines.fonts)}")

        if any("tone" in w.lower() for w in warnings):
            suggestions.append(
                f"Incorporate brand tone keywords: {', '.join(self.guidelines.tone_keywords[:5])}"
            )

        if any("brand name" in v.lower() for v in violations):
            suggestions.append(f"Always capitalize brand name as: {self.guidelines.brand_name}")

        return suggestions

    def validate(self, content: str) -> ValidationResult:
        """
        Perform complete brand validation
        Returns: ValidationResult
        """
        all_violations = []
        all_warnings = []

        # Run all validation checks
        color_v, color_w = self.validate_colors(content)
        all_violations.extend(color_v)
        all_warnings.extend(color_w)

        font_v, font_w = self.validate_fonts(content)
        all_violations.extend(font_v)
        all_warnings.extend(font_w)

        tone_v, tone_w = self.validate_tone(content)
        all_violations.extend(tone_v)
        all_warnings.extend(tone_w)

        brand_v, brand_w = self.validate_brand_name(content)
        all_violations.extend(brand_v)
        all_warnings.extend(brand_w)

        # Calculate score and generate suggestions
        score = self.calculate_score(all_violations, all_warnings)
        suggestions = self.generate_suggestions(all_violations, all_warnings)

        return ValidationResult(
            passed=len(all_violations) == 0,
            score=score,
            violations=all_violations,
            warnings=all_warnings,
            suggestions=suggestions,
        )


def load_guidelines_from_json(filepath: str) -> BrandGuidelines:
    """
    Load brand guidelines from JSON file

    Args:
        filepath: Path to JSON file containing brand guidelines

    Returns:
        BrandGuidelines object

    Raises:
        FileNotFoundError: If the file doesn't exist
        json.JSONDecodeError: If the file contains invalid JSON
        TypeError: If required fields are missing
    """
    try:
        with open(filepath) as f:
            data = json.load(f)
        return BrandGuidelines(**data)
    except FileNotFoundError as e:
        raise FileNotFoundError(f"Brand guidelines file not found: {filepath}") from e
    except json.JSONDecodeError as e:
        raise json.JSONDecodeError(
            f"Invalid JSON in brand guidelines file: {e.msg}", e.doc, e.pos
        ) from e
    except TypeError as e:
        raise TypeError(f"Missing required fields in brand guidelines: {e}") from e


def get_acme_corporation_guidelines() -> BrandGuidelines:
    """
    Get default Acme Corporation brand guidelines.

    These guidelines match the standards defined in the SKILL.md reference.
    Users should customize these for their own organization.

    Returns:
        BrandGuidelines object with Acme Corporation standards
    """
    return BrandGuidelines(
        brand_name="Acme Corporation",
        primary_colors=["#0066CC", "#003366", "#FFFFFF"],  # Acme Blue, Acme Navy, White
        secondary_colors=[
            "#28A745",
            "#FFC107",
            "#DC3545",
            "#6C757D",
            "#F8F9FA",
        ],  # Success Green, Warning Amber, Error Red, Neutral Gray, Light Gray
        fonts=["Segoe UI", "system-ui", "-apple-system", "sans-serif"],
        tone_keywords=[
            "innovation",
            "excellence",
            "professional",
            "solutions",
            "trusted",
            "reliable",
        ],
        prohibited_words=["cheap", "outdated", "inferior", "unprofessional", "sloppy"],
        tagline="Innovation Through Excellence",
    )


def main():
    """Example usage demonstrating brand validation"""
    # Load Acme Corporation brand guidelines
    # Users should customize this for their own organization
    guidelines = get_acme_corporation_guidelines()

    # Example content to validate (intentionally contains violations for demonstration)
    test_content = """
    Welcome to acme corporation!

    We are a cheap solution provider with outdated technology.

    Our innovation and excellence in professional solutions are trusted by many.

    Contact us at: font-family: 'Comic Sans MS'
    Color scheme: #FF0000
    Background: rgb(255, 0, 0)
    """

    # Validate
    validator = BrandValidator(guidelines)
    result = validator.validate(test_content)

    # Print results
    print("=" * 60)
    print("BRAND VALIDATION REPORT")
    print("=" * 60)
    print(f"\nOverall Status: {'✓ PASSED' if result.passed else '✗ FAILED'}")
    print(f"Compliance Score: {result.score}/100")

    if result.violations:
        print(f"\n❌ VIOLATIONS ({len(result.violations)}):")
        for i, violation in enumerate(result.violations, 1):
            print(f"  {i}. {violation}")

    if result.warnings:
        print(f"\n⚠️  WARNINGS ({len(result.warnings)}):")
        for i, warning in enumerate(result.warnings, 1):
            print(f"  {i}. {warning}")

    if result.suggestions:
        print("\n💡 SUGGESTIONS:")
        for i, suggestion in enumerate(result.suggestions, 1):
            print(f"  {i}. {suggestion}")

    print("\n" + "=" * 60)

    # Return JSON for programmatic use
    return asdict(result)


if __name__ == "__main__":
    main()
