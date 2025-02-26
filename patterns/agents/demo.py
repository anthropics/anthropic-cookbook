import os
from flask import Flask, render_template, request, jsonify
from anthropic import Anthropic
from tools import Tool
from tools.notes_tool import NoteTool
from tools.wikipedia_tools import WikiSearchTool, WikiContentTool
import json

class WebAgent:
    """Agent that uses Anthropic's native tool use API with tracking for visualization."""
    
    def __init__(self, system_prompt=None, api_key=None):
        self.model = "claude-3-5-sonnet-20241022"
        self.system_prompt = system_prompt
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self.client = Anthropic(api_key=self.api_key)
        self.tools = {}  # name -> Tool
        
        # For tracking and visualization
        self.messages = []
        self.thinking_history = []
        self.tool_use_history = []
        self.current_turn = 0
    
    def add_tool(self, tool: Tool):
        """Add a tool to the agent."""
        self.tools[tool.name] = tool
        
    def add_tools(self, tools):
        """Add multiple tools to the agent."""
        for tool in tools:
            self.add_tool(tool)
    
    def reset(self):
        """Reset the agent state."""
        self.messages = []
        self.thinking_history = []
        self.tool_use_history = []
        self.current_turn = 0
    
    def step(self, query=None):
        """Execute a single step of the agent."""
        # For the first step, initialize with the query
        if self.current_turn == 0 and query:
            self.messages = [{"role": "user", "content": query}]
        
        # Convert tools to API format
        tools = [tool.to_api_schema() for tool in self.tools.values()]
        
        # Prepare step data
        step_data = {
            "turn": self.current_turn + 1,
            "thinking": "",
            "tool_use": None,
            "tool_result": None
        }
        
        # Call the model
        params = {
            "model": self.model,
            "messages": self.messages,
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
        self.messages.append({"role": "assistant", "content": response.content})
        
        # Extract the assistant's thinking (text content)
        thinking_text = []
        for content_block in response.content:
            if hasattr(content_block, "type") and content_block.type == "text":
                thinking_text.append(content_block.text)
        
        step_data["thinking"] = "\n".join(thinking_text)
        self.thinking_history.append(step_data["thinking"])
        
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
            
            step_data["tool_use"] = {
                "name": tool_name,
                "input": tool_input
            }
            
            # Execute the tool
            if tool_name in self.tools:
                try:
                    result = self.tools[tool_name].run(**tool_input)
                except Exception as e:
                    result = f"Error executing tool {tool_name}: {str(e)}"
            else:
                result = f"Unknown tool: {tool_name}"
            
            step_data["tool_result"] = result
            self.tool_use_history.append({
                "name": tool_name,
                "input": tool_input,
                "result": result
            })
            
            # Add the tool response to the message history
            self.messages.append({
                "role": "user", 
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_id,
                        "content": result
                    }
                ]
            })
            
            # Increment turn counter
            self.current_turn += 1
            
            return step_data, False  # Not done yet
        else:
            # No tool call, agent is done
            self.current_turn += 1
            return step_data, True  # Done
    
    def run(self, query: str, max_turns: int = 5):
        """Run the agent with the user's query, returning all steps."""
        self.reset()
        
        all_steps = []
        is_done = False
        
        # First step with query
        step_data, is_done = self.step(query)
        all_steps.append(step_data)
        
        # Continue stepping until done or max_turns reached
        for _ in range(max_turns - 1):
            if is_done:
                break
            
            step_data, is_done = self.step()
            all_steps.append(step_data)
        
        return all_steps, is_done
    
    def get_final_response(self):
        """Get the final text response from the agent."""
        if not self.messages:
            return "No messages in history."
            
        final_message = self.messages[-1]
        if final_message["role"] == "assistant":
            text_content = []
            for content_block in final_message["content"]:
                if hasattr(content_block, "type") and content_block.type == "text":
                    text_content.append(content_block.text)
            
            if text_content:
                return "\n".join(text_content)
        
        return "No final response found. Consider increasing max_turns."


# Flask application
app = Flask(__name__)

# Global agent instance
agent = None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/init', methods=['POST'])
def initialize_agent():
    global agent
    
    data = request.json
    system_prompt = data.get('system_prompt', "")
    
    agent = WebAgent(system_prompt=system_prompt)
    
    # Add tools
    agent.add_tools([
        NoteTool(),
        WikiSearchTool(),
        WikiContentTool()
    ])
    
    return jsonify({'status': 'success', 'model': 'claude-3-5-sonnet-20241022'})

@app.route('/run', methods=['POST'])
def run_agent():
    global agent
    
    if not agent:
        return jsonify({'error': 'Agent not initialized'}), 400
    
    data = request.json
    query = data.get('query', '')
    max_turns = int(data.get('max_turns', 5))
    
    steps, is_done = agent.run(query, max_turns)
    
    return jsonify({
        'steps': steps,
        'is_done': is_done,
        'final_response': agent.get_final_response() if is_done else None
    })

@app.route('/step', methods=['POST'])
def step_agent():
    global agent
    
    if not agent:
        return jsonify({'error': 'Agent not initialized'}), 400
    
    data = request.json
    query = data.get('query', None)  # Only needed for first step
    
    step_data, is_done = agent.step(query)
    
    return jsonify({
        'step': step_data,
        'is_done': is_done,
        'final_response': agent.get_final_response() if is_done else None
    })

if __name__ == '__main__':
    # Create templates directory if it doesn't exist
    os.makedirs('templates', exist_ok=True)
    
    print("Starting Agent Visualization Interface...")
    print("Access the web interface at http://127.0.0.1:5000")
    print("Available tools: Notes, Wikipedia Search, Wikipedia Content")
    
    app.run(debug=True)