"""
Prompt Registry System for Math Solver V3.

Provides centralized management of prompt templates with versioning support.
Templates are loaded from static_design/ directory and can be overridden via environment variables.
"""

import os
import json
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, Optional, Any
from datetime import datetime


@dataclass
class PromptTemplate:
    """Represents a versioned prompt template."""
    name: str
    version: str
    content: str
    schema: Optional[Dict[str, Any]] = None
    loaded_at: datetime = None
    source_file: Optional[Path] = None
    
    def __post_init__(self):
        if self.loaded_at is None:
            self.loaded_at = datetime.now()


class PromptRegistry:
    """
    Registry for managing prompt templates with versioning.
    
    Usage:
        registry = PromptRegistry()
        system_prompt = registry.get_prompt("solver_system", "v3")
        schema = registry.get_schema("na_math_solver")
    """
    
    def __init__(self, base_path: Optional[Path] = None):
        """
        Initialize the prompt registry.
        
        Args:
            base_path: Base directory for prompt templates. 
                      Defaults to project_root/static_design
        """
        if base_path is None:
            # Default to static_design directory
            project_root = Path(__file__).parent.parent.parent.parent
            project_default = project_root / "static_design"

            # Allow environment override for base prompt path
            env_base_path = os.environ.get("PROMPT_BASE_PATH")
            if env_base_path:
                candidate = Path(env_base_path)
                if candidate.exists():
                    base_path = candidate
                else:
                    print(f"[PromptRegistry] WARNING: PROMPT_BASE_PATH not found: {candidate}")

            if base_path is None:
                # Fallback for containers mounting /static_design
                container_path = Path("/static_design")
                if container_path.exists():
                    base_path = container_path
                else:
                    base_path = project_default
          # Allow environment override for base prompt path
            env_base_path = os.environ.get("PROMPT_BASE_PATH")
            if env_base_path:
                base_path = Path(env_base_path)
            elif not base_path.exists():
                # Fallback for containers mounting /static_design
                container_path = Path("/static_design")
                if container_path.exists():
                    base_path = container_path
        self.base_path = Path(base_path)
        self.prompts: Dict[str, PromptTemplate] = {}
        self._schema_cache: Dict[str, Dict[str, Any]] = {}
        
        # Check for environment override
        override_path = os.environ.get("PROMPT_OVERRIDE_PATH")
        if override_path:
            self.override_path = Path(override_path)
            print(f"[PromptRegistry] Using override path: {self.override_path}")
        else:
            self.override_path = None
        
        # Load all prompts on initialization
        self._load_prompts()
    
    def _load_prompts(self):
        """Load all prompt templates from the base path."""
        if not self.base_path.exists():
            raise FileNotFoundError(f"Prompt base path does not exist: {self.base_path}")
        
        print(f"[PromptRegistry] Loading prompts from: {self.base_path}")
        
        # Load solver_system.txt (system prompt)
        system_file = self.base_path / "solver_system.txt"
        if system_file.exists():
            self._load_prompt_file(system_file, "solver_system", "v3")
        else:
            print(f"[PromptRegistry] WARNING: solver_system.txt not found at {system_file}")
        
        # Load solver_developer.txt (contains JSON schema)
        developer_file = self.base_path / "solver_developer.txt"
        if developer_file.exists():
            self._load_schema_file(developer_file, "na_math_solver")
        else:
            print(f"[PromptRegistry] WARNING: solver_developer.txt not found at {developer_file}")
        
        print(f"[PromptRegistry] Loaded {len(self.prompts)} prompts")
    
    def _load_prompt_file(self, file_path: Path, name: str, version: str):
        """Load a single prompt file."""
        try:
            content = file_path.read_text(encoding='utf-8')
            
            # Check for override
            if self.override_path:
                override_file = self.override_path / file_path.name
                if override_file.exists():
                    content = override_file.read_text(encoding='utf-8')
                    file_path = override_file
                    print(f"[PromptRegistry] Using override for {name}: {override_file}")
            
            template = PromptTemplate(
                name=name,
                version=version,
                content=content,
                source_file=file_path
            )
            
            key = f"{name}:{version}"
            self.prompts[key] = template
            
            # Also store as "latest"
            latest_key = f"{name}:latest"
            self.prompts[latest_key] = template
            
            print(f"[PromptRegistry] Loaded prompt: {name} v{version} ({len(content)} chars)")
            
        except Exception as e:
            print(f"[PromptRegistry] ERROR loading {file_path}: {e}")
            raise
    
    def _load_schema_file(self, file_path: Path, schema_name: str):
        """Load a JSON schema file (solver_developer.txt contains the schema)."""
        try:
            content = file_path.read_text(encoding='utf-8')
            
            # Check for override
            if self.override_path:
                override_file = self.override_path / file_path.name
                if override_file.exists():
                    content = override_file.read_text(encoding='utf-8')
                    file_path = override_file
                    print(f"[PromptRegistry] Using override for schema {schema_name}: {override_file}")
            
            # Parse as JSON
            schema = json.loads(content)
            
            # Cache the schema
            self._schema_cache[schema_name] = schema
            
            # Also store as a prompt template for completeness
            template = PromptTemplate(
                name=f"{schema_name}_schema",
                version="v3",
                content=content,
                schema=schema,
                source_file=file_path
            )
            
            key = f"{schema_name}_schema:v3"
            self.prompts[key] = template
            self.prompts[f"{schema_name}_schema:latest"] = template
            
            print(f"[PromptRegistry] Loaded schema: {schema_name} ({len(schema.get('properties', {}))} top-level properties)")
            
        except json.JSONDecodeError as e:
            print(f"[PromptRegistry] ERROR: {file_path} is not valid JSON: {e}")
            raise
        except Exception as e:
            print(f"[PromptRegistry] ERROR loading schema from {file_path}: {e}")
            raise
    
    def get_prompt(self, name: str, version: str = "latest", **kwargs) -> str:
        """
        Get a prompt template by name and version.
        
        Args:
            name: Prompt name (e.g., "solver_system")
            version: Version (e.g., "v3", "latest")
            **kwargs: Variables to substitute in the prompt (future enhancement)
        
        Returns:
            Prompt content as string
        
        Raises:
            KeyError: If prompt not found
        """
        key = f"{name}:{version}"
        
        if key not in self.prompts:
            available = [k for k in self.prompts.keys() if k.startswith(name)]
            raise KeyError(
                f"Prompt '{name}' version '{version}' not found. "
                f"Available: {available}"
            )
        
        template = self.prompts[key]
        content = template.content
        
        # Variable substitution (if kwargs provided)
        if kwargs:
            for key, value in kwargs.items():
                placeholder = f"{{{{{key}}}}}"
                content = content.replace(placeholder, str(value))
        
        return content
    
    def get_schema(self, schema_name: str = "na_math_solver") -> Dict[str, Any]:
        """
        Get a JSON schema by name.
        
        Args:
            schema_name: Schema name (e.g., "na_math_solver")
        
        Returns:
            JSON schema as dictionary
        
        Raises:
            KeyError: If schema not found
        """
        if schema_name not in self._schema_cache:
            raise KeyError(
                f"Schema '{schema_name}' not found. "
                f"Available: {list(self._schema_cache.keys())}"
            )
        
        return self._schema_cache[schema_name]
    
    def list_prompts(self) -> list:
        """List all available prompts."""
        return [
            {
                "name": template.name,
                "version": template.version,
                "source": str(template.source_file),
                "loaded_at": template.loaded_at.isoformat(),
                "size": len(template.content)
            }
            for template in self.prompts.values()
        ]
    
    def reload(self):
        """Reload all prompts from disk."""
        print("[PromptRegistry] Reloading all prompts...")
        self.prompts.clear()
        self._schema_cache.clear()
        self._load_prompts()


