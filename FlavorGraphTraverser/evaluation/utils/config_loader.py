"""
Configuration Loader

Loads conditions configuration from YAML files.
"""

import hashlib
import json
import yaml
from pathlib import Path
from typing import Any, Dict, Optional

# Condition keys that are labels only and do not change what the model sees.
_FINGERPRINT_IGNORED_KEYS = {"name", "description"}


def load_conditions_config(config_path: str = None) -> Dict[str, Any]:
    """
    Load conditions configuration from YAML.
    
    Args:
        config_path: Path to conditions.yaml (optional, defaults to configs/conditions.yaml)
        
    Returns:
        Dict with condition configurations
        
    Example:
        >>> config = load_conditions_config()
        >>> config["conditions"]["no_tool"]["system_prompt"]
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


def condition_fingerprint(condition_config: Dict[str, Any], common_config: Dict[str, Any],
                          content: Optional[Dict[str, Any]] = None) -> str:
    """
    Short hash of everything in a condition (plus common settings) that affects a run:
    system prompt, tool settings, label resolution, graph rendering, draft flag,
    temperature, token limits. Used to stamp results and to invalidate cached
    results when a condition is edited (e.g. a draft prompt is finalized).

    `content` carries what the config alone does not determine: the rendered system
    prompt of graph_in_context conditions (graph + alias table) and the resolver's
    alias/display tables. QuestionEvaluator.content_fingerprint_inputs() builds it.
    It is left out of the payload when empty, so conditions without such content
    (no_tool, tool, tool_rerun) keep the fingerprints of the original runs.
    """
    from ..tools import get_tool_definitions  # local import: avoid import cycle

    payload = {
        "condition": {k: v for k, v in condition_config.items() if k not in _FINGERPRINT_IGNORED_KEYS},
        "common": common_config,
        "tools": get_tool_definitions() if condition_config.get("tools_enabled") else None,
    }
    if content:
        payload["content"] = content
    blob = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:12]
