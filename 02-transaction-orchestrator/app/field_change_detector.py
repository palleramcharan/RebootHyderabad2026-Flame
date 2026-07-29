from typing import Any, Dict, List, Optional


def detect_changes(previous: Optional[Dict[str, Any]], current: Dict[str, Any]) -> List[Dict[str, Any]]:
    changes = []
    if not previous:
        for key, value in current.items():
            if isinstance(value, (str, int, float, bool)) and not key.startswith("_"):
                changes.append({
                    "field": key,
                    "oldValue": None,
                    "newValue": str(value) if not isinstance(value, str) else value,
                })
        return changes

    all_keys = set(list(previous.keys()) + list(current.keys()))
    for key in all_keys:
        old_val = previous.get(key)
        new_val = current.get(key)
        if old_val != new_val:
            if isinstance(new_val, (str, int, float, bool)) or isinstance(old_val, (str, int, float, bool)):
                changes.append({
                    "field": key,
                    "oldValue": str(old_val) if old_val is not None else None,
                    "newValue": str(new_val) if new_val is not None else None,
                })
            elif isinstance(new_val, dict) or isinstance(old_val, dict):
                nested = detect_changes(
                    old_val if isinstance(old_val, dict) else {},
                    new_val if isinstance(new_val, dict) else {},
                )
                for n in nested:
                    n["field"] = f"{key}.{n['field']}"
                changes.extend(nested)
    return changes
