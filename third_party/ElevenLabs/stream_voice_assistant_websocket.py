"""Low Latency Voice Assistant with WebSocket Streaming

A production-ready conversational voice assistant that demonstrates real-time
speech-to-text, Claude integration, and text-to-speech with minimal latency.

Usage:
    1. Set up environment variables:
       - Copy .env.example to .env
       - Add your API keys to .env:
         * Get ElevenLabs API key: https://elevenlabs.io/app/developers/api-keys
         * Get Anthropic API key: https://console.anthropic.com/settings/keys

    2. Install dependencies:
       pip install -r requirements.txt

    3. Run the script:
       python stream_voice_assistant_websocket.py

    4. Interaction flow:
       - Press Enter to start recording
       - Speak into your microphone
       - Press Enter to stop recording
       - Claude will respond with synthesized speech
       - Repeat or press Ctrl+C to exit

Key optimizations:
- Text chunks sent to TTS immediately as they arrive from Claude
- No sentence buffering required - audio generation begins instantly
- MP3 audio format compatible with free tier accounts
- Continuous audio streaming with pre-buffering prevents crackling
"""

import base64
import io
import json
import os
import threading
import time

import anthropic
import elevenlabs
import numpy as np
import sounddevice as sd
import websocket
from dotenv import load_dotenv
from pydub import AudioSegment
from scipy.io import wavfile

# Load environment variables from .env file
load_dotenv()

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

assert ELEVENLABS_API_KEY is not None, (
    "ERROR: ELEVENLABS_API_KEY not found. Please copy .env.example to .env and add your API keys."
)
assert ANTHROPIC_API_KEY is not None, (
    "ERROR: ANTHROPIC_API_KEY not found. Please copy .env.example to .env and add your API keys."
)

SAMPLE_RATE = 44100  # Audio sample rate for recording
CHANNELS = 1  # Mono audio

elevenlabs_client = elevenlabs.ElevenLabs(
    api_key=ELEVENLABS_API_KEY, base_url="https://api.elevenlabs.io"
)

anthropic_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# Fetch available voices and select the first one
voices = elevenlabs_client.voices.search().voices
selected_voice = voices[0]
VOICE_ID = selected_voice.voice_id
print(f"Using voice: {selected_voice.name} (ID: {VOICE_ID})")

# TTS configuration
TTS_MODEL_ID = "eleven_turbo_v2_5"  # Fast, low-latency model
TTS_OUTPUT_FORMAT = "mp3_44100_128"  # MP3 format (free tier compatible)


