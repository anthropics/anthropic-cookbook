import wikipedia
from typing import Dict, List
from .base import Tool

class WikipediaTool(Tool):
    """Tool for searching Wikipedia and fetching article content."""
    
    def __init__(self):
        super().__init__(
            name="wikipedia",
            description="Search Wikipedia or fetch full article content",
            parameters={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "description": "The action to perform: 'search' for a topic or 'fetch' for a full article",
                        "enum": ["search", "fetch"]
                    },
                    "query": {
                        "type": "string",
                        "description": "The search term or exact article title"
                    },
                    "depth": {
                        "type": "string",
                        "description": "For search: 'summary' (default) or 'detailed' to get more information",
                        "enum": ["summary", "detailed"]
                    }
                },
                "required": ["action", "query"]
            },
            function=self.wikipedia_action
        )
    
    def wikipedia_action(self, action: str, query: str, depth: str = "summary") -> str:
        """
        Perform Wikipedia actions: search or fetch.
        
        Args:
            action: Either 'search' to find information or 'fetch' to get a full article
            query: The search term or article title
            depth: For search, controls how much information to return (summary or detailed)
            
        Returns:
            A formatted string with the results
        """
        try:
            if action == "search":
                return self._search(query, depth)
            elif action == "fetch":
                return self._fetch(query)
            else:
                return f"Invalid action: {action}. Use 'search' or 'fetch'."
        except Exception as e:
            return f"Error performing Wikipedia {action}: {str(e)}"
    
    def _search(self, query: str, depth: str = "summary") -> str:
        """Search Wikipedia for a topic."""
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
    
    def _fetch(self, title: str) -> str:
        """Fetch the full content of a specific Wikipedia page."""
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