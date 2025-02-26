import wikipedia
from typing import Dict, List
from .base import Tool

class WikiSearchTool(Tool):
    """Tool for searching Wikipedia articles."""
    
    def __init__(self):
        super().__init__(
            name="wiki_search",
            description="Search Wikipedia for information on a topic",
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search term to look up on Wikipedia"
                    },
                    "depth": {
                        "type": "string",
                        "description": "Controls how much information to return: 'summary' (default) or 'detailed'",
                        "enum": ["summary", "detailed"]
                    }
                },
                "required": ["query"]
            },
            function=self.search_wikipedia
        )
    
    def search_wikipedia(self, query: str, depth: str = "summary") -> str:
        """
        Search Wikipedia for a topic.
        
        Args:
            query: The search term
            depth: Controls how much information to return (summary or detailed)
            
        Returns:
            A formatted string with the search results
        """
        try:
            # Find search results
            search_results = wikipedia.search(query, results=5)
            
            if not search_results:
                return f"No Wikipedia results found for '{query}'."
            
            try:
                # Get the page for the top result
                page = wikipedia.page(search_results[0])
                
                if depth == "summary":
                    # Just get a summary
                    summary = wikipedia.summary(search_results[0], sentences=5)
                    result = f"Title: {page.title}\n\nSummary: {summary}\n\nURL: {page.url}"
                    
                    # Add other search results if any
                    if len(search_results) > 1:
                        result += "\n\nOther relevant topics: " + ", ".join(search_results[1:5])
                    
                    return result
                else:
                    # Get more detailed information
                    summary = wikipedia.summary(search_results[0], sentences=10)
                    content = page.content[:4000]  # First part of the content
                    
                    result = f"# {page.title}\n\n"
                    result += f"URL: {page.url}\n\n"
                    result += f"## Summary\n{summary}\n\n"
                    result += f"## Content (Partial)\n{content}"
                    
                    if len(page.content) > 4000:
                        result += "\n\n[Content truncated due to length...]"
                    
                    # Add other search results if any
                    if len(search_results) > 1:
                        result += "\n\n## Other relevant topics:\n- " + "\n- ".join(search_results[1:5])
                    
                    return result
                    
            except wikipedia.DisambiguationError as e:
                return f"Multiple matches found for '{query}'. Try one of these specific topics: {', '.join(e.options[:5])}"
            except Exception as e:
                return f"Error retrieving Wikipedia page: {str(e)}"
        except Exception as e:
            return f"Error searching Wikipedia: {str(e)}"


class WikiContentTool(Tool):
    """Tool for fetching full Wikipedia article content."""
    
    def __init__(self):
        super().__init__(
            name="wiki_content",
            description="Fetch the full content of a specific Wikipedia article",
            parameters={
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "The exact title of the Wikipedia article to fetch"
                    }
                },
                "required": ["title"]
            },
            function=self.fetch_content
        )
    
    def fetch_content(self, title: str) -> str:
        """
        Fetch the full content of a specific Wikipedia page.
        
        Args:
            title: The exact title of the Wikipedia article
            
        Returns:
            The article content as formatted text
        """
        try:
            # Get the page
            page = wikipedia.page(title)
            
            # Build the result
            result = f"# {page.title}\n\n"
            result += f"URL: {page.url}\n\n"
            
            # Add content
            result += page.content[:8000]  # Limit to avoid overwhelming the model
            
            if len(page.content) > 8000:
                result += "\n\n[Content truncated due to length...]"
                
            return result
        except wikipedia.DisambiguationError as e:
            return f"Multiple matches found for '{title}'. Try one of these specific topics: {', '.join(e.options[:5])}"
        except wikipedia.PageError:
            return f"No Wikipedia page found with the title '{title}'."
        except Exception as e:
            return f"Error fetching Wikipedia page: {str(e)}"