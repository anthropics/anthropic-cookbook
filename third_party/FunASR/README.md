# FunASR + Claude meeting notes

[FunASR](https://github.com/modelscope/FunASR) provides an OpenAI-compatible speech-to-text API for local and self-hosted transcription. This recipe sends an audio file to a local FunASR server, then uses Claude to produce a summary, decisions, action items, and open questions.

Start with [`funasr_claude_meeting_notes.ipynb`](./funasr_claude_meeting_notes.ipynb).

## Privacy boundary

The audio is sent only to the configured FunASR server. With the default `http://127.0.0.1:8000` endpoint, it stays on the local machine. The resulting transcript is sent to the Claude API when `ANTHROPIC_API_KEY` is configured. Review or redact sensitive transcripts before that step.

## Quick start

Install and start FunASR in one terminal:

```bash
python -m pip install -U "funasr>=1.3.26"
funasr-server --model sensevoice --device cpu --host 127.0.0.1 --port 8000
```

Use `--device cuda` on a compatible GPU host. In another terminal, install the notebook dependencies and configure the inputs:

```bash
python -m pip install -U "anthropic>=0.109.0" "requests>=2.32.5" notebook
export ANTHROPIC_API_KEY="your-key"
export AUDIO_PATH="/absolute/path/to/meeting.wav"
jupyter notebook funasr_claude_meeting_notes.ipynb
```

The notebook uses deterministic demo content when no audio is configured, and it skips the Claude call for a live transcript when the API key is absent. This keeps every cell executable without presenting unrelated demo notes as a live result.

## What the cookbook demonstrates

- multipart audio upload to `POST /v1/audio/transcriptions`
- finite HTTP timeouts and explicit response validation
- a current Claude model alias loaded through the Anthropic SDK
- a stable Markdown contract for Summary, Decisions, Action items, and Open questions
- transparent local-audio and remote-transcript privacy boundaries

## Production considerations

Keep the FunASR service on a private network. If it must be reachable remotely, add authentication, TLS, request-size limits, rate limits, and network access controls at a gateway or reverse proxy. Validate audio type and size before upload, chunk long transcripts before sending them to Claude, and apply your retention policy to both source audio and generated text.

More FunASR deployment and security examples are available in the [OpenAI-compatible API documentation](https://github.com/modelscope/FunASR/tree/main/examples/openai_api).
