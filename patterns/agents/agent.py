import os
from typing import Dict, List, Any
from anthropic import Anthropic
from tools import Tool


class Agent:
    """Agent that uses Anthropic's native tool use API."""
    
    def __init__(self, model="claude-3-7-sonnet-20250219", system_prompt=None, api_key=None):
        self.model = model
        self.system_prompt = system_prompt
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self.client = Anthropic(api_key=self.api_key)
        self.tools = {}  # name -> Tool
    
    def add_tool(self, tool: Tool):
        """Add a tool to the agent."""
        self.tools[tool.name] = tool
        
    def add_tools(self, tools):
        """Add multiple tools to the agent."""
        for tool in tools:
            self.add_tool(tool)
    
    def run(self, query: str, max_turns: int = 5, verbose: bool = True) -> str:
        """Run the agent with the user's query."""
        messages = [{"role": "user", "content": query}]
        
        if verbose:
            print("\n===== STARTING SESSION =====\n")
            print(f"Query: {query}\n")
        
        # Convert tools to API format
        tools = [tool.to_api_schema() for tool in self.tools.values()]
        
        for turn in range(max_turns):
            if verbose:
                print(f"\n----- Turn {turn+1} -----\n")
            
            # Call the model
            params = {
                "model": self.model,
                "messages": messages,
                "max_tokens": 4096,
                "temperature": 0.1,
                "system": self.system_prompt,
            }
            
            # Add tools if they exist
            if tools:
                params["tools"] = tools
                
            # Make the API call
            response = self.client.messages.create(**params)
            
            # Add the assistant's response to the message history
            messages.append({"role": "assistant", "content": response.content})
            
            # Print the assistant's thinking (text content)
            if verbose:
                print("Agent thinking:")
                for content_block in response.content:
                    if hasattr(content_block, "type") and content_block.type == "text":
                        print(content_block.text)
                        print()
            
            # Check if there's a tool call
            tool_call = None
            for content_block in response.content:
                if content_block.type == "tool_use":
                    tool_call = content_block
                    break
            
            if tool_call:
                # Extract tool details
                tool_name = tool_call.name
                tool_input = tool_call.input
                tool_id = tool_call.id
                
                if verbose:
                    print(f"Using tool: {tool_name}")
                    print(f"Input: {tool_input}")
                
                # Execute the tool
                if tool_name in self.tools:
                    try:
                        result = self.tools[tool_name].run(**tool_input)
                    except Exception as e:
                        result = f"Error executing tool {tool_name}: {str(e)}"
                else:
                    result = f"Unknown tool: {tool_name}"
                
                # Print truncated tool result
                if verbose:
                    truncated_result = result
                    if len(truncated_result) > 500:
                        truncated_result = truncated_result[:500] + "... [truncated]"
                    print(f"Tool result: {truncated_result}\n")
                
                # Add the tool response to the message history
                messages.append({
                    "role": "user", 
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": tool_id,
                            "content": result
                        }
                    ]
                })
            else:
                # No tool call, agent is done
                if verbose:
                    print("Agent completed task")
                break
        
        # Extract the final text response
        final_message = messages[-1]
        if final_message["role"] == "assistant":
            text_content = []
            for content_block in final_message["content"]:
                if hasattr(content_block, "type") and content_block.type == "text":
                    text_content.append(content_block.text)
            
            if text_content:
                return "\n".join(text_content)
            
            try:
                return str(final_message["content"])
            except:
                pass
        
        return "No final response found. Consider increasing max_turns."