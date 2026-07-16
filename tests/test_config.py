from deeptalk.config import Config


def test_defaults_when_env_empty():
    c = Config.from_env({})
    assert c.stt == "fake"
    assert c.audio == "file"
    assert c.session_id == "demo"
    assert c.db_path == "deeptalk-demo.db"
    assert c.audio_file is None
    assert c.qwen_asr_url == "http://127.0.0.1:8010/v1/audio/transcriptions"
    assert c.qwen_asr_model == "Qwen/Qwen3-ASR-0.6B"
    assert c.qwen_asr_chunk_ms == 2000
    assert c.qwen_language is None
    assert c.qwen_rms_threshold == 200
    assert c.qwen_max_phrase_ms == 15000
    assert c.intent_model is None
    assert c.host == "127.0.0.1"
    assert c.port == 8000
    assert c.fixture_path.replace("\\", "/").endswith("fixtures/sample_meeting.jsonl")



def test_reads_overrides_from_env():
    c = Config.from_env({
        "DEEPTALK_STT": "nemotron",
        "DEEPTALK_AUDIO": "mic",
        "DEEPTALK_SESSION_ID": "meeting1",
        "DEEPTALK_DB": "/tmp/x.db",
        "DEEPTALK_AUDIO_FILE": "/tmp/a.wav",
        "DEEPTALK_QWEN_ASR_URL": "http://localhost:8020/v1/audio/transcriptions",
        "DEEPTALK_QWEN_ASR_MODEL": "Qwen/Qwen3-ASR-1.7B",
        "DEEPTALK_QWEN_ASR_CHUNK_MS": "3000",
        "DEEPTALK_QWEN_LANGUAGE": "zh",
        "DEEPTALK_QWEN_RMS_THRESHOLD": "350",
        "DEEPTALK_QWEN_MAX_PHRASE_MS": "20000",
        "DEEPTALK_INTENT_MODEL": "qwen2.5:7b",
        "DEEPTALK_HOST": "0.0.0.0",
        "DEEPTALK_PORT": "9000",
    })
    assert c.stt == "nemotron"
    assert c.audio == "mic"
    assert c.session_id == "meeting1"
    assert c.db_path == "/tmp/x.db"
    assert c.audio_file == "/tmp/a.wav"
    assert c.qwen_asr_url == "http://localhost:8020/v1/audio/transcriptions"
    assert c.qwen_asr_model == "Qwen/Qwen3-ASR-1.7B"
    assert c.qwen_asr_chunk_ms == 3000
    assert c.qwen_language == "zh"
    assert c.qwen_rms_threshold == 350
    assert c.qwen_max_phrase_ms == 20000
    assert c.intent_model == "qwen2.5:7b"
    assert c.host == "0.0.0.0"
    assert c.port == 9000


def test_config_is_frozen():
    import dataclasses, pytest
    c = Config.from_env({})
    with pytest.raises(dataclasses.FrozenInstanceError):
        c.stt = "nemotron"
