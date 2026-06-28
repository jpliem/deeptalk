@echo off
set DEEPTALK_STT=qwen
set DEEPTALK_AUDIO=mic
set DEEPTALK_TIMELINE_INTERVAL=10
set DEEPTALK_OLLAMA_URL=http://localhost:11434
set DEEPTALK_OLLAMA_MODEL=llama3.2:3b
"%~dp0..\.venv\Scripts\python.exe" -u -m deeptalk.server
