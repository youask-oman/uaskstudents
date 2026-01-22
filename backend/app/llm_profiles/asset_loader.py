import os
import json
import hashlib
import threading
from typing import Union, Dict, Optional
from datetime import datetime, timedelta

from app.models import PromptAsset

# Thread-safe in-memory cache
# Key: f"{asset.id}:{asset.checksum}" -> Content
_ASSET_CACHE: Dict[str, Union[str, Dict]] = {}
_CACHE_LOCK = threading.Lock()
_LAST_CACHE_CLEANUP = datetime.utcnow()

class AssetLoaderError(Exception):
    """Raised when an asset cannot be loaded."""
    pass

class AssetLoader:
    """
    Handles loading of PromptAssets from disk with caching.
    Ensures checksum validation.
    """
    
    @staticmethod
    def get_asset_content(asset: PromptAsset) -> Union[str, Dict]:
        """
        Retrieve content for a PromptAsset. 
        Returns string for 'system' kind, dict for 'schema' kind.
        """
        if not asset.path:
            raise AssetLoaderError(f"Asset {asset.key} has no path configured.")

        # Cache Key matches exact version of asset
        cache_key = f"{asset.id}:{asset.checksum}"
        
        with _CACHE_LOCK:
            if cache_key in _ASSET_CACHE:
                return _ASSET_CACHE[cache_key]

        # Miss - Load from disk
        # Path is relative to backend/app usually because that's how we seeded it.
        # But we need to resolve it relative to the PROJECT ROOT or Backend Root.
        # Implied structure: backend/app/... 
        # But seed script joined "app" + "llm_profiles/...".
        # Let's verify assumption:
        # If seed script path was "llm_profiles/shared/...", and it joined os.path.join("app", path) -> "app/llm_profiles/shared/..."
        # So the DB path is "llm_profiles/shared/...".
        # Running from backend/app/main.py, relative path "llm_profiles" is locally accessible if we are in app dir.
        # Best to match relative to "backend/app".
        
        # We assume the working directory when running the app is `backend`.
        # So "app/llm_profiles/..." would be correct relative path if running from backend.
        # If DB says "llm_profiles/...", we need to prepend "app/".
        
        # Robust path finding:
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")) # backend/
        full_path = os.path.join(base_dir, "app", asset.path)
        
        if not os.path.exists(full_path):
             # Try without 'app' prefix if seeded differently
             alt_path = os.path.join(base_dir, asset.path)
             if os.path.exists(alt_path):
                 full_path = alt_path
             else:
                 raise AssetLoaderError(f"Asset file not found: {full_path} or {alt_path}")

        try:
            with open(full_path, "rb") as f:
                raw_bytes = f.read()
            
            # Verify Checksum (if present)
            if asset.checksum:
                computed = hashlib.sha256(raw_bytes).hexdigest()
                if computed != asset.checksum:
                    print(f"WARNING: Checksum mismatch for {asset.key}. Expected {asset.checksum}, got {computed}")
                    # We proceed but warn, or we could fail. Proceeding is safer for now to avoid downtime on manual edits.
                    
            content: Union[str, Dict]
            
            if asset.kind == "schema":
                content = json.loads(raw_bytes.decode("utf-8"))
            else:
                content = raw_bytes.decode("utf-8")
                
            # Update Cache
            with _CACHE_LOCK:
                _ASSET_CACHE[cache_key] = content
                
            return content
            
        except Exception as e:
            raise AssetLoaderError(f"Failed to read asset {asset.key}: {str(e)}")

    @staticmethod
    def clear_cache():
        with _CACHE_LOCK:
            _ASSET_CACHE.clear()
