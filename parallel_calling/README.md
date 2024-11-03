# Anthropic Parallel API Processor
## Overview

This tool is designed to generate datasets faster and more cost-effectively by parallel calling the Anthropic API with optional caching for Claude. It's perfect for processing large volumes of requests while respecting rate limits.

A key feature of this processor is its approach to token estimation. Since there's no open-source tokenizer model available for the new Claude models, we use an older tokenizer to make initial estimates. Once we receive a response from the API, we update these estimates with the actual token usage. This adaptive approach allows us to maintain efficient processing while adhering to Anthropic's rate limits.

## Key Features

- **Parallel Processing**: Maximize throughput with concurrent API requests.
- **Rate Limiting**: Stay within Anthropic's API limits for requests and tokens.
- **Adaptive Token Estimation**: Use initial estimates and update with actual usage.
- **Caching Support**: Optional caching for efficient processing of repeated content.
- **Error Handling**: Retry failed requests and log issues for easy debugging.
- **Memory Efficient**: Stream requests from file to handle large datasets.

## Quick Start

### Installation
This project was developed using Python **3.10.13**. For optimal compatibility and performance, it is strongly recommended that you use the same version.

1. Clone the repository:
    ```bash
    git clone https://github.com/anthropics/anthropic-cookbook.git
    ```
    ```bash
    cd anthropic-cookbook/parallel_calling
    ```
2. Create virtual environment:
    ```bash
    python -m venv .venv
    ```
    For macOS/Linux:
    ```bash
    source .venv/bin/activate
    ```
    For Windows:
    ```bash
    .venv\Scripts\activate
    ```

3. Install dependencies:
    ```
    pip install -r requirements.txt
    ```

4. Set up your Anthropic API key:

   You have two options to set up your API key:

   a. Create a `.env` file in the root of the project and add your API key:
      ```
      ANTHROPIC_API_KEY=your-api-key-here
      ```

   b. Or, set it as an environment variable in your terminal:
      ```bash
      export ANTHROPIC_API_KEY=your-api-key-here
      ```

   > 📎 **Note**: Replace 'your-api-key-here' with your actual Anthropic API key.

### Usage

#### Without Caching

```bash
python api_request_parallel_processor.py \
--requests_filepath examples/test_requests_to_parallel_process.jsonl \
--save_filepath examples/data/test_requests_to_parallel_process_results.jsonl \
--request_url https://api.anthropic.com/v1/messages \
--max_requests_per_minute 40 \
--max_tokens_per_minute 16000 \
--max_attempts 5 \
--logging_level INFO
```

#### With Caching

```bash
python api_request_parallel_processor.py \
--requests_filepath examples/test_caching_requests_to_parallel_process.jsonl \
--save_filepath examples/data/test_caching_requests_to_parallel_process_results.jsonl \
--request_url https://api.anthropic.com/v1/messages \
--use_caching True \
--max_requests_per_minute 40 \
--max_tokens_per_minute 16000 \
--max_attempts 5 \
--logging_level INFO
```
## Important Notes ⚠️

### Cache Limitations
The minimum cacheable prompt length is:

- 1024 tokens for Claude 3.5 Sonnet and Claude 3 Opus
- 2048 tokens for Claude 3 Haiku

We suggest first testing the prompt manually until you see that caching works. In our script, there is an initial call for caching that will let you know if caching is used. If not, you will receive a warning and a 10-second delay before starting the parallel API calls, giving you time to kill the process if needed.

You can learn more about caching from the official Anthropic documentation: [Prompt Caching](https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching)

### Rate Limits
Users need to be aware of and check their specific rate limits. The default settings in this script (40 requests per minute and 16,000 tokens per minute) are set to approximately 80% of the `Tier 1` limits. However, based on your tier, there can be different rate limits.

To check your Tier and rate limits:
- Go to the Anthropic Console
- Navigate to the Settings tab
- Look for the Limits tab in the sidebar on the left side
- Here you can see Rate limits for all models and your current tier

