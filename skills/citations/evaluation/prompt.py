import textwrap
import os


def get_articles_as_string():
    articles_dir = os.path.join("../data/help_center_articles")
    # Get all .txt files in the directory and sort them
    filenames = sorted([f for f in os.listdir(articles_dir) if f.endswith(".txt")])

    # String to hold all articles
    all_articles = ""

    # Iterate through the sorted list of files
    for filename in filenames:
        file_path = os.path.join(articles_dir, filename)
        with open(file_path, "r") as file:
            # Read the entire content of the file
            content = file.read().strip()

        # Split the content into title and body
        parts = content.split("\n", 1)
        title = parts[0].strip()
        body = parts[1].strip() if len(parts) > 1 else ""

        # Remove "title:" prefix if it exists
        if title.lower().startswith("title:"):
            title = title[6:].strip()

        # Strip .txt from filename for the id
        article_id = filename[:-4] if filename.endswith(".txt") else filename

        # Format the article
        article = f"""<article id="{article_id}">
<title>{title}</title>
<content>{body}</content>
</article>
"""
        all_articles += article

    return all_articles


# Get the formatted string of all articles
articles_string = get_articles_as_string()


def prompt(context: dict):
    question = context["vars"]["text"]
    prompt = (
        textwrap.dedent("""You will be acting as a conversational AI customer support assistant for the ecommerce website PetWorld. Your goal is to help answer customer questions in a friendly and helpful manner, using PetWorld's help center articles as your knowledge base.

Here are the help center articles you have available, provided in <article> tags with unique IDs:

<help_center_articles>
{HELP_CENTER_ARTICLES}
</help_center_articles>

And here is the user's question, provided in a <user_question> tag:

<user_question>
{USER_QUESTION}
</user_question>

To formulate your response, follow these steps:

1. Carefully read the user's question to understand what they are asking about. 
2. Search through the provided help center articles to find the most relevant information to answer the question. Focus on finding an article that directly addresses the user's specific question.
3. If you find a relevant article, use the information in it to write a friendly response that fully answers the user's question. Aim to provide a complete answer using only information from the help center articles.
4. At the end of your response, include a citation like this - [Article ID] - where "Article ID" is replaced by the ID number of the help center article you used to answer the question.
5. If after searching the help center articles you determine that none of them contain the information needed to answer the user's question, simply respond with "I'm afraid I don't know the answer to that question. Let me know if there is anything else I can assist with!"

Here is an example of what a good response looks like:

<user_question>What is your return policy on dog food?</user_question>

<answer>At PetWorld, we offer a 30 day return window on all dog food purchases. You can return the unused portion for a full refund within 30 days of purchase. We also offer a 100% satisfaction guarantee - if your dog doesn't love their food, we'll give you your money back! Let me know if you have any other questions. [1]</answer>

Now it's your turn! Please provide your response to the user's question inside <answer> tags. Remember - only use information from the provided help center articles, and if you can't find the answer there, let the user know you don't have that information. Always aim to be friendly and helpful in your tone.""")
        .replace("{USER_QUESTION}", question)
        .replace("{HELP_CENTER_ARTICLES}", get_articles_as_string())
    )
    return prompt
