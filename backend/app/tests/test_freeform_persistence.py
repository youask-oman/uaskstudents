from sqlmodel import SQLModel, Session, create_engine, select

from app.api import _persist_freeform_attempt
from app.models import SolverOutputAttempt


def test_persist_freeform_attempt_creates_db_row(tmp_path):
    db_path = tmp_path / "freeform_persist.db"
    engine = create_engine(f"sqlite:///{db_path}")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        row = _persist_freeform_attempt(
            session=session,
            request_id="req-1",
            user_id=1,
            session_id=None,
            message_id=None,
            attempt_number=1,
            provider="openai",
            model="mightykatun/gpt-5-mini",
            prompt_id="free_form_math_standard_detailed_v1",
            prompt_version="v1",
            raw_solution_text="Step 1: test",
            extracted_answer="x=2",
            validation_json={"is_valid": True, "score": "8/8"},
            latency_ms=1234,
            archive_path="storage/solver_outputs/freeform/2026/02/03/file.md",
            status="ok",
        )
        assert row.id is not None

        saved = session.exec(select(SolverOutputAttempt).where(SolverOutputAttempt.request_id == "req-1")).one()
        assert saved.output_format == "freeform"
        assert saved.raw_solution_text == "Step 1: test"
        assert saved.attempt_number == 1
        assert saved.validation_json["is_valid"] is True
