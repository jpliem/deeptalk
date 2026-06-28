import sys
from transformers import pipeline

p = pipeline(
    "automatic-speech-recognition",
    model="openai/whisper-tiny",
    device="cpu",
)

print("--- whisper-tiny without return_timestamps ---")
res = p("synthesized_meeting.wav")
print(res)

print("--- whisper-tiny with generate_kwargs ---")
res2 = p("synthesized_meeting.wav", generate_kwargs={"no_repeat_ngram_size": 2})
print(res2)
