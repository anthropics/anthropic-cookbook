# Use LiteLLM Proxy to call Anthropic

Use [LiteLLM Proxy](https://docs.litellm.ai/docs/simple_proxy) for:
- Calling 100+ LLMs OpenAI, Azure, Vertex, Bedrock/etc. in the OpenAI ChatCompletions & Completions format
- Track usage + set budgets with Virtual Keys

Works for [Anthropic API](https://docs.litellm.ai/docs/providers/anthropic) + [Vertex AI](https://docs.litellm.ai/docs/providers/vertex) + [Bedrock](https://docs.litellm.ai/docs/providers/bedrock)

## Sample Usage

### Step 1. Create a Config for LiteLLM proxy

LiteLLM Requires a config with all your models define - we can call this file `litellm_config.yaml`

[Detailed docs on how to setup litellm config - here](https://docs.litellm.ai/docs/proxy/configs)

```yaml
model_list:
  - model_name: claude-3 ### RECEIVED MODEL NAME ###
    litellm_params: # all params accepted by litellm.completion() - https://docs.litellm.ai/docs/completion/input
      model: claude-3-opus-20240229 ### MODEL NAME sent to `litellm.completion()` ###
      api_key: "os.environ/ANTHROPIC_API_KEY" # does os.getenv("ANTHROPIC_API_KEY")

```

### Step 2. Start litellm proxy

```shell
docker run \
    -v $(pwd)/litellm_config.yaml:/app/config.yaml \
    -e ANTHROPIC_API_KEY=<your-anthropic-api-key>
    -p 4000:4000 \
    ghcr.io/berriai/litellm:main-latest \
    --config /app/config.yaml --detailed_debug
```

### Step 3. Test it! 

[Use with Langchain, LlamaIndex, Instructor, etc.](https://docs.litellm.ai/docs/proxy/user_keys)

```bash
import openai
client = openai.OpenAI(
    api_key="anything",
    base_url="http://0.0.0.0:4000"
)

# request sent to model set on litellm proxy, `litellm --model`
response = client.chat.completions.create(
    model="claude-3",
    messages = [
        {
            "role": "user",
            "content": "this is a test request, write a short poem"
        }
    ]
)

print(response)
```

## Tool Calling 

```python
from openai import OpenAI
client = OpenAI(api_key="anything", base_url="http://0.0.0.0:4000") # set base_url to litellm proxy endpoint

tools = [
  {
    "type": "function",
    "function": {
      "name": "get_current_weather",
      "description": "Get the current weather in a given location",
      "parameters": {
        "type": "object",
        "properties": {
          "location": {
            "type": "string",
            "description": "The city and state, e.g. San Francisco, CA",
          },
          "unit": {"type": "string", "enum": ["celsius", "fahrenheit"]},
        },
        "required": ["location"],
      },
    }
  }
]
messages = [{"role": "user", "content": "What's the weather like in Boston today?"}]
completion = client.chat.completions.create(
  model="claude-3",
  messages=messages,
  tools=tools,
  tool_choice="auto"
)

print(completion)

```

## Vision Example

```python

from openai import OpenAI

client = OpenAI(api_key="anything", base_url="http://0.0.0.0:4000") # set base_url to litellm proxy endpoint

response = client.chat.completions.create(
    model="claude-3",
    messages=[
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "What's in this image?"},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/d/dd/Gfp-wisconsin-madison-the-nature-boardwalk.jpg/2560px-Gfp-wisconsin-madison-the-nature-boardwalk.jpg"
                    }
                }
            ],
        }
    ],
    max_tokens=300,
)

print(response.choices[0])
```

## Supported Anthropic API Models

**ALL MODELS SUPPORTED**. 

Just add `anthropic/` to the beginning of the model name.

Example models: 

| Model Name       | Usage                         |
|------------------|--------------------------------------------|
| claude-3-5-sonnet  | `completion('anthropic/claude-3-5-sonnet-20240620', messages)` | `os.environ['ANTHROPIC_API_KEY']`       |
| claude-3-haiku  | `completion('anthropic/claude-3-haiku-20240307', messages)` | `os.environ['ANTHROPIC_API_KEY']`       |
| claude-3-opus  | `completion('anthropic/claude-3-opus-20240229', messages)` | `os.environ['ANTHROPIC_API_KEY']`       |
| claude-3-5-sonnet-20240620  | `completion('anthropic/claude-3-5-sonnet-20240620', messages)` | `os.environ['ANTHROPIC_API_KEY']`       |
| claude-3-sonnet  | `completion('anthropic/claude-3-sonnet-20240229', messages)` | `os.environ['ANTHROPIC_API_KEY']`       |
| claude-2.1  | `completion('anthropic/claude-2.1', messages)` | `os.environ['ANTHROPIC_API_KEY']`       |
| claude-2  | `completion('anthropic/claude-2', messages)` | `os.environ['ANTHROPIC_API_KEY']`       |
| claude-instant-1.2  | `completion('anthropic/claude-instant-1.2', messages)` | `os.environ['ANTHROPIC_API_KEY']`       |
| claude-instant-1  | `completion('anthropic/claude-instant-1', messages)` | `os.environ['ANTHROPIC_API_KEY']`       |

## Supported VertexAI Anthropic Models

| Model Name       | Usage                       |
|------------------|--------------------------------------|
| claude-3-opus@20240229   | `completion('vertex_ai/claude-3-opus@20240229', messages)` |
| claude-3-5-sonnet@20240620  | `completion('vertex_ai/claude-3-5-sonnet@20240620', messages)` |
| claude-3-sonnet@20240229   | `completion('vertex_ai/claude-3-sonnet@20240229', messages)` |
| claude-3-haiku@20240307   | `completion('vertex_ai/claude-3-haiku@20240307', messages)` |

## Supported Bedrock Anthropic Models
| Model Name       | Usage                       |
|------------------|--------------------------------------|
| Anthropic Claude-V3.5 Sonnet    | `completion(model='bedrock/anthropic.claude-3-5-sonnet-20240620-v1:0', messages=messages)`   | `os.environ['AWS_ACCESS_KEY_ID']`, `os.environ['AWS_SECRET_ACCESS_KEY']`           |
| Anthropic Claude-V3  sonnet    | `completion(model='bedrock/anthropic.claude-3-sonnet-20240229-v1:0', messages=messages)`   | `os.environ['AWS_ACCESS_KEY_ID']`, `os.environ['AWS_SECRET_ACCESS_KEY']`           |
| Anthropic Claude-V3 Haiku     | `completion(model='bedrock/anthropic.claude-3-haiku-20240307-v1:0', messages=messages)`   | `os.environ['AWS_ACCESS_KEY_ID']`, `os.environ['AWS_SECRET_ACCESS_KEY']`           |
| Anthropic Claude-V3 Opus     | `completion(model='bedrock/anthropic.claude-3-opus-20240229-v1:0', messages=messages)`   | `os.environ['AWS_ACCESS_KEY_ID']`, `os.environ['AWS_SECRET_ACCESS_KEY']`           |
| Anthropic Claude-V2.1      | `completion(model='bedrock/anthropic.claude-v2:1', messages=messages)`   | `os.environ['AWS_ACCESS_KEY_ID']`, `os.environ['AWS_SECRET_ACCESS_KEY']`           |
| Anthropic Claude-V2        | `completion(model='bedrock/anthropic.claude-v2', messages=messages)`   | `os.environ['AWS_ACCESS_KEY_ID']`, `os.environ['AWS_SECRET_ACCESS_KEY']`           |
| Anthropic Claude-Instant V1 | `completion(model='bedrock/anthropic.claude-instant-v1', messages=messages)` | `os.environ['AWS_ACCESS_KEY_ID']`, `os.environ['AWS_SECRET_ACCESS_KEY']`           |