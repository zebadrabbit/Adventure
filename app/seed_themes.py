"""Programmatic, idempotent seeding of the Cold Steel and Classic Dungeon themes.

Like app/seed_skills.py, this seeds via the ORM so the Theme-driven design system
(Phase 1 of the UI redesign) has real data from a fresh database. Idempotent:
themes are upserted by name. Activating "Cold Steel" deactivates every other theme
first, matching the same exclusivity rule the admin "activate" endpoint enforces
(app/routes/theme_api.py).

Usage:
    from app.seed_themes import seed_themes
    seed_themes()

CLI:
    python run.py seed-themes
"""

from __future__ import annotations

from app import app as flask_app
from app import db
from app.models.theme import Theme

THEMES = [
    {
        "name": "Cold Steel",
        "description": "Slate/charcoal hub with a teal accent — the default look.",
        "primary": "#5ad1c9",
        "secondary": "#2e3440",
        "success": "#4caf82",
        "danger": "#c0392b",
        "warning": "#d6a23a",
        "info": "#5ad1c9",
        "light": "#dfe4ea",
        "dark": "#0c0e12",
        "body_bg": "#0c0e12",
        "body_color": "#dfe4ea",
        "link_color": "#5ad1c9",
        "link_hover_color": "#7adbd4",
        "border_color": "#2e3440",
        "card_bg": "#1b1f27",
        "card_opacity": 1.0,
        "gradient_angle": 135,
        "gradient_start": "#0c0e12",
        "gradient_end": "#1b1f27",
        "is_active": True,
    },
    {
        "name": "Classic Dungeon",
        "description": "The original warm-brown medieval palette, preserved as an alt theme.",
        "primary": "#d4a574",
        "secondary": "#c17a3a",
        "success": "#4a6741",
        "danger": "#8b2e2e",
        "warning": "#c17a3a",
        "info": "#8b6f47",
        "light": "#d4c5b0",
        "dark": "#0d0a0a",
        "body_bg": "#0d0a0a",
        "body_color": "#d4c5b0",
        "link_color": "#d4a574",
        "link_hover_color": "#e8c9a0",
        "border_color": "#3d3226",
        "card_bg": "#1a1512",
        "card_opacity": 1.0,
        "gradient_angle": 135,
        "gradient_start": "#0d0a0a",
        "gradient_end": "#1a1512",
        "is_active": False,
    },
]


def seed_themes(verbose: bool = True) -> int:
    """Create or update the Cold Steel and Classic Dungeon themes. Returns count.

    Idempotent: themes are upserted by name. If a theme in THEMES is marked
    is_active=True, every other theme row (seeded or not) is deactivated first,
    so there is never more than one active theme after this runs.
    """
    with flask_app.app_context():
        count = 0
        for spec in THEMES:
            theme = Theme.query.filter_by(name=spec["name"]).first()
            if not theme:
                theme = Theme(name=spec["name"])
                db.session.add(theme)
            for key, value in spec.items():
                if key != "is_active":
                    setattr(theme, key, value)
            count += 1

        db.session.flush()

        # Enforce that at most one theme is marked as active.
        active_specs = [spec for spec in THEMES if spec.get("is_active")]
        assert len(active_specs) <= 1, "THEMES must define at most one is_active=True spec"
        if active_specs:
            Theme.query.update({"is_active": False})
            theme = Theme.query.filter_by(name=active_specs[0]["name"]).first()
            theme.is_active = True

        db.session.commit()
        if verbose:
            print(f"[seed-themes] {count} themes seeded.")
        return count


__all__ = ["seed_themes"]
