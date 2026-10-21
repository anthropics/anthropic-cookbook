"""
Discount Engine — validates and manages discount codes.

Recent changes (v2.4.1, 2026-03-28):
  - Added tiered_percent discount type for bulk order promotions
  - Added buy_x_get_y discount type for BOGO campaigns
  - Fixed: max discount cap was not applied to tiered_percent (see SHOP-4891)

Known issue (SHOP-5102, reported 2026-04-08):
  - tiered_percent discounts can exceed order subtotal for orders with
    many low-priced items. Root cause under investigation.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from .models import DiscountCode
from .database import db_session
from .audit_log import record_event


class DiscountEngine:
    """Manages discount code lifecycle and validation."""

    MAX_DISCOUNT_PERCENT = Decimal("50.00")

    def create_code(
        self,
        code: str,
        discount_type: str,
        discount_value: Decimal,
        max_uses: int = 100,
        eligible_categories: Optional[list] = None,
        expires_at: Optional[datetime] = None,
        tier_thresholds: Optional[list] = None,
        free_quantity: Optional[int] = None,
    ) -> DiscountCode:
        """Create a new discount code."""
        if discount_type == "percent" and discount_value > self.MAX_DISCOUNT_PERCENT:
            raise ValueError(
                f"Discount percentage {discount_value}% exceeds maximum "
                f"allowed {self.MAX_DISCOUNT_PERCENT}%"
            )

        # NOTE: MAX_DISCOUNT_PERCENT is NOT enforced for tiered_percent type
        # because the effective percentage depends on item quantities at
        # checkout time. Validation happens in OrderService.apply_discount().
        # TODO(SHOP-5102): Add a cap to tiered_percent in _calculate_discount

        dc = DiscountCode(
            code=code.upper(),
            discount_type=discount_type,
            discount_value=discount_value,
            max_uses=max_uses,
            usage_count=0,
            eligible_categories=eligible_categories,
            expires_at=expires_at,
            tier_thresholds=tier_thresholds,
            free_quantity=free_quantity,
        )
        db_session.save(dc)
        record_event("discount_code.created", code=code, type=discount_type)
        return dc

    def validate_code(self, code: str) -> tuple:
        """
        Validate a discount code.
        Returns (is_valid: bool, reason: str).
        """
        dc = db_session.get_discount_code(code.upper())
        if not dc:
            return False, "Code not found"

        if dc.expires_at and dc.expires_at < datetime.utcnow():
            return False, "Code has expired"

        if dc.usage_count >= dc.max_uses:
            return False, "Usage limit reached"

        return True, "Valid"

    def increment_usage(self, code: str) -> None:
        """Increment the usage counter for a discount code."""
        dc = db_session.get_discount_code(code.upper())
        if dc:
            dc.usage_count += 1
            db_session.save(dc)
            record_event("discount_code.used", code=code, usage_count=dc.usage_count)
