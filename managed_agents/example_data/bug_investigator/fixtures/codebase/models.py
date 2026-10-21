"""
Data models for the SmartCommerce order processing system.
"""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import List, Optional, Tuple
import uuid


@dataclass
class OrderItem:
    product_id: str
    name: str
    price: Decimal
    quantity: int
    category: str

    @classmethod
    def from_cart_item(cls, cart_item):
        return cls(
            product_id=cart_item.product_id,
            name=cart_item.name,
            price=cart_item.price,
            quantity=cart_item.quantity,
            category=cart_item.category,
        )


@dataclass
class DiscountCode:
    code: str
    discount_type: str  # "percent", "fixed", "tiered_percent", "buy_x_get_y"
    discount_value: Decimal
    max_uses: int
    usage_count: int
    eligible_categories: Optional[List[str]] = None
    expires_at: Optional[datetime] = None
    tier_thresholds: Optional[List[Tuple[int, int]]] = None  # [(min_qty, percent), ...]
    free_quantity: Optional[int] = None  # for buy_x_get_y


@dataclass
class Order:
    customer_id: str
    items: List[OrderItem]
    subtotal: Decimal
    status: str = "pending"
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    currency: str = "USD"
    discount_code: Optional[str] = None
    discount_amount: Decimal = Decimal("0")
    total: Optional[Decimal] = None
    payment_id: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self):
        if self.total is None:
            self.total = self.subtotal


@dataclass
class PaymentResult:
    success: bool
    payment_id: Optional[str] = None
    error_message: Optional[str] = None


@dataclass
class AuditEntry:
    event_type: str
    timestamp: datetime
    details: dict
    user_id: Optional[str] = None
