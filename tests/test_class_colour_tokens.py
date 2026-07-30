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
# NOTE: these are hardcoded, but only the cold one is fixed in tokens.css.
# --class-*-bg derives from --realm-bg, which in the town realm is --ui-bg --
# and app/models/theme.py:132 overwrites --ui-bg from Theme.body_bg at runtime.
# Every seeded theme is dark, so nothing fails today, but the guarantee below is
# scoped to the DEFAULT town ground; it is not unconditional across all themes.
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


# --- No stylesheet may be a second source ----------------------------------
# The three tests above all read tokens.css, so they say nothing about what the
# other 20-odd stylesheets do. That is exactly how two sources survived two
# audits: theme.css's twelve hardcoded badge rules got through the original
# sweep, and glass-theme.css's six `!important` gradients got through the
# unification sweep -- live on /combat, because combat.html:127 loads the
# "admin and account" dialect in `{% block head %}`, i.e. after theme.css.
# Neither was findable by grepping tokens.css. These two tests are.

CSS_DIR = TOKENS.parent
# The properties through which a class colour can actually reach the screen.
COLOUR_PROPS = {"background", "background-color", "color", "border", "border-color"}
_COMMENT = re.compile(r"/\*.*?\*/", re.S)
_RULE = re.compile(r"([^{}]*)\{([^{}]*)\}", re.S)
_CLASS_BADGE = re.compile(rf"\.({'|'.join(CLASSES)})-badge\b")


def _rules():
    """(path, selector, declarations) for every flat rule in app/static/css."""
    for path in sorted(CSS_DIR.glob("*.css")):
        text = _COMMENT.sub("", path.read_text())
        for match in _RULE.finditer(text):
            yield path, match.group(1).strip(), match.group(2)


def _declarations(block):
    for chunk in block.split(";"):
        prop, _, value = chunk.partition(":")
        if value:
            yield prop.strip().lower(), value.strip()


# Orphaned stylesheets that still carry a pre-token class palette. Exempt ONLY
# for as long as no template loads them -- test_the_exempt_orphans_are_still_
# unreachable below enforces that, so linking one turns this exemption back into
# a failure. tactical-theme.css (688 lines, six classes, hardcoded hexes) is
# already marked for deletion in DESIGN_SYSTEM.md's orphan table; it is a ninth
# source of class colour on disk but reaches no screen.
EXEMPT_ORPHANS = {"tactical-theme.css"}
TEMPLATES = TOKENS.parents[2] / "templates"


def _stylesheets_templates_load():
    refs = set()
    for path in TEMPLATES.rglob("*.html"):
        refs.update(re.findall(r"css/([A-Za-z0-9_-]+\.css)", path.read_text()))
    return refs


def test_no_stylesheet_sets_a_class_badge_colour_outside_the_tokens():
    """Every per-class badge colour must be a var(--class-*), in any file.

    A `.rogue-badge { background: <a literal> }` anywhere in app/static/css is
    a second palette by definition, whatever file it hides in.
    """
    offenders = {}
    for path, selector, block in _rules():
        if not _CLASS_BADGE.search(selector):
            continue
        for prop, value in _declarations(block):
            if prop in COLOUR_PROPS and "var(--class-" not in value:
                offenders.setdefault(path.name, []).append(f"{selector} {{ {prop}: {value} }}")

    live = [f"{name}: {d}" for name, decls in offenders.items() if name not in EXEMPT_ORPHANS for d in decls]
    assert not live, "class badge colour not read from a token:\n  " + "\n  ".join(live)

    unexpected = sorted(set(offenders) - EXEMPT_ORPHANS - _stylesheets_templates_load())
    assert not unexpected, f"new orphan carrying a class palette (delete it or add it to EXEMPT_ORPHANS): {unexpected}"


def test_the_exempt_orphans_are_still_unreachable():
    """The exemption above is conditional on the file reaching no screen. If a
    template starts loading it, it becomes a live second palette -- which is
    precisely how glass-theme.css's six `!important` gradients ended up on
    /combat while being documented as the admin-and-account dialect."""
    loaded = _stylesheets_templates_load()
    linked = sorted(EXEMPT_ORPHANS & loaded)
    assert not linked, f"exempt orphan is now loaded by a template, so its palette is live again: {linked}"


def test_no_class_badge_rule_uses_important():
    """`!important` is how the glass-theme block beat the tokens regardless of
    load order and specificity, so no amount of correct cascade could fix it."""
    offenders = [
        f"{path.name}: {selector}"
        for path, selector, block in _rules()
        if ("class-badge" in selector or _CLASS_BADGE.search(selector)) and "!important" in block
    ]
    assert not offenders, "!important in a class-badge rule:\n  " + "\n  ".join(offenders)
