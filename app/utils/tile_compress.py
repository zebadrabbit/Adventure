"""Utility helpers for compact encoding of tile coordinate sets.

Format strategy:
  - Input: semicolon separated 'x,y' pairs (unordered)
  - We sort coordinates, delta-encode x and y separately, prefix with 'D:' marker.
  - If compressed payload is not shorter than raw, we return the raw source.

Compressed grammar (simple):
  D:x0,y0|dx1,dy1|dx2,dy2|...

Limitations:
  - Assumes non-negative integer coordinates.
  - Falls back to raw if parsing fails.
"""

from __future__ import annotations


def compress_tiles(raw: str) -> str:
    """Return compressed representation of a semicolon ``x,y`` list.

    The compressor sorts coordinates, delta-encodes successive x and y values
    independently, and prefixes with ``D:``. If the encoded payload is not
    shorter than the original, the original string is returned unchanged.

    Args:
        raw: Semicolon separated list of ``x,y`` integer pairs (e.g. ``"1,2;3,4"``).

    Returns:
        Compressed string starting with ``D:`` or the original input if no
        size benefit or any parsing error occurs.
    """
    if not raw or ";" not in raw:
        return raw
    try:
        coords = []
        for part in raw.split(";"):
            if not part:
                continue
            x_s, y_s = part.split(",")
            x, y = int(x_s), int(y_s)
            coords.append((x, y))
        if not coords:
            return ""
        coords.sort()
        pieces = []
        prev_x, prev_y = None, None
        for x, y in coords:
            if prev_x is None:
                pieces.append(f"{x},{y}")
            else:
                pieces.append(f"{x-prev_x},{y-prev_y}")
            prev_x, prev_y = x, y
        compressed = "D:" + "|".join(pieces)
        return compressed if len(compressed) < len(raw) else raw
    except Exception:
        return raw


def decompress_tiles(data: str) -> str:
    """Inverse of :func:`compress_tiles`.

    Reconstructs the original semicolon separated coordinate list from a
    ``D:`` delta-encoded string. If the input does not start with ``D:`` the
    data is returned unchanged. On parsing failure an empty string is returned
    (caller should treat empty as a failed decode and ignore).

    Args:
        data: Compressed delta string or already-raw coordinate list.

    Returns:
        Raw coordinate list string or empty string on decode failure.
    """
    if not data or not data.startswith("D:"):
        return data
    try:
        body = data[2:]
        parts = body.split("|")
        coords = []
        prev_x, prev_y = None, None
        for idx, token in enumerate(parts):
            x_s, y_s = token.split(",")
            dx, dy = int(x_s), int(y_s)
            if prev_x is None:
                x, y = dx, dy
            else:
                x, y = prev_x + dx, prev_y + dy
            coords.append(f"{x},{y}")
            prev_x, prev_y = x, y
        return ";".join(coords)
    except Exception:
        return ""


__all__ = ["compress_tiles", "decompress_tiles"]
