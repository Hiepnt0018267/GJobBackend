"""One-entity best-effort lifecycle task. No business writes, extraction or queue.

Fresh session owned by the task; never captures request ORM/session objects.
Lifecycle response is already committed; embedding failure cannot undo it.
"""
import logging

from app.core import database
from app.services.matching_input_service import MatchingInputService
from app.services.ranking_cache import RankingCache

logger = logging.getLogger(__name__)


async def precompute_entity(kind, entity_id):
    try:
        with database.SessionLocal() as db:
            inputs = MatchingInputService(db)
            canonical = (inputs.build_cv_input(entity_id) if kind == "cv"
                         else inputs.build_job_input(entity_id, require_approved=False))
        await RankingCache().precompute(kind, canonical)
    except Exception:
        logger.warning("Ranking lifecycle precompute unavailable kind=%s", kind)
