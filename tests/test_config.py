from deeptalk.config import Config


def test_defaults_when_env_empty():
    c = Config.from_env({})
    assert c.stt == "fake"
    assert c.audio == "file"
    assert c.session_id == "demo"
    assert c.db_path == "deeptalk-demo.db"
    assert c.audio_file is None
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
        "DEEPTALK_HOST": "0.0.0.0",
        "DEEPTALK_PORT": "9000",
    })
    assert c.stt == "nemotron"
    assert c.audio == "mic"
    assert c.session_id == "meeting1"
    assert c.db_path == "/tmp/x.db"
    assert c.audio_file == "/tmp/a.wav"
    assert c.host == "0.0.0.0"
    assert c.port == 9000


def test_config_is_frozen():
    import dataclasses, pytest
    c = Config.from_env({})
    with pytest.raises(dataclasses.FrozenInstanceError):
        c.stt = "nemotron"
