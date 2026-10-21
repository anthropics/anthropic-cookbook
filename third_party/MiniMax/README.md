# MiniMax TTS <> Claude Cookbooks

[MiniMax](https://platform.minimax.io/) provides high-quality text-to-speech APIs with streaming support, enabling low-latency voice synthesis for AI applications.

This cookbook demonstrates how to build a voice assistant by combining MiniMax's TTS with Claude's intelligent text generation.

## What's Included

- **[Voice Assistant Notebook](./voice_assistant_with_minimax_tts.ipynb)** — Step-by-step guide to building a voice assistant with Claude and MiniMax TTS, covering basic TTS, SSE streaming, and a complete assistant pipeline.

## Prerequisites

- Python 3.11+
- An [Anthropic API key](https://console.anthropic.com/settings/keys)
- A [MiniMax API key](https://platform.minimax.io/)

## Quick Start

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure environment variables:**

   Create a `.env` file in this directory:
   ```
   MINIMAX_API_KEY=your_minimax_api_key_here
   ANTHROPIC_API_KEY=sk-ant-api03-...
   ```

3. **Open the notebook:**
   ```bash
   jupyter notebook voice_assistant_with_minimax_tts.ipynb
   ```

## What You'll Learn

- How to use the MiniMax TTS API to synthesize speech
- How to parse SSE (Server-Sent Events) streaming responses
- How to decode hex-encoded audio from the MiniMax API
- How to combine Claude streaming with MiniMax TTS for a voice assistant

## MiniMax TTS Key Points

- **Audio encoding**: MiniMax audio is **hex-encoded** (use `bytes.fromhex()`, not base64)
- **Streaming**: Uses SSE format — parse `data:` lines and decode JSON
- **Models**: `speech-2.8-hd` (high quality) or `speech-2.8-turbo` (faster)
- **API endpoint**: `POST https://api.minimax.io/v1/t2a_v2`

## Resources

- [MiniMax Platform](https://platform.minimax.io/)
- [MiniMax TTS API Reference](https://platform.minimax.io/docs/api-reference/speech-t2a-http)
- [Anthropic Claude Documentation](https://docs.anthropic.com/)
