import re
from pathlib import Path

import pytest

from app import app
from app.models.theme import Theme
from app.seed_themes import THEMES, seed_themes

TOKENS_CSS = Path(__file__).resolve().parents[1] / "app" / "static" / "css" / "tokens.css"

# Theme column -> the --ui-* custom property it feeds in
# Theme.to_css_variables(). See docs/DESIGN_SYSTEM.md, "Layer 0".
COLUMN_TO_TOKEN = {
    "body_bg": "--ui-bg",
    "card_bg": "--ui-panel",
    "border_color": "--ui-elevated",
    "primary": "--ui-accent",
    "secondary": "--ui-accent-hover",
    "danger": "--ui-danger",
    "success": "--ui-success",
    "warning": "--ui-warning",
    "body_color": "--ui-text",
    "light": "--ui-text-dim",
}


@pytest.mark.db_isolation
def test_seed_themes_creates_lamplight_cold_steel_and_classic_dungeon():
    with app.app_context():
        count = seed_themes(verbose=False)
        assert count == 3

        lamplight = Theme.query.filter_by(name="Lamplight").first()
        assert lamplight is not None
        assert lamplight.is_active is True
        assert lamplight.primary == "#d9a441"
        assert lamplight.body_bg == "#0f0c09"

        cold_steel = Theme.query.filter_by(name="Cold Steel").first()
        assert cold_steel is not None
        assert cold_steel.is_active is False
        assert cold_steel.primary == "#5ad1c9"

        classic = Theme.query.filter_by(name="Classic Dungeon").first()
        assert classic is not None
        assert classic.is_active is False
        assert classic.primary == "#d4a574"


@pytest.mark.db_isolation
def test_seed_themes_is_idempotent():
    with app.app_context():
        seed_themes(verbose=False)
        first_count = Theme.query.count()
        seed_themes(verbose=False)
        second_count = Theme.query.count()
        assert first_count == second_count


def test_exactly_one_seeded_theme_is_active():
    """The active theme owns the whole palette; two would be ambiguous."""
    assert sum(1 for spec in THEMES if spec.get("is_active")) == 1


def test_active_theme_matches_tokens_css_fallbacks():
    """The active seed and tokens.css Layer 0 must not drift apart.

    tokens.css ships the palette as static fallbacks; the active Theme row
    ships it as the value that actually wins at runtime (it loads last). If
    they disagree, the app renders one palette and the design system documents
    another -- which is the exact failure this design system exists to stop.
    """
    css = TOKENS_CSS.read_text(encoding="utf-8")
    active = next(spec for spec in THEMES if spec.get("is_active"))

    for column, token in COLUMN_TO_TOKEN.items():
        match = re.search(rf"^\s*{re.escape(token)}:\s*(#[0-9a-fA-F]{{6}})\s*;", css, re.MULTILINE)
        assert match, f"{token} not found in tokens.css"
        assert match.group(1).lower() == active[column].lower(), (
            f"{token} is {match.group(1)} in tokens.css but " f"Theme.{column} is {active[column]} in seed_themes.py"
        )
