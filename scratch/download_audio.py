import urllib.request
import os

url = "https://raw.githubusercontent.com/microsoft/Cognitive-Speech-STT-Service-Sample/main/samples/SpeechSynthesis/SpeechSynthesisSample/SpeechSynthesisSample/SpeechSynthesisSample.wav"
dest = os.path.join(os.path.dirname(os.path.dirname(__file__)), "sample_speech_long.wav")

print(f"Downloading from {url} to {dest}...")
urllib.request.urlretrieve(url, dest)
print("Download completed successfully!")
