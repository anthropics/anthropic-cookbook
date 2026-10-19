# FlowSpeech <> Claude Cookbook

[FlowSpeech](https://flowspeech.io/) is a context-aware text-to-speech service for generating human-like narration with emotion, pause, voice, and multi-speaker controls.

This integration shows how to use Claude to turn a creative brief into a directed two-speaker script, then synthesize the result with the FlowSpeech API.

## What's Included

- **[Create directed narration with Claude and FlowSpeech](./claude_directed_narration.ipynb)** - Generate a concise dialogue with Claude, send it to FlowSpeech, save the returned audio as a WAV file, and play it in Jupyter.

## Setup

1. Create a virtual environment and activate it.
2. Install the notebook dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Copy the environment template and add your keys:

   ```bash
   cp .env.example .env
   ```

4. Create the required API keys:
   - [Anthropic API key](https://console.anthropic.com/settings/keys)
   - [FlowSpeech API key](https://flowspeech.io/settings/apikeys/create)

5. Start Jupyter and open `claude_directed_narration.ipynb`.

The example never stores credentials in the notebook. Both keys are loaded from environment variables.
