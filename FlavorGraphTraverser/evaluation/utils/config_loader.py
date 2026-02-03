"""
Configuration Loader

Loads conditions configuration from YAML files.
"""

import yaml
from pathlib import Path
from typing import Dict, Any


def load_conditions_config(config_path: str = None) -> Dict[str, Any]:
    """
    Load conditions configuration from YAML.
    
    Args:
        config_path: Path to conditions.yaml (optional, defaults to configs/conditions.yaml)
        
    Returns:
        Dict with condition configurations
        
    Example:
        >>> config = load_conditions_config()
        >>> config["conditions"]["C0"]["system_prompt"]
        'You are an expert in coffee flavor analysis...'
    """
    if config_path is None:
        # Default to configs/conditions.yaml
        project_root = Path(__file__).parent.parent.parent.parent
        config_path = project_root / "configs" / "conditions.yaml"
    else:
        config_path = Path(config_path)
    
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    return config
