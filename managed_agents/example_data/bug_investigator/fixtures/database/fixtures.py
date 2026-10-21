"""
Database fixtures — simulated query results for the cookbook demo.

In production, these would come from your actual database via a read-only
query tool. For the cookbook, we return pre-built results so anyone can
run the demo without a database.
"""

# The bug report that triggers the investigation (single source of truth)
BUG_REPORT = {
    "id": "SHOP-5102",
    "summary": "Checkout crashes with negative total when applying discount code BULK25",
    "priority": "Critical",
    "reporter": "support-agent-maria",
    "created": "2026-04-08T14:23:00Z",
    "description": (
        "Customer reported checkout failure. After applying discount code BULK25 "
        "to an order with 15 items (small accessories, $2-5 each), the checkout "
        "page displayed 'Payment Error: Invalid amount' and the order could not "
        "be completed.\n\n"
        "Steps to reproduce:\n"
        "1. Add 15+ items from the 'Accessories' category ($2-5 price range)\n"
        "2. Apply discount code BULK25\n"
        "3. Click Checkout\n"
        "4. Error: 'Payment Error: Invalid amount'\n\n"
        "Environment: Production (us-east-1)\n"
        "Customer ID: CUST-88291\n"
        "Order ID: ORD-20260408-7721\n\n"
        "Impact: Customer unable to complete purchase. 3 additional reports "
        "received in the last hour from different customers using BULK25."
    ),
}

# Past similar incidents for the agent to find
PAST_INCIDENTS = [
    {
        "id": "SHOP-4891",
        "summary": "Max discount cap not applied to tiered_percent codes",
        "status": "Resolved",
        "resolved_date": "2026-03-28",
        "root_cause": "tiered_percent discount type added without MAX_DISCOUNT_PERCENT guard",
        "resolution": "Added cap logic in OrderService._calculate_discount",
    },
    {
        "id": "SHOP-4650",
        "summary": "Fixed discount exceeds order subtotal for small orders",
        "status": "Resolved",
        "resolved_date": "2026-02-15",
        "root_cause": "Fixed $50 discount applied to $30 order = negative total",
        "resolution": "Added min() guard in _calculate_discount for fixed type",
    },
    {
        "id": "SHOP-3998",
        "summary": "Percent discount applied twice on retry",
        "status": "Resolved",
        "resolved_date": "2025-11-02",
        "root_cause": "Idempotency check missing in apply_discount",
        "resolution": "Added check for existing discount_code on order before applying",
    },
]

# Fixture data — simulates read-only database query results (keys matched as substrings of SQL)
FIXTURE_DB = {
    "SELECT * FROM orders WHERE order_id = 'ORD-20260408-7721'": {
        "columns": ["order_id", "customer_id", "status", "subtotal", "discount_code",
                     "discount_amount", "total", "currency", "created_at"],
        "rows": [["ORD-20260408-7721", "CUST-88291", "pending", "52.45", "BULK25",
                  "78.68", "-26.23", "USD", "2026-04-08 14:20:33"]],
    },
    "SELECT * FROM order_items WHERE order_id = 'ORD-20260408-7721'": {
        "columns": ["item_id", "product_id", "name", "price", "quantity", "category"],
        "rows": [
            ["ITM-001", "PROD-2201", "USB-C Cable 1m", "3.99", 3, "Accessories"],
            ["ITM-002", "PROD-2202", "Screen Protector", "2.49", 4, "Accessories"],
            ["ITM-003", "PROD-2203", "Phone Stand", "4.99", 2, "Accessories"],
            ["ITM-004", "PROD-2204", "Cable Organizer", "2.99", 3, "Accessories"],
            ["ITM-005", "PROD-2205", "Dust Plug Set", "1.99", 5, "Accessories"],
        ],
    },
    "SELECT * FROM discount_codes WHERE code = 'BULK25'": {
        "columns": ["code", "discount_type", "discount_value", "max_uses", "usage_count",
                     "eligible_categories", "tier_thresholds", "expires_at"],
        "rows": [["BULK25", "tiered_percent", "0", 500, 47,
                  '["Accessories","Cables"]',
                  '[[1,10],[5,25],[10,40],[15,60]]',
                  "2026-06-30 23:59:59"]],
    },
    "SELECT * FROM audit_log WHERE entity_id = 'ORD-20260408-7721' ORDER BY timestamp": {
        "columns": ["event_type", "timestamp", "entity_id", "details"],
        "rows": [
            ["order.created", "2026-04-08 14:20:33", "ORD-20260408-7721",
             '{"customer_id":"CUST-88291","item_count":15}'],
            ["discount.applied", "2026-04-08 14:21:05", "ORD-20260408-7721",
             '{"code":"BULK25","discount_amount":"78.68","new_total":"-26.23"}'],
            ["payment.failed", "2026-04-08 14:21:08", "ORD-20260408-7721",
             '{"reason":"Invalid amount: -26.23","gateway":"stripe"}'],
        ],
    },
    "SELECT COUNT(*) as affected FROM orders WHERE discount_code = 'BULK25' AND total < 0": {
        "columns": ["affected"],
        "rows": [[12]],
    },
    "SELECT * FROM audit_log WHERE event_type LIKE '%discount_code%' ORDER BY timestamp DESC LIMIT 5": {
        "columns": ["event_type", "timestamp", "details"],
        "rows": [
            ["discount_code.created", "2026-03-28 09:15:22",
             '{"code":"BULK25","type":"tiered_percent","tiers":[[1,10],[5,25],[10,40],[15,60]]}'],
            ["discount_code.created", "2026-03-28 09:12:00",
             '{"code":"BULK10","type":"tiered_percent","tiers":[[1,5],[5,10],[10,15]]}'],
        ],
    },
}


def execute_mock_query(sql: str) -> dict:
    """
    Mock database executor. Matches queries by checking if the fixture key
    is contained in the incoming SQL (case-insensitive, whitespace-normalized).

    In production, replace this with your read-only database tool.
    """
    sql_normalized = " ".join(sql.lower().split())
    for fixture_sql, result in FIXTURE_DB.items():
        if " ".join(fixture_sql.lower().split()) in sql_normalized:
            return {
                "success": True,
                "columns": result["columns"],
                "rows": result["rows"],
                "row_count": len(result["rows"]),
            }
    return {
        "success": True,
        "columns": [],
        "rows": [],
        "row_count": 0,
        "note": "No matching fixture for this query — try the templates in the skill.",
    }
