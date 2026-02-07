from typing import Optional, Dict, Any, Union
from pydantic import BaseModel

class PromptProfile(BaseModel):
    """
    Validation profile for a solver request.
    Created from resolved prompt binding.
    """
    tier: str
    mode: str # minimal, detailed, fast, etc.
    
    system_prompt_content: str
    developer_prompt_content: Optional[str] = None
    json_schema_content: Union[Dict[str, Any], str] = {}
    
    max_output_tokens: Optional[int] = None
    max_steps: Optional[int] = None
    
    allow_detailed: bool = False
    allow_visuals_only_if_asked: bool = False
    
    prompt_binding_meta: Optional[Dict[str, Any]] = None
    
    # Computed helpers if needed
    
def get_prompt_profile(*args, **kwargs):
    """Legacy helper if needed, but SolverV3 constructs directly now."""
    raise NotImplementedError("Use ProfileResolver or construct PromptProfile directly.")
