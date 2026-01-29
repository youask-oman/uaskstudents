
from typing import Optional, Dict, List, Any
from datetime import datetime
import json
import hashlib
from sqlmodel import Session, select, desc

from app.models import SystemConfig, SystemConfigVersion, User

def _simple_diff(old: Dict, new: Dict) -> Dict:
    """Simple diff implementation without external dependencies."""
    diff = {"added": {}, "removed": {}, "changed": {}}
    
    all_keys = set(old.keys()) | set(new.keys())
    for key in all_keys:
        if key not in old:
            diff["added"][key] = new[key]
        elif key not in new:
            diff["removed"][key] = old[key]
        elif old[key] != new[key]:
            diff["changed"][key] = {"old": old[key], "new": new[key]}
    
    return diff if any(diff.values()) else {}

class AdminConfigService:
    def get_active_config(self, session: Session, config_type: str) -> Dict[str, Any]:
        """
        Get the currently active configuration for the given type.
        Falls back to SystemConfig (legacy) if no versioned config exists yet.
        """
        # 1. Try to get latest version
        statement = select(SystemConfigVersion).where(
            SystemConfigVersion.config_type == config_type
        ).order_by(desc(SystemConfigVersion.version))
        latest = session.exec(statement).first()
        
        if latest:
            return latest.value
            
        # 2. Fallback to legacy SystemConfig
        legacy = session.get(SystemConfig, config_type)
        if legacy:
            try:
                return json.loads(legacy.value)
            except:
                pass
                
        return {} # Return empty (or default) if nothing found
        
    def update_config(
        self, 
        session: Session, 
        config_type: str, 
        new_value: Dict[str, Any], 
        user_id: int, 
        change_msg: str
    ) -> SystemConfigVersion:
        """
        Update configuration:
        1. Validate (TODO: Add schema validation schemas)
        2. Calculate Diff
        3. Create new Version
        4. Update Legacy SystemConfig (for compatibility)
        """
        
        # 1. Get current active to compute diff
        current_value = self.get_active_config(session, config_type)
        
        # Compute Diff using simple implementation
        diff_json = _simple_diff(current_value, new_value)
        
        # Checksum
        content_str = json.dumps(new_value, sort_keys=True)
        check_sum = hashlib.sha256(content_str.encode()).hexdigest()
        
        # Get next version number
        statement = select(SystemConfigVersion).where(
            SystemConfigVersion.config_type == config_type
        ).order_by(desc(SystemConfigVersion.version))
        last_version = session.exec(statement).first()
        next_version = (last_version.version + 1) if last_version else 1
        
        # Create Version
        new_version = SystemConfigVersion(
            config_type=config_type,
            version=next_version,
            value=new_value,
            diff_json=diff_json,
            check_sum=check_sum,
            created_by=user_id,
            change_msg=change_msg
        )
        session.add(new_version)
        
        # Update Legacy SystemConfig (Single Source of Truth for reads usually)
        legacy = session.get(SystemConfig, config_type)
        if not legacy:
            legacy = SystemConfig(key=config_type, value=content_str)
            session.add(legacy)
        else:
            legacy.value = content_str
            legacy.updated_at = datetime.utcnow()
            session.add(legacy)
            
        session.commit()
        session.refresh(new_version)
        return new_version

    def get_history(self, session: Session, config_type: str, limit: int = 50) -> List[SystemConfigVersion]:
        statement = select(SystemConfigVersion).where(
            SystemConfigVersion.config_type == config_type
        ).order_by(desc(SystemConfigVersion.version)).limit(limit)
        return session.exec(statement).all()

    def revert_config(
        self, 
        session: Session, 
        version_id: int, 
        user_id: int, 
        reason_msg: str
    ) -> SystemConfigVersion:
        """
        Revert to a specific version.
        Creates a *NEW* version with the old content.
        """
        target_version = session.get(SystemConfigVersion, version_id)
        if not target_version:
            raise ValueError("Target version not found")
            
        new_msg = f"Revert to v{target_version.version}: {reason_msg}"
        
        return self.update_config(
            session=session,
            config_type=target_version.config_type,
            new_value=target_version.value,
            user_id=user_id,
            change_msg=new_msg
        )

admin_config_service = AdminConfigService()
