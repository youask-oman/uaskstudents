from app.api import _persist_debug_blob_refs


def test_telemetry_strips_raw_keys_without_capture(monkeypatch):
    monkeypatch.setenv("STORE_DEBUG_BLOBS_DEFAULT", "false")
    monkeypatch.setenv("STORE_PROVIDER_RAW_DEFAULT", "false")
    telemetry = {
        "provider": "ollama",
        "model": "x",
        "provider_raw_text": "raw text",
        "provider_raw_payload": {"a": 1},
        "ollama_prompt_dump_files": ["f1.txt"],
        "schema_valid": True,
    }
    cleaned, refs = _persist_debug_blob_refs(
        session=None,  # not used when capture disabled
        attempt_id="a1",
        telemetry=telemetry,
        force_capture=False,
    )
    assert refs == []
    assert "provider_raw_text" not in cleaned
    assert "provider_raw_payload" not in cleaned
    assert "ollama_prompt_dump_files" not in cleaned
    assert cleaned.get("provider") == "ollama"
