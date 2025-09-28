
"""
playbooks_loader.py
Load YAML playbooks and select the ones whose 'applies_if' evaluates True
against the 'summary' dict from suggest_as_dict(df).
"""

from typing import List, Dict, Any
import os, yaml

def load_playbooks(directory: str) -> List[Dict[str, Any]]:
    pbs = []
    for name in sorted(os.listdir(directory)):
        if not name.endswith((".yml", ".yaml")):
            continue
        with open(os.path.join(directory, name), "r", encoding="utf-8") as f:
            pbs.append(yaml.safe_load(f))
    return pbs

def _safe_eval(expr: str, summary: Dict[str, Any]) -> bool:
    # Very restricted eval: only allow 'summary' in globals, no builtins
    try:
        return bool(eval(expr, {"__builtins__": {}}, {"summary": summary}))
    except Exception:
        return False

def select_playbooks(playbooks: List[Dict[str, Any]], summary: Dict[str, Any]) -> List[Dict[str, Any]]:
    selected = []
    for pb in playbooks:
        expr = pb.get("applies_if", "False")
        if _safe_eval(expr, summary):
            selected.append(pb)
    return selected
