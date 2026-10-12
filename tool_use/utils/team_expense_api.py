"""
Example Mock API for Team Expense Management Demo

This is a domain-specific API used in the programmatic tool calling cookbook.
It provides mock tools for retrieving team member information, expense records,
and budget limits by employee level.
"""

import json
import random
import time
from datetime import datetime, timedelta

# Configuration
EXPENSE_LINE_ITEMS_PER_PERSON_MIN = 20
EXPENSE_LINE_ITEMS_PER_PERSON_MAX = 50
DELAY_MULTIPLIER = 0  # Adjust this to simulate API latency


def get_team_members(department: str) -> str:
    """Returns a list of team members for a given department.

    Each team member includes their ID, name, role, level, and contact information.
    Use this to get a list of people whose expenses you want to analyze.

    Args:
        department: The department name (e.g., 'engineering', 'sales', 'marketing').
            Case-insensitive.

    Returns:
        JSON string containing an array of team member objects with fields:
        - id: Unique employee identifier
        - name: Full name
        - role: Job title
        - level: Employee level (junior, mid, senior, staff, principal)
        - email: Contact email
        - department: Department name
    """
    import time

    time.sleep(DELAY_MULTIPLIER * 0.1)

    department = department.lower()

    # Mock team data by department
    teams = {
        "engineering": [
            {
                "id": "ENG001",
                "name": "Alice Chen",
                "role": "Senior Software Engineer",
                "level": "senior",
                "email": "alice.chen@company.com",
                "department": "engineering",
            },
            {
                "id": "ENG002",
                "name": "Bob Martinez",
                "role": "Staff Engineer",
                "level": "staff",
                "email": "bob.martinez@company.com",
                "department": "engineering",
            },
            {
                "id": "ENG003",
                "name": "Carol White",
                "role": "Software Engineer",
                "level": "mid",
                "email": "carol.white@company.com",
                "department": "engineering",
            },
            {
                "id": "ENG004",
                "name": "David Kim",
                "role": "Principal Engineer",
                "level": "principal",
                "email": "david.kim@company.com",
                "department": "engineering",
            },
            {
                "id": "ENG005",
                "name": "Emma Johnson",
                "role": "Junior Software Engineer",
                "level": "junior",
                "email": "emma.johnson@company.com",
                "department": "engineering",
            },
            {
                "id": "ENG006",
                "name": "Frank Liu",
                "role": "Senior Software Engineer",
                "level": "senior",
                "email": "frank.liu@company.com",
                "department": "engineering",
            },
            {
                "id": "ENG007",
                "name": "Grace Taylor",
                "role": "Software Engineer",
                "level": "mid",
                "email": "grace.taylor@company.com",
                "department": "engineering",
            },
            {
                "id": "ENG008",
                "name": "Henry Park",
                "role": "Staff Engineer",
                "level": "staff",
                "email": "henry.park@company.com",
                "department": "engineering",
            },
        ],
        "sales": [
            {
                "id": "SAL001",
                "name": "Irene Davis",
                "role": "Account Executive",
                "level": "mid",
                "email": "irene.davis@company.com",
                "department": "sales",
            },
            {
                "id": "SAL002",
                "name": "Jack Wilson",
                "role": "Senior Account Executive",
                "level": "senior",
                "email": "jack.wilson@company.com",
                "department": "sales",
            },
            {
                "id": "SAL003",
                "name": "Kelly Brown",
                "role": "Sales Development Rep",
                "level": "junior",
                "email": "kelly.brown@company.com",
                "department": "sales",
            },
            {
                "id": "SAL004",
                "name": "Leo Garcia",
                "role": "Regional Sales Director",
                "level": "staff",
                "email": "leo.garcia@company.com",
                "department": "sales",
            },
            {
                "id": "SAL005",
                "name": "Maya Patel",
                "role": "Account Executive",
                "level": "mid",
                "email": "maya.patel@company.com",
                "department": "sales",
            },
            {
                "id": "SAL006",
                "name": "Nathan Scott",
                "role": "VP of Sales",
                "level": "principal",
                "email": "nathan.scott@company.com",
                "department": "sales",
            },
        ],
        "marketing": [
            {
                "id": "MKT001",
                "name": "Olivia Thompson",
                "role": "Marketing Manager",
                "level": "senior",
                "email": "olivia.thompson@company.com",
                "department": "marketing",
            },
            {
                "id": "MKT002",
                "name": "Peter Anderson",
                "role": "Content Specialist",
                "level": "mid",
                "email": "peter.anderson@company.com",
                "department": "marketing",
            },
            {
                "id": "MKT003",
                "name": "Quinn Rodriguez",
                "role": "Marketing Coordinator",
                "level": "junior",
                "email": "quinn.rodriguez@company.com",
                "department": "marketing",
            },
            {
                "id": "MKT004",
                "name": "Rachel Lee",
                "role": "Director of Marketing",
                "level": "staff",
                "email": "rachel.lee@company.com",
                "department": "marketing",
            },
            {
                "id": "MKT005",
                "name": "Sam Miller",
                "role": "Social Media Manager",
                "level": "mid",
                "email": "sam.miller@company.com",
                "department": "marketing",
            },
        ],
    }

    if department not in teams:
        return json.dumps(
            {
                "error": f"Department '{department}' not found. Available departments: {', '.join(teams.keys())}"
            }
        )

    return json.dumps(teams[department], indent=2)


