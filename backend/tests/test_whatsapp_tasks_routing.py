from pathlib import Path


def test_whatsapp_ocr_forces_glm_and_auto_enqueue():
    src = Path("backend/app/tasks/whatsapp_tasks.py").read_text(encoding="utf-8")
    assert "parse_image_with_ollama_generate(" in src
    assert '"whatsapp_solve"' in src
    assert "Image extracted. Solving now..." in src


def test_whatsapp_solve_uses_short_pipeline_and_short_tier():
    src = Path("backend/app/tasks/whatsapp_tasks.py").read_text(encoding="utf-8")
    assert "solve_text_questions(" in src
    assert 'requested_mode="free_minimal"' in src
    assert 'tier="SHORT_STEPS"' in src
    assert '"tier": "short_steps"' in src
