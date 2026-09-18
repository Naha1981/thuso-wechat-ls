from __future__ import annotations

from typing import Any


def template_value(key: str, variables: dict[str, Any]) -> Any:
    current: Any = variables
    for part in key.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None
    return current


def render(node: Any, variables: dict[str, Any]) -> Any:
    if isinstance(node, dict):
        return {k: render(v, variables) for k, v in node.items()}
    if isinstance(node, list):
        return [render(v, variables) for v in node]
    if isinstance(node, str) and node.startswith("{{") and node.endswith("}}") and node.count("{{") == 1:
        key = node[2:-2].strip()
        value = template_value(key, variables)
        return value if value is not None else node
    if isinstance(node, str):
        value = node
        for key, item in variables.items():
            value = value.replace("{{" + key + "}}", str(item))
        return value
    return node


def json_path(value: Any, path: str | None) -> Any:
    if not path:
        return value
    current = value
    for part in path.split("."):
        if isinstance(current, list):
            current = current[int(part)]
        elif isinstance(current, dict):
            current = current[part]
        else:
            raise KeyError(path)
    return current