def get_expenses(employee_id: str, quarter: str) -> str:
    """Returns all expense line items for a given employee in a specific quarter.

    Each expense includes comprehensive metadata: date, category, description, amount,
    receipt details, approval chain, merchant information, and more. An employee may
    have anywhere from a few to 150+ expense line items per quarter, and each line
    item contains substantial metadata for audit and compliance purposes.

    Args:
        employee_id: The unique employee identifier (e.g., 'ENG001', 'SAL002')
        quarter: Case-insensitive quarter identifier (e.g., 'Q1', 'Q2', 'Q3', 'Q4').
            The same employee and quarter always return the same mock records.

    Returns:
        JSON string containing an array of expense objects with fields:
        - expense_id: Unique expense identifier
        - date: ISO format date when expense occurred
        - category: Expense type (travel, meals, lodging, software, equipment, etc.)
        - description: Details about the expense
        - amount: Dollar amount (float)
        - currency: Currency code (default 'USD')
        - status: Approval status (approved, pending, rejected)
        - receipt_url: URL to uploaded receipt image
        - approved_by: Manager or finance person who approved
        - store_name: Merchant or vendor name
        - store_location: City and state of merchant
        - reimbursement_date: When the expense was reimbursed (if applicable)
        - payment_method: How it was paid (corporate_card, personal_reimbursement)
        - project_code: Project or cost center code
        - notes: Employee justification or additional context
    """

    time.sleep(DELAY_MULTIPLIER * 0.2)

    # Quarter date ranges
    quarter_dates = {
        "Q1": (datetime(2024, 1, 1), datetime(2024, 3, 31)),
        "Q2": (datetime(2024, 4, 1), datetime(2024, 6, 30)),
        "Q3": (datetime(2024, 7, 1), datetime(2024, 9, 30)),
        "Q4": (datetime(2024, 10, 1), datetime(2024, 12, 31)),
    }

    if quarter.upper() not in quarter_dates:
        return json.dumps({"error": f"Invalid quarter '{quarter}'. Must be Q1, Q2, Q3, or Q4"})

    quarter = quarter.upper()
    start_date, end_date = quarter_dates[quarter]

    # Keep records stable across processes without changing global random state.
    rng = random.Random(employee_id + quarter)
    num_expenses = rng.randint(EXPENSE_LINE_ITEMS_PER_PERSON_MIN, EXPENSE_LINE_ITEMS_PER_PERSON_MAX)

    # Expense categories and typical amounts
    expense_categories = [
        ("travel", "Flight to client meeting", 400, 1500),
        ("travel", "Train ticket", 1000, 1500),
        ("travel", "Rental car", 1000, 1500),
        ("travel", "Taxi/Uber", 150, 200),
        ("travel", "Parking fee", 10, 50),
        ("lodging", "Hotel stay", 150, 1900),
        ("lodging", "Airbnb rental", 1000, 1950),
        ("meals", "Client dinner", 50, 250),
        ("meals", "Team lunch", 20, 100),
        ("meals", "Conference breakfast", 15, 40),
        ("meals", "Coffee meeting", 5, 25),
        ("software", "SaaS subscription", 10, 200),
        ("software", "API credits", 50, 500),
        ("equipment", "Monitor", 200, 800),
        ("equipment", "Keyboard", 50, 200),
        ("equipment", "Webcam", 50, 150),
        ("equipment", "Headphones", 100, 300),
        ("conference", "Conference ticket", 500, 2500),
        ("conference", "Workshop registration", 200, 1000),
        ("office", "Office supplies", 10, 100),
        ("office", "Books", 20, 80),
        ("internet", "Mobile data", 30, 100),
        ("internet", "WiFi hotspot", 20, 60),
    ]

    # Manager names for approvals
    managers = [
        "Sarah Johnson",
        "Michael Chen",
        "Emily Rodriguez",
        "David Park",
        "Jennifer Martinez",
    ]

    # Store/merchant names by category
    merchants = {
        "travel": [
            "United Airlines",
            "Delta",
            "American Airlines",
            "Southwest",
            "Enterprise Rent-A-Car",
        ],
        "lodging": ["Marriott", "Hilton", "Hyatt", "Airbnb", "Holiday Inn"],
        "meals": ["Olive Garden", "Starbucks", "The Capital Grille", "Chipotle", "Panera Bread"],
        "software": ["AWS", "GitHub", "Linear", "Notion", "Figma"],
        "equipment": ["Amazon", "Best Buy", "Apple Store", "B&H Photo", "Newegg"],
        "conference": ["EventBrite", "WWDC", "AWS re:Invent", "Google I/O", "ReactConf"],
        "office": ["Staples", "Office Depot", "Amazon", "Target"],
        "internet": ["Verizon", "AT&T", "T-Mobile", "Comcast"],
    }

    # US cities for store locations
    cities = [
        "San Francisco, CA",
        "New York, NY",
        "Austin, TX",
        "Seattle, WA",
        "Boston, MA",
        "Chicago, IL",
        "Denver, CO",
        "Los Angeles, CA",
        "Portland, OR",
        "Miami, FL",
    ]

    # Project codes
    project_codes = [
        "PROJ-1001",
        "PROJ-1002",
        "PROJ-2001",
        "DEPT-ENG",
        "DEPT-OPS",
        "CLIENT-A",
        "CLIENT-B",
    ]

    # Justification templates
    justifications = {
        "travel": [
            "Client meeting to discuss Q4 roadmap and requirements",
            "On-site visit for infrastructure review and planning",
            "Conference attendance for professional development",
            "Team offsite for strategic planning session",
            "Customer presentation and product demo",
        ],
        "lodging": [
            "Hotel for multi-day client visit",
            "Accommodation during conference attendance",
            "Extended stay for project implementation",
            "Lodging for team collaboration week",
        ],
        "meals": [
            "Client dinner discussing partnership opportunities",
            "Team lunch during sprint planning",
            "Breakfast meeting with stakeholders",
            "Working dinner during crunch period",
        ],
        "software": [
            "Required tool for development workflow",
            "API credits for production workload",
            "Team collaboration platform subscription",
            "Design and prototyping tool license",
        ],
        "equipment": [
            "Replacing failed hardware",
            "Upgraded monitor for productivity",
            "Required for remote work setup",
            "Better equipment for video calls",
        ],
        "conference": [
            "Professional development - learning new technologies",
            "Networking with industry leaders and potential partners",
            "Presenting company work at industry event",
            "Training workshop for certification",
        ],
        "office": [
            "Supplies for home office setup",
            "Reference materials for project work",
            "Team whiteboarding supplies",
        ],
        "internet": [
            "Mobile hotspot for reliable connectivity",
            "Upgraded internet for remote work",
            "International data plan for travel",
        ],
    }

    expenses = []
    for i in range(num_expenses):
        category, desc_template, min_amt, max_amt = rng.choice(expense_categories)

        # Generate random date within quarter
        days_diff = (end_date - start_date).days
        random_days = rng.randint(0, days_diff)
        expense_date = start_date + timedelta(days=random_days)

        # Generate amount
        amount = round(rng.uniform(min_amt, max_amt), 2)

        # Status (most are approved)
        status = rng.choices(["approved", "pending", "rejected"], weights=[0.85, 0.10, 0.05])[0]

        # Generate additional metadata
        approved_by = rng.choice(managers) if status == "approved" else None
        store_name = rng.choice(merchants.get(category, ["Unknown Merchant"]))
        store_location = rng.choice(cities)
        payment_method = rng.choice(["corporate_card", "personal_reimbursement"])
        project_code = rng.choice(project_codes)
        notes = rng.choice(justifications.get(category, ["Business expense"]))

        # Reimbursement date is 15-30 days after expense date for approved expenses
        reimbursement_date = None
        if status == "approved" and payment_method == "personal_reimbursement":
            reimb_days = rng.randint(15, 30)
            reimbursement_date = (expense_date + timedelta(days=reimb_days)).strftime("%Y-%m-%d")

        expenses.append(
            {
                "expense_id": f"{employee_id}_{quarter}_{i:03d}",
                "date": expense_date.strftime("%Y-%m-%d"),
                "category": category,
                "description": desc_template,
                "amount": amount,
                "currency": "USD",
                "status": status,
                "receipt_url": f"https://receipts.company.com/{employee_id}/{quarter}/{i:03d}.pdf",
                "approved_by": approved_by,
                "store_name": store_name,
                "store_location": store_location,
                "reimbursement_date": reimbursement_date,
                "payment_method": payment_method,
                "project_code": project_code,
                "notes": notes,
            }
        )

    # Sort by date
    expenses.sort(key=lambda x: x["date"])

    return json.dumps(expenses, indent=2)


