import json


def build_alias_map(control_registry):
    alias_map = {}

    for canonical, metadata in control_registry.items():
        alias_map[canonical.lower()] = canonical
        for alias in metadata.get("aliases", []):
            alias_map[alias.strip().lower()] = canonical

    return alias_map


def normalize_evidence(raw_evidence, control_registry_path="control_registry.json"):
    with open(control_registry_path) as f:
        control_registry = json.load(f)

    alias_map = build_alias_map(control_registry)
    normalized = {}

    for raw_key, raw_value in raw_evidence.items():
        key = str(raw_key).strip().lower()
        canonical_key = alias_map.get(key, raw_key)

        if isinstance(raw_value, bool):
            normalized[canonical_key] = 1.0 if raw_value else 0.0
        elif isinstance(raw_value, (int, float)):
            # Ensure value is between 0 and 1
            normalized[canonical_key] = max(0.0, min(1.0, float(raw_value)))
        elif isinstance(raw_value, str):
            lowered = raw_value.strip().lower()
            if lowered in {"true", "yes", "y", "1", "on"}:
                normalized[canonical_key] = 1.0
            elif lowered in {"false", "no", "n", "0", "off"}:
                normalized[canonical_key] = 0.0
            else:
                # Try to parse as float
                try:
                    val = float(raw_value)
                    normalized[canonical_key] = max(0.0, min(1.0, val))
                except ValueError:
                    normalized[canonical_key] = raw_value
        else:
            normalized[canonical_key] = raw_value

    return normalized

