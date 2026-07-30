"""Class colours come from one place, cover all twelve classes, and are distinct.

Before this there were five sources. `base.css` styled six classes, an orphaned
`classes.css` styled the same six with fifteen different values, and a runtime
injector (`config_api.CLASS_COLORS` -> `/api/config/class_colors` ->
`adventure.js`) `!important`-overrode both on /adventure only -- so a Fighter's
badge was #7a3314 on the dashboard and #301d0b in the dungeon, and six of the
twelve classes had no colour at all outside the dungeon.

The palette itself also failed: `bard` and `paladin` were the same hue, three
golds sat within 6 degrees, and `fighter`, `warlock` and `rogue` were below the
4.5:1 contrast floor.

Spec: docs/superpowers/specs/2026-07-29-class-colour-unification-design.md
"""

import colorsys
import itertools
import pathlib
import re

TOKENS = pathlib.Path(__file__).resolve().parents[1] / "app" / "static" / "css" / "tokens.css"

CLASSES = [
    "fighter",
    "rogue",
    "mage",
    "cleric",
    "ranger",
    "druid",
    "barbarian",
    "bard",
    "monk",
    "paladin",
    "sorcerer",
    "warlock",
]

# The two realm grounds a class colour must be legible against.
GROUNDS = {"warm": "#0f0c09", "cold": "#0b0d11"}
CONTRAST_FLOOR = 4.5


def _hues():
    text = TOKENS.read_text()
    found = dict(re.findall(r"--class-([a-z]+)\s*:\s*(#[0-9a-fA-F]{6})\s*;", text))
    return {k: v for k, v in found.items() if k in CLASSES}


def _rel_luminance(hex_colour):
    parts = [int(hex_colour[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    parts = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in parts]
    return 0.2126 * parts[0] + 0.7152 * parts[1] + 0.0722 * parts[2]


def _contrast(a, b):
    hi, lo = sorted((_rel_luminance(a), _rel_luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def _hsl(hex_colour):
    r, g, b = (int(hex_colour[i : i + 2], 16) / 255 for i in (1, 3, 5))
    h, lightness, s = colorsys.rgb_to_hls(r, g, b)
    return h * 360, s * 100, lightness * 100


def test_every_class_has_a_hue():
    hues = _hues()
    missing = [c for c in CLASSES if c not in hues]
    assert not missing, f"no --class-* hue for: {missing}"


def test_every_class_has_derived_bg_fg_and_border():
    """Six classes used to have these and six did not, which is why a runtime
    injector existed to paper over the gap."""
    text = TOKENS.read_text()
    for name in CLASSES:
        for part in ("bg", "fg", "border"):
            assert re.search(rf"--class-{name}-{part}\s*:", text), f"--class-{name}-{part} is not defined"


def test_derived_values_reference_the_hue_rather_than_restating_a_colour():
    """A derived value that hard-codes a hex is a second source of truth."""
    text = TOKENS.read_text()
    for name in CLASSES:
        for part in ("bg", "fg", "border"):
            m = re.search(rf"--class-{name}-{part}\s*:([^;]+);", text)
            assert m, f"--class-{name}-{part} is not defined"
            value = m.group(1)
            assert f"--class-{name}" in value, f"--class-{name}-{part} must derive from --class-{name}, got:{value}"
            assert "#" not in value, f"--class-{name}-{part} hard-codes a colour:{value}"


def test_every_hue_clears_the_contrast_floor_in_both_realms():
    for name, hue in _hues().items():
        for realm, ground in GROUNDS.items():
            ratio = _contrast(hue, ground)
            assert ratio >= CONTRAST_FLOOR, f"--class-{name} is {ratio:.2f}:1 on the {realm} ground"


def test_no_two_classes_are_close_in_both_hue_and_lightness():
    """`bard` and `paladin` used to be the same hue, and three golds sat within
    six degrees. Hue alone is not the test -- two colours may share a hue if
    lightness separates them clearly, as cleric and paladin now do."""
    hues = _hues()
    collisions = []
    for a, b in itertools.combinations(sorted(hues), 2):
        ha, _, la = _hsl(hues[a])
        hb, _, lb = _hsl(hues[b])
        dh = min(abs(ha - hb), 360 - abs(ha - hb))
        dl = abs(la - lb)
        if dh < 12 and dl < 18:
            collisions.append(f"{a}/{b}: {dh:.0f} deg hue, {dl:.0f} lightness")
    assert not collisions, "indistinguishable class colours: " + "; ".join(collisions)


def test_the_runtime_injector_is_gone():
    """A palette a script rewrites at runtime is not a source of truth."""
    root = TOKENS.parents[3]
    assert not (root / "app" / "static" / "css" / "classes.css").exists(), "orphaned classes.css still present"
    assert "CLASS_COLORS" not in (root / "app" / "routes" / "config_api.py").read_text()
    assert "class_colors" not in (root / "app" / "static" / "js" / "adventure.js").read_text()
