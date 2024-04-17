import anthropic

# Set up the Anthropic API client
client = anthropic.Client("YOUR_API_KEY")

# Define a function to track expenses
def track_expense(description, amount, category):
    # Use the Anthropic language model to categorize the expense
    response = client.completion(
        prompt=f"Categorize the following expense: {description}",
        max_tokens=50,
        stop_sequences=[],
    )
    categorized_category = response.result["choice"]

    # Store the expense in a database or file
    with open("expenses.txt", "a") as f:
        f.write(f"{description},{amount},{categorized_category}\n")

    print(f"Expense '{description}' of ${amount} categorized as '{categorized_category}'")

# Example usage
track_expense("Grocery shopping at Whole Foods", 75.25, "Food")
track_expense("Paid rent for May", 1200.00, "Housing")