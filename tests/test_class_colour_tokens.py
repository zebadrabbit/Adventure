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
# Neither was findable by grepping tokens.css. The three tests below are.

CSS_DIR = TOKENS.parent

# Every property through which a colour can reach a badge. `background-image`
# and `-webkit-text-fill-color` are here because they are the same class of
# bypass as `background` and `color`: the deleted glass-theme block did its
# damage through a `linear-gradient()`, i.e. background-image.
_SIDES = ("top", "right", "bottom", "left")
COLOUR_PROPS = (
    {"background", "background-color", "background-image", "color", "-webkit-text-fill-color"}
    | {"border", "border-color"}
    | {f"border-{s}" for s in _SIDES}
    | {f"border-{s}-color" for s in _SIDES}
)
# `border`/`border-<side>` shorthands may legitimately carry width and style
# with no colour at all -- theme.css's `.class-badge { border: 1px solid }` is
# correct, because it leaves the colour to `.<class>-badge`'s border-color.
_BORDER_SHORTHANDS = {"border"} | {f"border-{s}" for s in _SIDES}
_BORDER_KEYWORDS = {
    "none",
    "hidden",
    "dotted",
    "dashed",
    "solid",
    "double",
    "groove",
    "ridge",
    "inset",
    "outset",
    "thin",
    "medium",
    "thick",
}
_LENGTH = re.compile(r"^[\d.]+(px|em|rem|%|pt|vw|vh)?$")

_COMMENT = re.compile(r"/\*.*?\*/", re.S)
_RULE = re.compile(r"([^{}]*)\{([^{}]*)\}", re.S)
_CLASS_BADGE = re.compile(rf"\.({'|'.join(CLASSES)})-badge\b")
# Bare `.class-badge` too. This is NOT optional: it is the shape the real defect
# took. glass-theme.css set `.class-badge { border: 1px solid rgba(255,255,255,.3) }`,
# and because the `border` shorthand writes border-*-color it beat every
# `.<class>-badge { border-color: var(--class-*-border) }` on /combat -- greying
# the ring for all twelve classes. A guard that only matched `.<class>-badge`
# would have watched that happen.
_BARE_CLASS_BADGE = re.compile(r"\.class-badge\b")

# `.badge:where(:not(.class-badge))` mentions .class-badge in order to EXCLUDE
# it -- the three specificity guards in theme.css/combat.css/dashboard.css all
# look like this, and matching them would flag the very rules that protect class
# badges. Strip the arguments of :not()/:where()/:is()/:has() before matching, so
# only a genuine subject like `.class-badge:hover` counts. Applied repeatedly so
# nesting collapses from the inside out.
_FUNCTIONAL = re.compile(r":(?:not|where|is|has)\(([^()]*)\)")


def _selector_subject(selector):
    previous = None
    while previous != selector:
        previous = selector
        selector = _FUNCTIONAL.sub("", selector)
    return selector


def _specifies_a_colour(prop, value):
    """Does this declaration actually put a colour on the element?

    Only the border shorthands are ambiguous; for every other property in
    COLOUR_PROPS the presence of a value is itself a colour.
    """
    if prop not in _BORDER_SHORTHANDS:
        return bool(value.strip())
    remainder = [tok for tok in value.split() if tok.lower() not in _BORDER_KEYWORDS and not _LENGTH.match(tok)]
    return bool(remainder)


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
_IMPORT = re.compile(r"""@import\s+url\(\s*["']?([A-Za-z0-9_.-]+\.css)""")


def _reachable_stylesheets():
    """Every stylesheet that can reach a browser, transitively.

    A `<link>` in a template is not the only way in: app.css already pulls in
    hoard-ui.css and dungeon-config.css with `@import`, and app.css loads on
    every page. So `@import url("tactical-theme.css")` in any reachable file
    would make the exempt palette live without a template changing at all.
    Following imports is what makes the exemption below honest.
    """
    direct = set()
    for path in TEMPLATES.rglob("*.html"):
        direct.update(re.findall(r"css/([A-Za-z0-9_.-]+\.css)", path.read_text()))

    imports = {p.name: set(_IMPORT.findall(p.read_text())) for p in CSS_DIR.glob("*.css")}

    seen, queue = set(), list(direct)
    while queue:
        name = queue.pop()
        if name in seen:
            continue
        seen.add(name)
        queue.extend(imports.get(name, ()))
    return seen


def test_no_stylesheet_sets_a_class_badge_colour_outside_the_tokens():
    """Every class badge colour must be a var(--class-*), in any file.

    A `.rogue-badge { background: <a literal> }` -- or a `.class-badge` rule
    that sets a colour through any property at all -- is a second palette by
    definition, whatever file it hides in. Files in EXEMPT_ORPHANS are excused
    only while unreachable; the test below enforces that.
    """
    offenders = []
    for path, selector, block in _rules():
        if path.name in EXEMPT_ORPHANS:
            continue
        subject = _selector_subject(selector)
        if not (_CLASS_BADGE.search(subject) or _BARE_CLASS_BADGE.search(subject)):
            continue
        for prop, value in _declarations(block):
            if prop in COLOUR_PROPS and _specifies_a_colour(prop, value) and "var(--class-" not in value:
                offenders.append(f"{path.name}: {selector} {{ {prop}: {value} }}")

    assert not offenders, "class badge colour not read from a token:\n  " + "\n  ".join(offenders)


def test_the_exempt_orphans_are_still_unreachable():
    """The exemption is conditional on the file reaching no screen. The moment
    something links or @imports it, its palette is live again -- which is
    precisely how glass-theme.css's six `!important` gradients ended up on
    /combat while being documented as the admin-and-account dialect."""
    linked = sorted(EXEMPT_ORPHANS & _reachable_stylesheets())
    assert not linked, (
        "exempt orphan is reachable again (a template <link> or an @import), so "
        f"its class palette is live: {linked}. Delete the file or the reference."
    )


def test_no_class_badge_rule_uses_important():
    """`!important` is how the glass-theme block beat the tokens regardless of
    load order and specificity, so no amount of correct cascade could fix it."""
    offenders = []
    for path, selector, block in _rules():
        if path.name in EXEMPT_ORPHANS or "!important" not in block:
            continue
        subject = _selector_subject(selector)
        if _CLASS_BADGE.search(subject) or _BARE_CLASS_BADGE.search(subject):
            offenders.append(f"{path.name}: {selector}")
    assert not offenders, "!important in a class-badge rule:\n  " + "\n  ".join(offenders)
