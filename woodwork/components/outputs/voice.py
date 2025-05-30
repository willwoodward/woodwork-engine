import openai
import os
import tempfile

from woodwork.components.outputs.outputs import outputs
from woodwork.helper_functions import format_kwargs


class voice(outputs):
    def __init__(self, **config):
        format_kwargs(config, type="voice")
        super().__init__(**config)

    def input(self, data: str):
        """Given text, output the text as voice."""
        self.speak(data)

    def speak(self, text):
        response = openai.audio.speech.create(model="tts-1", voice="nova", input=text)
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
            tmp.write(response.content)
            tmp.flush()
            os.system(f"ffplay -nodisp -autoexit {tmp.name} > /dev/null 2>&1")