def get_custom_budget(user_id: str) -> str:
    """Get the custom quarterly travel budget for a specific employee.

    Most employees have a standard $5,000 quarterly travel budget. However, some
    employees have custom budget exceptions based on their role requirements.
    This function checks if a specific employee has a custom budget assigned.

    Args:
        user_id: The unique employee identifier (e.g., 'ENG001', 'SAL002')

    Returns:
        JSON string containing:
        - user_id: Employee identifier
        - has_custom_budget: Boolean indicating if custom budget exists
        - travel_budget: Quarterly travel budget amount (custom or standard $5,000)
        - reason: Explanation for custom budget (if applicable)
        - currency: Currency code (default 'USD')
    """
    time.sleep(DELAY_MULTIPLIER * 0.05)

    # Employees with custom budget exceptions
    custom_budgets = {
        "ENG002": {
            "user_id": "ENG002",
            "has_custom_budget": True,
            "travel_budget": 8000,
            "reason": "Staff engineer with regular client site visits",
            "currency": "USD",
        },
        "ENG004": {
            "user_id": "ENG004",
            "has_custom_budget": True,
            "travel_budget": 12000,
            "reason": "Principal engineer leading distributed team across multiple offices",
            "currency": "USD",
        },
        "SAL004": {
            "user_id": "SAL004",
            "has_custom_budget": True,
            "travel_budget": 15000,
            "reason": "Regional sales director covering west coast territory",
            "currency": "USD",
        },
        "SAL006": {
            "user_id": "SAL006",
            "has_custom_budget": True,
            "travel_budget": 20000,
            "reason": "VP of Sales with extensive client travel requirements",
            "currency": "USD",
        },
        "MKT004": {
            "user_id": "MKT004",
            "has_custom_budget": True,
            "travel_budget": 10000,
            "reason": "Director of Marketing attending industry conferences and partner meetings",
            "currency": "USD",
        },
    }

    # Check if user has custom budget
    if user_id in custom_budgets:
        return json.dumps(custom_budgets[user_id], indent=2)

    # Return standard budget
    return json.dumps(
        {
            "user_id": user_id,
            "has_custom_budget": False,
            "travel_budget": 5000,
            "reason": "Standard quarterly travel budget",
            "currency": "USD",
        },
        indent=2,
    )


