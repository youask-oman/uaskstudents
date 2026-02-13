from __future__ import annotations

import logging

from sqlmodel import Session, select

from app.database import engine
from app.models import SolverOutputAttempt
from app.services.graph.asset_service import pre_render_attempt_graph
from app.worker import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="render_attempt_graph", soft_time_limit=10, time_limit=12)
def render_attempt_graph(attempt_id: str) -> bool:
    with Session(engine) as session:
        attempt = session.exec(select(SolverOutputAttempt).where(SolverOutputAttempt.attempt_id == attempt_id)).first()
        if attempt is None or attempt.user_id is None:
            logger.info("graph_worker skip attempt_id=%s reason=attempt_missing", attempt_id)
            return False
        ok = pre_render_attempt_graph(session, attempt_id=attempt_id, user_id=attempt.user_id, theme="light")
        logger.info("graph_worker done attempt_id=%s ok=%s", attempt_id, ok)
        return ok
