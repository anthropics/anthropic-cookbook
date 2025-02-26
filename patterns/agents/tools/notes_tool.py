from typing import Dict, List
from .base import Tool

class NoteTool(Tool):
    """Tool for taking and organizing research notes."""
    
    def __init__(self):
        self.notes = ""
        super().__init__(
            name="notes",
            description="Take, read, and manage research notes",
            parameters={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "description": "The action to perform with notes",
                        "enum": ["read", "write", "append", "clear"]
                    },
                    "content": {
                        "type": "string",
                        "description": "The content to write (only needed for write/append)"
                    }
                },
                "required": ["action"]
            },
            function=self.handle_notes
        )
    
    def handle_notes(self, action: str, content: str = None) -> str:
        """
        Handle note operations.
        
        Args:
            action: The action to perform (read, write, append, clear)
            content: The content to write (for write/append actions)
            
        Returns:
            The result of the action
        """
        if action == "read":
            return self.read()
        elif action == "write" and content:
            return self.write(content, overwrite=True)
        elif action == "append" and content:
            return self.write(content, overwrite=False)
        elif action == "clear":
            return self.clear()
        else:
            return "Invalid action or missing content for write/append."
    
    def read(self) -> str:
        """Read the current notes."""
        return self.notes if self.notes else "No notes have been saved yet."
    
    def write(self, content: str, overwrite: bool = False) -> str:
        """Write or append to notes."""
        if overwrite:
            self.notes = content
            return "Notes have been overwritten."
        else:
            if not self.notes:
                self.notes = content
            else:
                self.notes += f"\n\n{content}"
            return "Content has been added to notes."
    
    def clear(self) -> str:
        """Clear all notes."""
        self.notes = ""
        return "All notes have been cleared."