class AudioQueue:
    """Manages continuous audio playback with minimal latency.

    Uses sounddevice OutputStream with callback-based streaming:
    - Maintains a byte buffer for incoming audio chunks
    - Stream callback reads from buffer in real-time
    - Pre-buffering prevents crackling from buffer underruns
    """

    # Audio buffer configuration constants
    PRE_BUFFER_SIZE = (
        8192  # Minimum buffer size before playback starts (prevents initial crackling)
    )
    BUFFER_CLEANUP_THRESHOLD = 100000  # Bytes before buffer cleanup to prevent memory growth
    REMAINING_BYTES_THRESHOLD = 1000  # Bytes to consider playback effectively done

    def __init__(self):
        self.buffer = bytearray()
        self.buffer_lock = threading.Lock()
        self.playing = False
        self.stream = None
        self.first_audio_played = False
        self.first_audio_time = None
        self.sample_rate = 44100
        self.channels = 2
        self.finished = False
        self.read_position = 0

    def add(self, audio_data):
        """Add MP3 audio chunk to the playback buffer.

        Args:
            audio_data: Raw MP3 audio bytes
        """
        try:
            # Decode MP3 to PCM
            audio_segment = AudioSegment.from_mp3(io.BytesIO(audio_data))

            # Convert to numpy array
            samples = np.array(audio_segment.get_array_of_samples(), dtype=np.int16)
            samples = samples.astype(np.float32) / 32768.0

            if not self.playing:
                self.sample_rate = audio_segment.frame_rate
                self.channels = audio_segment.channels

            # Reshape based on number of channels
            if self.channels > 1:
                samples = samples.reshape((-1, self.channels))
            else:
                samples = samples.reshape((-1, 1))

            with self.buffer_lock:
                self.buffer.extend(samples.tobytes())

            # Start playback after pre-buffering
            if not self.playing and len(self.buffer) >= self.PRE_BUFFER_SIZE:
                self.start_playback()
        except Exception:  # noqa: S110
            # Silently skip invalid MP3 chunks that fail to decode
            # This is common when streaming MP3 data in real-time, as chunks may contain
            # incomplete frames. Skipping these prevents console errors but may cause
            # brief audio pops. To eliminate popping, upgrade to a paid ElevenLabs tier
            # and use pcm_44100 format instead of MP3.
            pass

    def start_playback(self):
        """Start the audio output stream."""
        self.playing = True

        def callback(outdata, frames, _time_info, _status):
            """Called by sounddevice to fill output buffer."""
            if not self.first_audio_played:
                self.first_audio_time = time.time()
                self.first_audio_played = True

            bytes_needed = frames * self.channels * 4

            with self.buffer_lock:
                bytes_available = len(self.buffer) - self.read_position
                bytes_to_read = min(bytes_needed, bytes_available)

                if bytes_to_read > 0:
                    data = bytes(
                        self.buffer[self.read_position : self.read_position + bytes_to_read]
                    )
                    self.read_position += bytes_to_read

                    if self.read_position > self.BUFFER_CLEANUP_THRESHOLD:
                        self.buffer = self.buffer[self.read_position :]
                        self.read_position = 0
                else:
                    data = b""

            if len(data) > 0:
                audio_array = np.frombuffer(data, dtype=np.float32)
                audio_array = audio_array.reshape((-1, self.channels))

                samples_to_write = min(len(audio_array), frames)
                if samples_to_write > 0:
                    outdata[:samples_to_write] = audio_array[:samples_to_write]
                if samples_to_write < frames:
                    outdata[samples_to_write:] = 0
            else:
                outdata[:] = 0

        self.stream = sd.OutputStream(
            samplerate=self.sample_rate,
            channels=self.channels,
            callback=callback,
            dtype=np.float32,
            blocksize=2048,
        )
        self.stream.start()

    def wait_until_done(self):
        """Block until all buffered audio finishes playing."""
        while True:
            with self.buffer_lock:
                remaining = len(self.buffer) - self.read_position
            if remaining < self.REMAINING_BYTES_THRESHOLD:
                break
            time.sleep(0.1)

        time.sleep(0.5)

        if self.stream:
            self.stream.stop()
            self.stream.close()
        self.playing = False


def record_audio():
    """Record audio from microphone with Enter to start and stop.

    Returns:
        io.BytesIO: WAV format audio buffer
    """
    input("Press Enter to start recording...")
    print("Recording... Press Enter to stop.")
    recording = []

    def callback(indata, _frames, _time_info, _status):
        """Callback that appends audio chunks to recording list."""
        recording.append(indata.copy())

    # Create audio input stream
    stream = sd.InputStream(
        samplerate=SAMPLE_RATE, channels=CHANNELS, callback=callback, dtype=np.float32
    )

    stream.start()
    input()  # Wait for Enter key press
    stream.stop()
    stream.close()

    # Concatenate all audio chunks into a single array
    audio_data = np.concatenate(recording, axis=0)

    # Convert float32 audio to int16 WAV format
    audio_buffer = io.BytesIO()
    audio_int16 = (audio_data * 32767).astype(np.int16)
    wavfile.write(audio_buffer, SAMPLE_RATE, audio_int16)
    audio_buffer.seek(0)

    return audio_buffer


