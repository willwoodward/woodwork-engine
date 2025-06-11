import contextlib
import json
import logging
import os
import sys
import tempfile
import time
import urllib.request
import wave
import zipfile
from threading import Lock, Thread

import numpy as np
import openai
import sounddevice as sd
import webrtcvad
from vosk import KaldiRecognizer, Model

from woodwork.components.inputs.inputs import inputs
from woodwork.helper_functions import format_kwargs

log = logging.getLogger(__name__)


@contextlib.contextmanager
def suppress_stderr():
    """A context manager to suppress C++ library stderr (e.g., Vosk)."""
    with open(os.devnull, "w") as devnull:
        stderr_fd = sys.stderr.fileno()

        # Save current stderr file descriptor
        saved_stderr_fd = os.dup(stderr_fd)

        # Redirect stderr to /dev/null
        os.dup2(devnull.fileno(), stderr_fd)
        try:
            yield
        finally:
            # Restore original stderr
            os.dup2(saved_stderr_fd, stderr_fd)
            os.close(saved_stderr_fd)


class keyword_voice(inputs):
    def __init__(self, api_key, keyword, **config):
        format_kwargs(config, type="keyword_voice")
        super().__init__(**config)
        log.debug("Creating keyword voice input...")

        self._api_key = api_key
        self._keyword = keyword
        self._listening_lock = Lock()

        # Loading the lightweight model for keyword detection
        self._ensure_model()
        with suppress_stderr():
            self._model = Model(".woodwork/models/vosk-model-small-en-us-0.15")
        self._rec = KaldiRecognizer(self._model, 16000)

        thread = Thread(target=self._hotword_listener, daemon=True)
        thread.start()
        while True:
            time.sleep(1)

    def _download_model(self):
        zip_path = os.path.join(".woodwork", "models", "vosk-model-small-en-us-0.15.zip")
        log.debug("Downloading Vosk model...")
        urllib.request.urlretrieve("https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip", zip_path)
        log.debug("Download complete. Extracting...")

        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall(".woodwork/models")

        os.remove(zip_path)
        log.debug("Model ready.")

    def _ensure_model(self):
        if not os.path.isdir(".woodwork/models/vosk-model-small-en-us-0.15"):
            os.makedirs(".woodwork/models", exist_ok=True)
            self._download_model()
        else:
            log.debug("Model already present.")

    def _hotword_listener(self):
        def callback_wrapper(indata, frames, time_info, status):
            self._rec.AcceptWaveform(bytes(indata))
            partial_result = json.loads(self._rec.PartialResult())
            log.debug(partial_result)
            if self._keyword in partial_result.get("partial", "").lower():
                print("Hotword detected!")
                with self._listening_lock:
                    self._handle_voice_command()
                    self._rec = KaldiRecognizer(self._model, 16000)

        # Initialize the audio stream (for some reason it sometimes doesn't work the first time)
        try:
            sd.RawInputStream(samplerate=16000, blocksize=8000, dtype="int16", channels=1, callback=callback_wrapper)
        except:
            pass

        with sd.RawInputStream(samplerate=16000, blocksize=8000, dtype="int16", channels=1, callback=callback_wrapper):
            print("Listening for keyword...")
            while True:
                pass

    def _record_audio_vad(self, filename="temp.wav", max_duration=30, aggressiveness=2, silence_threshold=2.0):
        fs = 16000  # Sampling rate
        vad = webrtcvad.Vad(aggressiveness)
        frame_duration = 30  # ms
        frame_size = int(fs * frame_duration / 1000)  # number of samples per frame
        silence_duration = [0]
        recorded_frames = []

        print("Listening... Speak now.")

        def callback(indata, frames, time, status):
            nonlocal silence_duration, recorded_frames

            if status:
                print(status)

            audio_frame = indata[:, 0]  # Mono
            pcm_bytes = audio_frame.astype(np.int16).tobytes()
            is_speech = vad.is_speech(pcm_bytes, fs)

            recorded_frames.append(pcm_bytes)

            if is_speech:
                silence_duration[0] = 0
            else:
                silence_duration[0] += frame_duration / 1000

        with sd.InputStream(samplerate=fs, channels=1, dtype="int16", blocksize=frame_size, callback=callback):
            while (
                silence_duration[0] < silence_threshold
                and (len(recorded_frames) * frame_duration / 1000) < max_duration
            ):
                sd.sleep(frame_duration)

        print("Recording complete.")

        # Save to WAV
        with wave.open(filename, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)  # int16 = 2 bytes
            wf.setframerate(fs)
            wf.writeframes(b"".join(recorded_frames))

        return filename

    def _transcribe_audio(self, filepath):
        client = openai.OpenAI(api_key=self._api_key)

        log.debug("Transcribing with Whisper...")
        with open(filepath, "rb") as f:
            transcript = client.audio.transcriptions.create(model="whisper-1", file=f)
        log.debug(f"Transcribed: {transcript.text}")
        return transcript.text

    def _handle_voice_command(self):
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            audio_file = self._record_audio_vad(tmp.name)
            query = self._transcribe_audio(audio_file)
            self._output.input(query)
