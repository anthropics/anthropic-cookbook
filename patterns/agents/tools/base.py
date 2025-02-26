from typing import Dict, Callable

class Tool:
    """Tool that can be used by the agent."""
    
    def __init__(self, name: str, description: str, parameters: Dict, function: Callable):
        self.name = name
        self.description = description 
        self.parameters = parameters
        self.function = function
    
    def run(self, **kwargs) -> str:
        """Run the tool with the provided arguments."""
        return self.function(**kwargs)
    
    def to_api_schema(self) -> Dict:
        """Convert to the format expected by Anthropic's API."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.parameters
        }