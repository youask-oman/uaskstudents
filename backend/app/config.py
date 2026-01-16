
import os
from functools import lru_cache

class Settings:
    def __init__(self):
        self.CANONICAL_CACHE_ENABLED = os.environ.get("CANONICAL_CACHE_ENABLED", "false").lower() == "true"
        self.SEMANTIC_CACHE_ENABLED = os.environ.get("SEMANTIC_CACHE_ENABLED", "false").lower() == "true"
        self.CACHE_WRITE_ENABLED = os.environ.get("CACHE_WRITE_ENABLED", "true").lower() == "true"
        self.CACHE_DEBUG_LOGS = os.environ.get("CACHE_DEBUG_LOGS", "false").lower() == "true"
        
        # Versioning
        self.PROMPT_VERSION = os.environ.get("PROMPT_VERSION", "v1.0")
        self.SCHEMA_VERSION = os.environ.get("SCHEMA_VERSION", "v3.0")
        self.SOLVER_VERSION = os.environ.get("SOLVER_VERSION", "v1.0")

@lru_cache()
def get_settings():
    return Settings()
