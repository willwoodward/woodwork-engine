import logging
import tempfile
import time
import wave
from threading import Thread

import numpy as np
import openai
import sounddevice as sd
import webrtcvad

from woodwork.components.inputs.inputs import inputs
from woodwork.helper_functions import format_kwargs

log = logging.getLogger(__name__)


class push_to_talk(inputs):
    def __init__(self, api_key, **config):
        format_kwargs(config, type="push_to_talk")
        super().__init__(**config)
        log.debug("Creating a push to talk input...")

        self._api_key = api_key

        # Initialize the audio stream (for some reason it sometimes doesn't work the first time)
        try:
            sd.RawInputStream(
                samplerate=16000, blocksize=8000, dtype="int16", channels=1, callback=self._handle_voice_command
            )
        except:
            pass

        thread = Thread(target=self._push_to_talk_listener, daemon=True)
        thread.start()
        while True:
            time.sleep(1)

    def _push_to_talk_listener(self):
        print("Press ENTER to start recording. (Ctrl+C to exit)")
        while True:
            input()  # Wait for the user to press Enter
            self._handle_voice_command()

    def _record_audio_vad(self, filename="temp.wav", max_duration=30, aggressiveness=2, silence_threshold=2.0):
        fs = 16000  # Sampling rate
        vad = webrtcvad.Vad(aggressiveness)
        frame_duration = 30  # ms
        frame_size = int(fs * frame_duration / 1000)  # number of samples per frame
        silence_duration = [0]
        recorded_frames = []

        print("Listening... Speak now.")

        def callback(indata, frames, time, status):
            nonlocal recorded_frames

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