def transcribe_audio(audio_buffer):
    """Transcribe audio using ElevenLabs speech-to-text.

    Args:
        audio_buffer: Audio data in WAV format

    Returns:
        str: Transcribed text
    """
    print("\nTranscribing...")

    # Use ElevenLabs Scribe model for speech-to-text
    transcription = elevenlabs_client.speech_to_text.convert(
        file=audio_buffer, model_id="scribe_v1"
    )

    print(f"Transcription: {transcription.text}")

    return transcription.text


def stream_claude_and_synthesize_ws(messages, audio_queue):
    """Stream Claude response directly to ElevenLabs WebSocket.

    Text chunks are sent to TTS immediately without buffering,
    achieving minimal latency from first token to first audio.

    Args:
        messages: Conversation history (list of message dicts)
        audio_queue: AudioQueue instance

    Returns:
        str: Full assistant response text
    """
    print("\nStreaming Claude response...\n")

    ws_url = f"wss://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}/stream-input?model_id={TTS_MODEL_ID}&output_format={TTS_OUTPUT_FORMAT}"

    ws_connected = False
    ws_finished = False

    def on_message(ws, message):
        """Handle incoming WebSocket messages."""
        nonlocal ws_finished
        data = json.loads(message)

        if "audio" in data and data["audio"]:
            audio_bytes = base64.b64decode(data["audio"])
            audio_queue.add(audio_bytes)

        # Check if generation is complete
        if data.get("isFinal"):
            ws_finished = True

    def on_error(ws, error):
        print(f"\nWebSocket error: {error}")

    def on_close(ws, close_status_code, close_msg):
        """Handle WebSocket connection closure."""
        if close_status_code or close_msg:
            print(f"\nWebSocket closed with status {close_status_code}: {close_msg}")

    def on_open(ws):
        nonlocal ws_connected
        ws_connected = True

        initial_message = {
            "text": " ",
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.8},
            "xi_api_key": ELEVENLABS_API_KEY,
        }
        ws.send(json.dumps(initial_message))

    ws = websocket.WebSocketApp(
        ws_url, on_message=on_message, on_error=on_error, on_close=on_close, on_open=on_open
    )

    ws_thread = threading.Thread(target=ws.run_forever)
    ws_thread.daemon = True
    ws_thread.start()

    while not ws_connected:
        time.sleep(0.01)

    response_text = ""

    # Stream Claude response and send each chunk to WebSocket
    with anthropic_client.messages.stream(
        model="claude-haiku-4-5",
        max_tokens=1000,
        extra_body={"temperature": 0},
        system="""You are a helpful voice assistant. Your responses will be converted to speech using ElevenLabs.
Do not write in markdown, as it cannot be read aloud properly.""",
        messages=messages,
    ) as stream:
        for text in stream.text_stream:
            print(text, end="", flush=True)
            response_text += text
            ws.send(json.dumps({"text": text, "try_trigger_generation": True}))

    ws.send(json.dumps({"text": ""}))

    # Wait for WebSocket to signal completion
    while not ws_finished:
        time.sleep(0.1)

    ws.close()
    ws_thread.join(timeout=2)
    print()

    return response_text


def main():
    """Main execution loop."""
    print("=== Low Latency Voice Assistant (WebSocket) ===\n")
    print("Press Ctrl+C to exit\n")

    conversation_history = []

    try:
        while True:
            audio_buffer = record_audio()
            enter_pressed_time = time.time()

            transcription = transcribe_audio(audio_buffer)
            conversation_history.append({"role": "user", "content": transcription})

            audio_queue = AudioQueue()
            response_text = stream_claude_and_synthesize_ws(conversation_history, audio_queue)
            conversation_history.append({"role": "assistant", "content": response_text})

            audio_queue.wait_until_done()

            if audio_queue.first_audio_time:
                time_to_first_audio = audio_queue.first_audio_time - enter_pressed_time
                print(f"Time to first audio: {time_to_first_audio:.2f}s\n")
    except KeyboardInterrupt:
        print("\n\nExiting...")


if __name__ == "__main__":
    main()
