import os
from transformers import pipeline

p = pipeline(
    "automatic-speech-recognition",
    model="openai/whisper-tiny",
    device="cpu",
)

files = [
    "sample_speech.wav",
    "sample_speech.mp3",
    "sample_speech_long.wav",
    "sample_meeting.wav",
    "harvard.wav",
    "synthesized_meeting.wav"
]

for f in files:
    if os.path.exists(f):
        try:
            res = p(f, generate_kwargs={"no_repeat_ngram_size": 2})
            print(f"{f}: {res.get('text')}")
        except Exception as e:
            print(f"Error on {f}: {e}")
    else:
        print(f"File not found: {f}")
