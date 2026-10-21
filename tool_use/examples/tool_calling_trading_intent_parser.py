"""
tool_calling_trading_intent_parser.py

Demonstrates Anthropic tool calling by building a natural language
intent parser that maps plain English trading commands to structured
function calls — with a safety validation layer between the LLM
response and execution.

This pattern is useful any time you want an LLM to trigger real
actions (API calls, database writes, system commands) from free-form
user input, while keeping a deterministic safety gate in your code.

Requirements:
    pip install anthropic python-dotenv

Setup:
    export ANTHROPIC_API_KEY=your_key
    (or add to a .env file)
"""

import json
import os
from decimal import Decimal, InvalidOperation
from dotenv import load_dotenv
import anthropic

load_dotenv()
client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

# ── Step 1: Define tools — what the LLM is allowed to call ────────────────────
#
# Each tool has a name, a description (what the LLM reads to decide when to
# use it), and an input_schema (JSON Schema defining required parameters).
#
# Good descriptions are the most important part of tool calling.
# The LLM uses them to decide WHICH tool fits the user's intent.

TOOLS = [
    {
        "name": "place_market_order",
        "description": (
            "Places a market order that executes immediately at the current price. "
            "Use when the user says 'buy/sell now', 'at market', or gives no price."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "symbol":   {"type": "string",  "description": "Trading pair e.g. BTCUSDT"},
                "side":     {"type": "string",  "enum": ["BUY", "SELL"]},
                "quantity": {"type": "number",  "description": "Amount to buy or sell"},
            },
            "required": ["symbol", "side", "quantity"],
        },
    },
    {
        "name": "place_limit_order",
        "description": (
            "Places a limit order that only fills at the specified price or better. "
            "Use when the user gives a specific price target."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "symbol":   {"type": "string", "description": "Trading pair e.g. BTCUSDT"},
                "side":     {"type": "string", "enum": ["BUY", "SELL"]},
                "quantity": {"type": "number", "description": "Amount to buy or sell"},
                "price":    {"type": "number", "description": "Limit price — required"},
            },
            "required": ["symbol", "side", "quantity", "price"],
        },
    },
    {
        "name": "get_price",
        "description": "Returns the current market price for a symbol.",
        "input_schema": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "Trading pair e.g. BTCUSDT"},
            },
            "required": ["symbol"],
        },
    },
]


# ── Step 2: Safety validation — runs BEFORE any execution ─────────────────────
#
# This is a critical pattern: the LLM decides what to call, but your code
# decides whether it's safe. Never let LLM output reach external APIs
# without a validation layer.

class SafetyError(Exception):
    pass

MAX_QUANTITY = Decimal("1.0")  # block unreasonably large orders
ALLOWED_SYMBOLS = {"BTCUSDT", "ETHUSDT", "BNBUSDT"}

def validate(tool_name: str, tool_input: dict) -> None:
    symbol = tool_input.get("symbol", "").upper()
    if symbol and symbol not in ALLOWED_SYMBOLS:
        raise SafetyError(f"Symbol '{symbol}' not in allowed list: {ALLOWED_SYMBOLS}")

    if "quantity" in tool_input:
        try:
            qty = Decimal(str(tool_input["quantity"]))
        except InvalidOperation:
            raise SafetyError(f"Invalid quantity: {tool_input['quantity']!r}")
        if qty <= 0:
            raise SafetyError(f"Quantity must be positive, got {qty}")
        if qty > MAX_QUANTITY:
            raise SafetyError(f"Quantity {qty} exceeds safety limit of {MAX_QUANTITY}")

    if tool_name == "place_limit_order" and "price" not in tool_input:
        raise SafetyError("LIMIT order missing price — specify a price or use a market order")


# ── Step 3: Simulated execution (replace with real API calls) ─────────────────

def execute(tool_name: str, tool_input: dict) -> dict:
    """
    In a real application this calls your exchange, database, or external API.
    Here we simulate the response so this example runs without credentials.
    """
    if tool_name == "place_market_order":
        return {
            "status": "FILLED",
            "order_id": 123456,
            "symbol": tool_input["symbol"],
            "side": tool_input["side"],
            "quantity": tool_input["quantity"],
            "note": "[simulated — replace execute() with real API call]",
        }
    if tool_name == "place_limit_order":
        return {
            "status": "NEW",
            "order_id": 789012,
            "symbol": tool_input["symbol"],
            "side": tool_input["side"],
            "quantity": tool_input["quantity"],
            "price": tool_input["price"],
            "note": "[simulated — replace execute() with real API call]",
        }
    if tool_name == "get_price":
        return {
            "symbol": tool_input["symbol"],
            "mark_price": "67423.50",
            "note": "[simulated — replace execute() with real API call]",
        }
    raise ValueError(f"Unknown tool: {tool_name!r}")


# ── Step 4: The tool-use loop ──────────────────────────────────────────────────
#
# Anthropic's tool calling works in a loop:
#   1. Send user message + tool definitions
#   2. LLM responds with tool_use blocks (which tools to call + with what args)
#   3. You execute the tools and send back tool_result blocks
#   4. LLM uses the results to form a final natural language response
#
# stop_reason == "tool_use"  → LLM wants to call tools, keep looping
# stop_reason == "end_turn"  → LLM is done, return the final text

def chat(user_message: str) -> str:
    print(f"\nUser: {user_message}")
    conversation = [{"role": "user", "content": user_message}]

    while True:
        response = client.messages.create(
            model      = "claude-sonnet-4-20250514",
            max_tokens = 1024,
            tools      = TOOLS,
            messages   = conversation,
            system     = (
                "You are a trading assistant. Parse the user's intent and call "
                "the appropriate tool. Confirm order details in your final response."
            ),
        )

        # Collect tool calls and any text from this response turn
        tool_results = []
        final_text   = ""

        for block in response.content:
            if block.type == "text":
                final_text = block.text

            elif block.type == "tool_use":
                print(f"  → tool call: {block.name}({json.dumps(block.input)})")

                try:
                    validate(block.name, block.input)           # safety gate
                    result  = execute(block.name, block.input)  # execute
                    content = json.dumps(result)
                    print(f"  ← result: {content}")
                except SafetyError as e:
                    content = f"BLOCKED: {e}"
                    print(f"  ✗ safety block: {e}")

                tool_results.append({
                    "type":        "tool_result",
                    "tool_use_id": block.id,
                    "content":     content,
                })

        # Append assistant turn, then tool results if any
        conversation.append({"role": "assistant", "content": response.content})

        if tool_results:
            conversation.append({"role": "user", "content": tool_results})
            continue  # loop back — let the LLM form a response using the results

        break  # stop_reason is "end_turn", no more tool calls

    print(f"Assistant: {final_text}")
    return final_text


# ── Demo ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    examples = [
        "What is the current BTC price?",
        "Place a limit buy for 0.01 BTCUSDT at 60000",
        "Sell 0.005 ETH at market",
        "Buy 5 BTC at market",           # triggers safety block (qty > 1.0)
        "Buy 0.01 DOGEUSDT at market",   # triggers safety block (not in whitelist)
    ]

    for message in examples:
        chat(message)
        print("-" * 60)