# Singleton instance
_registry_instance: Optional[PromptRegistry] = None


def get_prompt_registry() -> PromptRegistry:
    """Get the global prompt registry instance."""
    global _registry_instance
    if _registry_instance is None:
        _registry_instance = PromptRegistry()
    return _registry_instance


# Convenience functions
def get_prompt(name: str, version: str = "latest", **kwargs) -> str:
    """Get a prompt from the global registry."""
    return get_prompt_registry().get_prompt(name, version, **kwargs)


def get_schema(schema_name: str = "na_math_solver") -> Dict[str, Any]:
    """Get a JSON schema from the global registry."""
    return get_prompt_registry().get_schema(schema_name)


if __name__ == "__main__":
    # Test the registry
    print("Testing Prompt Registry...")
    registry = PromptRegistry()
    
    print("\n--- Available Prompts ---")
    for prompt_info in registry.list_prompts():
        print(f"  {prompt_info['name']} v{prompt_info['version']}: {prompt_info['size']} bytes")
    
    print("\n--- Testing get_prompt ---")
    try:
        system_prompt = registry.get_prompt("solver_system", "v3")
        print(f"solver_system loaded: {len(system_prompt)} characters")
        print(f"First 200 chars: {system_prompt[:200]}...")
    except KeyError as e:
        print(f"Error: {e}")
    
    print("\n--- Testing get_schema ---")
    try:
        schema = registry.get_schema("na_math_solver")
        print(f"na_math_solver schema loaded: {len(schema.get('properties', {}))} properties")
        print(f"Required fields: {schema.get('required', [])}")
    except KeyError as e:
        print(f"Error: {e}")
