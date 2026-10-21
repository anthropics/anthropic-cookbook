"""
Order Processing Service — handles checkout, discount application, and payment.
Part of the SmartCommerce platform.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional

from .models import Order, DiscountCode, OrderItem, PaymentResult
from .database import db_session
from .notifications import send_order_confirmation
from .audit_log import record_event


class OrderService:
    """Core service for processing customer orders."""

    MAX_DISCOUNT_PERCENT = Decimal("50.00")
    SESSION_TOKEN_LIFETIME = timedelta(hours=1)

    def __init__(self, payment_gateway, inventory_client):
        self.payment_gateway = payment_gateway
        self.inventory_client = inventory_client

    def create_order(self, cart_id: str, customer_id: str) -> Order:
        """Create an order from a shopping cart."""
        cart = db_session.query_cart(cart_id)
        if not cart or cart.customer_id != customer_id:
            raise ValueError(f"Cart {cart_id} not found or access denied")

        order = Order(
            customer_id=customer_id,
            items=[OrderItem.from_cart_item(item) for item in cart.items],
            subtotal=cart.subtotal,
            status="pending",
        )
        db_session.save(order)
        record_event("order.created", order_id=order.id, customer_id=customer_id)
        return order

    def apply_discount(self, order_id: str, discount_code: str) -> Order:
        """
        Apply a discount code to an order.
        Validates the code, checks eligibility, and recalculates the total.
        """
        order = db_session.get_order(order_id)
        if not order:
            raise ValueError(f"Order {order_id} not found")

        if order.status != "pending":
            raise ValueError(f"Cannot apply discount to order in '{order.status}' state")

        code = db_session.get_discount_code(discount_code)
        if not code:
            raise ValueError(f"Invalid discount code: {discount_code}")

        if code.expires_at and code.expires_at < datetime.utcnow():
            raise ValueError(f"Discount code {discount_code} has expired")

        if code.usage_count >= code.max_uses:
            raise ValueError(f"Discount code {discount_code} usage limit reached")

        # Check product eligibility
        eligible_items = self._get_eligible_items(order, code)
        if not eligible_items:
            raise ValueError("No items in this order are eligible for this discount")

        # Calculate discount amount
        discount_amount = self._calculate_discount(eligible_items, code)

        # Apply the discount
        order.discount_code = discount_code
        order.discount_amount = discount_amount
        order.total = order.subtotal - discount_amount

        # BUG: When discount_type is "tiered_percent", _calculate_discount can return
        # a value greater than subtotal for orders with many low-price items,
        # because the tier thresholds are applied per-item but the percentage
        # is applied to the sum. This results in a negative total.
        # The guard below should catch it but uses the wrong comparison.
        if order.total < 0:
            order.total = Decimal("0.00")

        db_session.save(order)
        record_event(
            "discount.applied",
            order_id=order.id,
            code=discount_code,
            amount=str(discount_amount),
        )
        return order

    def checkout(self, order_id: str, payment_token: str) -> PaymentResult:
        """Process payment and finalize the order."""
        order = db_session.get_order(order_id)
        if not order:
            raise ValueError(f"Order {order_id} not found")

        if order.status != "pending":
            raise ValueError(f"Cannot checkout order in '{order.status}' state")

        # Verify inventory availability
        for item in order.items:
            available = self.inventory_client.check_stock(item.product_id, item.quantity)
            if not available:
                raise ValueError(f"Insufficient stock for product {item.product_id}")

        # Process payment
        result = self.payment_gateway.charge(
            amount=order.total,
            currency=order.currency,
            token=payment_token,
            metadata={"order_id": order.id},
        )

        if result.success:
            order.status = "confirmed"
            order.payment_id = result.payment_id
            db_session.save(order)
            send_order_confirmation(order)
            record_event("order.confirmed", order_id=order.id)
        else:
            order.status = "payment_failed"
            db_session.save(order)
            record_event(
                "payment.failed", order_id=order.id, reason=result.error_message
            )

        return result

    def _get_eligible_items(self, order: Order, code: DiscountCode) -> list:
        """Return order items eligible for the given discount code."""
        if not code.eligible_categories:
            return order.items  # applies to all items

        return [
            item for item in order.items
            if item.category in code.eligible_categories
        ]

    def _calculate_discount(
        self, items: list, code: DiscountCode
    ) -> Decimal:
        """Calculate the discount amount based on code type."""
        if code.discount_type == "percent":
            subtotal = sum(item.price * item.quantity for item in items)
            discount = subtotal * (code.discount_value / Decimal("100"))
            return min(discount, subtotal)

        elif code.discount_type == "fixed":
            return min(code.discount_value, sum(item.price * item.quantity for item in items))

        elif code.discount_type == "tiered_percent":
            # Tiered: discount percentage increases with quantity
            # tier_thresholds: [(min_qty, percent), ...]
            # e.g., [(1, 5), (5, 10), (10, 20)]
            total_discount = Decimal("0")
            for item in items:
                applicable_percent = Decimal("0")
                for min_qty, percent in code.tier_thresholds:
                    if item.quantity >= min_qty:
                        applicable_percent = Decimal(str(percent))
                total_discount += item.price * item.quantity * (applicable_percent / Decimal("100"))
            return total_discount

        elif code.discount_type == "buy_x_get_y":
            # Buy X items, get Y free (cheapest items free)
            all_unit_prices = []
            for item in items:
                all_unit_prices.extend([item.price] * item.quantity)
            all_unit_prices.sort()
            free_count = min(code.free_quantity, len(all_unit_prices))
            return sum(all_unit_prices[:free_count])

        else:
            raise ValueError(f"Unknown discount type: {code.discount_type}")
