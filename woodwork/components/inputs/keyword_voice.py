from threading import Thread
from vosk import Model, KaldiRecognizer
import json
import sounddevice as sd
import webrtcvad
import numpy as np
import wave
import openai
import tempfile
import time

from woodwork.helper_functions import print_debug, format_kwargs
from woodwork.components.inputs.inputs import inputs


class keyword_voice(inputs):
    def __init__(self, api_key, keyword, **config):
        format_kwargs(config, type="keyword_voice")
        super().__init__(**config)
        print_debug("Creating keyword voice input...")

        self._api_key = api_key
        self._keyword = keyword
        self._model = Model(".woodwork/models/vosk-model-small-en-us-0.15")
        self._rec = KaldiRecognizer(self._model, 16000)
        print(f'Keyword voice input activated, listening for {keyword}')
        thread = Thread(target=self._hotword_listener, daemon=True)
        thread.start()

        while True:
            time.sleep(1)

    def _hotword_listener(self):
        def callback_wrapper(indata, frames, time_info, status):
            self._rec.AcceptWaveform(bytes(indata))
            partial_result = json.loads(self._rec.PartialResult())
            print(partial_result)
            if self._keyword in partial_result.get("partial", "").lower():
                print("Hotword detected!")
                self._handle_voice_command()

        with sd.RawInputStream(samplerate=16000, blocksize=8000, dtype='int16',
                            channels=1, callback=callback_wrapper):
            print("Listening for hotword...")
            while True:
                pass

    def _record_audio_vad(self, filename="temp.wav", max_duration=30, aggressiveness=2, silence_threshold=2.0):
        fs = 16000  # Sampling rate
        vad = webrtcvad.Vad(aggressiveness)
        frame_duration = 30  # ms
        frame_size = int(fs * frame_duration / 1000)  # number of samples per frame
        silence_duration = 0
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
                silence_duration = 0
            else:
                silence_duration += frame_duration / 1000

        with sd.InputStream(samplerate=fs, channels=1, dtype='int16', blocksize=frame_size, callback=callback):
            while silence_duration < silence_threshold and (len(recorded_frames) * frame_duration / 1000) < max_duration:
                sd.sleep(frame_duration)

        print("Recording complete.")

        # Save to WAV
        with wave.open(filename, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)  # int16 = 2 bytes
            wf.setframerate(fs)
            wf.writeframes(b''.join(recorded_frames))

        return filename

    def _transcribe_audio(self, filepath):
        client = openai.OpenAI(api_key=self._api_key)

        print("Transcribing with Whisper...")
        with open(filepath, "rb") as f:
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=f
            )
        print(f"Transcribed: {transcript.text}")
        return transcript.text

    def _handle_voice_command(self):
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            audio_file = self._record_audio_vad(tmp.name)
            query = self._transcribe_audio(audio_file)
            print(self._output.input(query))
