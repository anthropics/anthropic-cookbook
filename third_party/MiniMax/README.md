# MiniMax <> Claude Cookbooks

[MiniMax](https://www.minimax.io/) is an AI company offering powerful large language models and text-to-speech APIs. Their TTS service provides natural, expressive speech synthesis in multiple voices with streaming support.

This cookbook demonstrates how to combine MiniMax's text-to-speech (TTS) capabilities with Claude's intelligent responses to build voice-enabled applications.

## What's Included

- **[Voice Assistant Notebook](./claude_minimax_tts.ipynb)** — An interactive tutorial that walks you through:
  - Generating conversational responses with Claude
  - Synthesizing speech using the MiniMax TTS API (`speech-2.8-hd`)
  - Parsing the SSE streaming audio response
  - Building a multi-turn voice conversation pipeline
  - Exploring different MiniMax voices

## How to Use This Cookbook

### Step 1: Set Up Your Environment

1. **Navigate to this directory:**
   ```bash
   cd third_party/MiniMax
   ```

2. **Create and activate a virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # macOS/Linux
   # or: venv\Scripts\activate  # Windows
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

### Step 2: Get Your API Keys

- **Anthropic API key:** [console.anthropic.com/settings/keys](https://console.anthropic.com/settings/keys)
- **MiniMax API key:** [platform.minimax.io](https://platform.minimax.io/)

Set them as environment variables or create a `.env` file:

```bash
ANTHROPIC_API_KEY=sk-ant-...
MINIMAX_API_KEY=your_minimax_api_key
```

### Step 3: Run the Notebook

Open the notebook and run cells sequentially:

```bash
jupyter notebook claude_minimax_tts.ipynb
```

## MiniMax TTS Highlights

| Feature | Details |
|---------|---------|
| **Models** | `speech-2.8-hd` (high quality), `speech-2.8-turbo` (fast) |
| **Streaming** | SSE with hex-encoded audio chunks |
| **Formats** | MP3, PCM, FLAC, WAV |
| **Sample rates** | 8k, 16k, 22.05k, 24k, 32k, 44.1k Hz |
| **Voices** | Multiple English voices (see notebook for full list) |

### Available English Voices

| Voice ID | Style |
|----------|-------|
| `English_Graceful_Lady` | Warm, graceful (female) |
| `English_Insightful_Speaker` | Calm, authoritative (male) |
| `English_radiant_girl` | Energetic, bright (female) |
| `English_Persuasive_Man` | Confident, persuasive (male) |
| `English_Lucky_Robot` | Sci-fi, robotic (neutral) |
| `English_expressive_narrator` | Expressive, storytelling (male) |

## More About MiniMax

- [MiniMax Platform](https://www.minimax.io/)
- [TTS API Documentation](https://platform.minimax.io/docs/api-reference/speech-t2a-http)
- [Voice ID Reference](https://platform.minimax.io/faq/system-voice-id)
- [Pricing](https://platform.minimax.io/docs/guides/pricing-paygo)