# Helper function to get all available tools
def get_expense_tools():
    """Returns a list of all expense management tools for use with Claude API."""
    return [get_team_members, get_expenses, get_custom_budget]


if __name__ == "__main__":
    # Example usage demonstrating custom budget checking
    print("=== Team Expense Analysis Example ===\n")

    # Get team members
    team = json.loads(get_team_members("engineering"))

    exceeded_standard = []
    for member in team[:5]:  # Just check first 5 for demo
        print(f"Checking expenses for {member['name']}...")

        # Fetch this person's expenses (could be 100+ line items)
        expenses = json.loads(get_expenses(member["id"], "Q3"))

        # Calculate total travel expenses
        travel_total = sum(
            exp["amount"]
            for exp in expenses
            if exp["status"] == "approved" and exp["category"] in ["travel", "lodging"]
        )

        print(f"  - Found {len(expenses)} expense line items")
        print(f"  - Total approved travel expenses: ${travel_total:,.2f}")

        # Check against standard $5,000 budget
        if travel_total > 5000:
            print("  ⚠️  Exceeded standard $5,000 budget")
            # Now check if they have a custom budget exception
            custom = json.loads(get_custom_budget(member["id"]))
            print(f"  - Custom budget: ${custom['travel_budget']:,}")

            if travel_total > custom["travel_budget"]:
                print("  ❌ VIOLATION: Exceeded custom budget!")
                exceeded_standard.append(
                    {
                        "name": member["name"],
                        "spent": travel_total,
                        "custom_limit": custom["travel_budget"],
                    }
                )
            else:
                print("  ✅ Within custom budget limit")
        print()

    print("\n=== Summary: Employees Over Custom Budget ===")
    print(json.dumps(exceeded_standard, indent=2))