You can read more about rate limits and tiers in the official Anthropic documentation: [Anthropic API Rate Limits](https://docs.anthropic.com/en/api/rate-limits)

Make sure to adjust the `max_requests_per_minute` and `max_tokens_per_minute` configuration options according to your specific tier and needs to ensure optimal performance and avoid hitting rate limits.

## Input File Format
The input file should be a JSONL file where each line is a JSON object representing a single API request. Here's an example structure:
```json
{"model": "claude-3-5-sonnet-20240620", "max_tokens": 1024, "messages": [{"role": "user", "content": "Tell me a joke"}], "metadata": {"row_id": 1}}
```

For caching, use the following structure:
```json
{
  "model": "claude-3-5-sonnet-20240620",
  "max_tokens": 1024,
  "system": [
    {
      "type": "text",
      "text": "You are an AI assistant tasked with analyzing blogs."
    },
    {
      "type": "text",
      "text": "<blog content here>",
      "cache_control": {"type": "ephemeral"}
    }
  ],
  "messages": [
    {
      "role": "user",
      "content": "Analyze the main themes of this blog."
    }
  ]
}
```


## Generating Request Files

You can generate JSONL files for API requests using Python. The following examples demonstrate one approach for both non-caching and caching scenarios, but keep in mind that there are many ways to create these files depending on your specific needs and data sources. These examples are meant to serve as a starting point:


### Without Caching

To generate a JSONL file for standard requests:

```python
import json

filename = "examples/test_requests_to_parallel_process.jsonl"
n_requests = 10
jobs = [
    {
        "model": "claude-3-5-sonnet-20240620",
        "max_tokens": 1024,
        "temperature": 0,
        "messages": [
            {
                "role": "user",
                "content": f"How much is 8 * {x}? Return only the result.\n Result:",
            }
        ],
    }
    for x in range(n_requests)
]
with open(filename, "w") as f:
    for job in jobs:
        json_string = json.dumps(job)
        f.write(json_string + "\n")
```

### With Caching

For requests utilizing caching:

```python
import json

filename = "examples/test_caching_requests_to_parallel_process.jsonl"
queries = [
    "<query/instruction_1>",
    "<query/instruction_2>",
    # ...
]
jobs = [
    {
        "model": "claude-3-5-sonnet-20240620",
        "max_tokens": 1024,
        "temperature": 0,
        "system": [
            {
                "type": "text",
                "text": "You are an AI assistant tasked with... Your goal is to provide insightful information and knowledge.\n",
            },
            {
                "type": "text",
                "text": "<Large repetitive prompt you want to cache.>",
                "cache_control": {"type": "ephemeral"},
            },
        ],
        "messages": [
            {
                "role": "user",
                "content": query,
            }
        ],
    }
    for query in queries
]
with open(filename, "w") as f:
    for job in jobs:
        json_string = json.dumps(job)
        f.write(json_string + "\n")
```
Remember to replace `<Large repetitive prompt you want to cache.>` and `<query/instruction_X>` with your actual data.

### Note on Metadata 💡
You can add a `metadata` key to each request object to include any additional information you want to associate with the request. This can be particularly useful for tracking or mapping requests to your dataset. For example:

```python
"metadata": {"row_id": 1, "source": "dataset_A", "category": "science"}
```
The metadata will be preserved in the output, allowing you to easily map the results back to your original data or include any other relevant information for post-processing.

## Configuration Options

- `requests_filepath`: Path to the input JSONL file.
- `save_filepath`: Path for the output JSONL file (optional).
- `request_url`: Anthropic API endpoint (default: "https://api.anthropic.com/v1/messages").
- `api_key`: Your Anthropic API key (can be set as an environment variable).
- `max_requests_per_minute`: Target requests per minute (default: 40).
- `max_tokens_per_minute`: Target tokens per minute (default: 16,000).
- `max_attempts`: Number of retries for failed requests (default: 5).
- `logging_level`: Logging verbosity (default: INFO).
    - **ERROR** or 40: Logs when requests fail after all retries
    - **WARNING** or 30: Logs when requests hit rate limits or other errors
    - **SUCCESS** or 25: Logs successful operations (Loguru-specific level)
    - **INFO** or 20: Logs when requests start and the status at finish
    - **DEBUG** or 10: Logs various things as the loop runs to see when they occur
    - **TRACE** or 5: Logs very detailed information for debugging
- `use_caching`: Enable caching for repeated content (optional).