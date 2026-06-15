"""Compose item display names from prefix + base + suffix."""


def compose_name(prefix: str | None, base: str, suffix: str | None) -> str:
    parts = []
    if prefix:
        parts.append(prefix)
    parts.append(base)
    name = " ".join(parts)
    if suffix:
        name = f"{name} {suffix}"
    return name
