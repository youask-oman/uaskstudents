
from typing import Optional, Dict, Any, Tuple
from datetime import datetime
from sqlmodel import Session, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import SQLAlchemyError
import logging
from app.models import CanonicalProblem, CanonicalSolution
from app.config import get_settings

class CacheService:
    def __init__(self):
        self.settings = get_settings()
        self._logger = logging.getLogger(__name__)

    def get_cached_solution(self, session: Session, canonical_key: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves a valid solution for given canonical key if it exists and passes verification.
        Refreshes 'last_seen_at' stats on hit.
        """
        try:
            # 1. Lookup Problem with JOIN to Solution (single query)
            stmt = select(CanonicalProblem, CanonicalSolution).join(
                CanonicalSolution, CanonicalProblem.id == CanonicalSolution.problem_id, isouter=True
            ).where(CanonicalProblem.normalized_problem_hash == canonical_key)
            
            result = session.exec(stmt).first()
            
            if not result:
                return None
                
            problem, solution = result
            
            if not problem:
                return None

            # 2. Update Hit Stats (atomic operation)
            problem.last_seen_at = datetime.utcnow()
            problem.seen_count += 1
            session.add(problem)
            
            if solution:
                # Update solution stats
                solution.last_served_at = datetime.utcnow()
                solution.served_count += 1
                session.add(solution)
            
            # Single commit for all updates
            session.commit()
            
            if solution:
                return solution.solution_json
                
            return None
            
        except SQLAlchemyError as e:
            session.rollback()
            self._logger.error(f"Database error in get_cached_solution: {e}")
            return None
        except Exception as e:
            session.rollback()
            self._logger.error(f"Unexpected error in get_cached_solution: {e}")
            return None

    def store_solution(self, session: Session, 
                       key: str, 
                       text: str, 
                       intent: str, 
                       math_obj: str, 
                       latex_blocks: list, 
                       assumptions: dict, 
                       solution_json: dict) -> int:
        """
        Upserts the CanonicalProblem and CanonicalSolution.
        Guarantees uniqueness via DB constraints.
        """
        
        # 1. Upsert Problem
        # Use simple check-then-insert pattern if UPSERT is too complex with SQLModel, 
        # BUT user strictly requested UPSERT for race safety.
        # SQLModel doesn't native support upsert syntax easily, gotta use Core.
        
        versions = {
            "prompt_version": self.settings.PROMPT_VERSION,
            "solver_version": self.settings.SOLVER_VERSION,
            "schema_version": self.settings.SCHEMA_VERSION
        }

        insert_stmt = pg_insert(CanonicalProblem).values(
            normalized_problem_hash=key,
            normalized_text=text,
            intent=intent,
            canonical_math_object=math_obj,
            assumptions_hash=str(hash(str(assumptions))), # simple hash for now
            normalized_latex_blocks=latex_blocks,
            language="en",
            prompt_version=versions["prompt_version"],
            solver_version=versions["solver_version"],
            schema_version=versions["schema_version"],
            created_at=datetime.utcnow(),
            last_seen_at=datetime.utcnow(),
            seen_count=1
        )
        
        do_update_stmt = insert_stmt.on_conflict_do_update(
            index_elements=['normalized_problem_hash'],
            set_={
                "last_seen_at": datetime.utcnow(),
                "seen_count": CanonicalProblem.seen_count + 1
            }
        ).returning(CanonicalProblem.id)
        
        # Execute
        try:
            result = session.exec(do_update_stmt).first()
            problem_id = result # It might return a tuple or integer depending on driver
            
            # Determine strict ID (SQLModel exec on Core stmt might return Row)
            if hasattr(result, 'id'):
                problem_id = result.id
            elif isinstance(result, tuple) or isinstance(result, list): # Row
                problem_id = result[0]
            
            if not problem_id:
                 # Fallback lookup if upsert returned nothing (shouldn't happen with returning)
                 p = session.exec(select(CanonicalProblem).where(CanonicalProblem.normalized_problem_hash == key)).first()
                 problem_id = p.id

            # 2. Store Solution (Assuming 1:1 for this flow)
            # Use atomic upsert to prevent race conditions
            insert_sol_stmt = pg_insert(CanonicalSolution).values(
                problem_id=problem_id,
                solution_json=solution_json,
                verification_status="pending", # Default
                prompt_version=versions["prompt_version"],
                served_count=1,
                created_at=datetime.utcnow(),
                last_served_at=datetime.utcnow()
            ).on_conflict_do_nothing(
                index_elements=['problem_id']
            )
            
            session.exec(insert_sol_stmt)
            session.commit()
            self._logger.info(f"Stored new solution for problem_id: {problem_id}")
            
        except SQLAlchemyError as e:
            session.rollback()
            self._logger.error(f"Database error storing solution: {e}")
            # Check if solution already exists (race condition)
            existing_sol = session.exec(
                select(CanonicalSolution).where(CanonicalSolution.problem_id == problem_id)
            ).first()
            if existing_sol:
                self._logger.info(f"Solution already exists for problem_id: {problem_id} (race condition)")
            else:
                raise e
        except Exception as e:
            session.rollback()
            self._logger.error(f"Unexpected error storing solution: {e}")
            raise e

        return problem_id

cache_service = CacheService()
