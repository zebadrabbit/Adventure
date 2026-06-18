"""Theme model for dynamic UI theming."""

from datetime import datetime

from app import db


class Theme(db.Model):
    """User-created themes with Bootstrap CSS variable mappings."""

    __tablename__ = "theme"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False, unique=True)
    description = db.Column(db.Text, nullable=True)

    # Bootstrap CSS Variables (stored as hex colors)
    primary = db.Column(db.String(7), nullable=False, default="#6366f1")
    secondary = db.Column(db.String(7), nullable=False, default="#8b5cf6")
    success = db.Column(db.String(7), nullable=False, default="#22c55e")
    danger = db.Column(db.String(7), nullable=False, default="#ef4444")
    warning = db.Column(db.String(7), nullable=False, default="#f59e0b")
    info = db.Column(db.String(7), nullable=False, default="#3b82f6")
    light = db.Column(db.String(7), nullable=False, default="#f8f9fa")
    dark = db.Column(db.String(7), nullable=False, default="#212529")

    # Background and text colors
    body_bg = db.Column(db.String(7), nullable=False, default="#0f172a")
    body_color = db.Column(db.String(7), nullable=False, default="#f1f5f9")

    # Link colors
    link_color = db.Column(db.String(7), nullable=False, default="#6366f1")
    link_hover_color = db.Column(db.String(7), nullable=False, default="#8b5cf6")

    # Border and component colors
    border_color = db.Column(db.String(7), nullable=False, default="#334155")
    card_bg = db.Column(db.String(7), nullable=False, default="#1e293b")
    card_opacity = db.Column(db.Float, nullable=False, default=0.1)  # 0.0 to 1.0

    # Gradient background settings
    gradient_angle = db.Column(db.Integer, nullable=False, default=135)
    gradient_start = db.Column(db.String(7), nullable=False, default="#4c5270")
    gradient_end = db.Column(db.String(7), nullable=False, default="#5a3a52")

    # Background image settings
    background_image = db.Column(db.String(255), nullable=True)
    bg_position = db.Column(db.String(50), nullable=False, default="center")
    bg_size = db.Column(db.String(50), nullable=False, default="cover")
    bg_repeat = db.Column(db.String(50), nullable=False, default="no-repeat")
    bg_attachment = db.Column(db.String(50), nullable=False, default="scroll")

    # Active theme flag
    is_active = db.Column(db.Boolean, nullable=False, default=False)

    # Metadata
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)

    def to_dict(self):
        """Convert theme to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "primary": self.primary,
            "secondary": self.secondary,
            "success": self.success,
            "danger": self.danger,
            "warning": self.warning,
            "info": self.info,
            "light": self.light,
            "dark": self.dark,
            "body_bg": self.body_bg,
            "body_color": self.body_color,
            "link_color": self.link_color,
            "link_hover_color": self.link_hover_color,
            "border_color": self.border_color,
            "card_bg": self.card_bg,
            "card_opacity": self.card_opacity,
            "gradient": {
                "angle": self.gradient_angle,
                "start": self.gradient_start,
                "end": self.gradient_end,
            },
            "background_image": self.background_image,
            "bg_position": self.bg_position,
            "bg_size": self.bg_size,
            "bg_repeat": self.bg_repeat,
            "bg_attachment": self.bg_attachment,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def _hex_to_rgb(self, hex_color):
        """Convert hex color to RGB tuple."""
        hex_color = hex_color.lstrip("#")
        return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))

    def to_css_variables(self):
        """Generate CSS custom properties string."""
        # Convert card_bg hex to RGB for opacity support
        r, g, b = self._hex_to_rgb(self.card_bg)

        css = f"""
:root {{
    --bs-primary: {self.primary};
    --bs-secondary: {self.secondary};
    --bs-success: {self.success};
    --bs-danger: {self.danger};
    --bs-warning: {self.warning};
    --bs-info: {self.info};
    --bs-light: {self.light};
    --bs-dark: {self.dark};
    --bs-body-bg: {self.body_bg};
    --bs-body-color: {self.body_color};
    --bs-link-color: {self.link_color};
    --bs-link-hover-color: {self.link_hover_color};
    --bs-border-color: {self.border_color};
    --bs-card-bg: {self.card_bg};

    --adv-primary: {self.primary};
    --adv-primary-hover: {self.secondary};
    --adv-secondary: {self.secondary};
    --adv-success: {self.success};
    --adv-danger: {self.danger};
    --adv-warning: {self.warning};
    --adv-link-color: {self.link_color};
    --adv-link-hover-color: {self.link_hover_color};

    --ui-bg: {self.body_bg};
    --ui-panel: {self.card_bg};
    --ui-elevated: {self.border_color};
    --ui-accent: {self.primary};
    --ui-accent-hover: {self.secondary};
    --ui-danger: {self.danger};
    --ui-success: {self.success};
    --ui-warning: {self.warning};
    --ui-text: {self.body_color};
    --ui-text-dim: {self.light};
    --ui-font: 'Segoe UI', system-ui, -apple-system, sans-serif;
}}

body {{
"""
        # Add background image if present
        if self.background_image:
            css += f"""    background: linear-gradient({self.gradient_angle}deg, {self.gradient_start}, {self.gradient_end}), url({self.background_image}) !important;
    background-position: {self.bg_position} !important;
    background-size: {self.bg_size} !important;
    background-repeat: {self.bg_repeat} !important;
    background-attachment: {self.bg_attachment} !important;
"""
        else:
            css += f"""    background: linear-gradient({self.gradient_angle}deg, {self.gradient_start}, {self.gradient_end}) !important;
    background-attachment: fixed !important;
"""
        css += "}\n\n"
        css += f"""a {{
    color: {self.link_color} !important;
}}

a:hover {{
    color: {self.link_hover_color} !important;
}}

.card, .glass-panel, .section-card {{
    background: rgba({r}, {g}, {b}, {self.card_opacity}) !important;
    backdrop-filter: blur(16px) !important;
    -webkit-backdrop-filter: blur(16px) !important;
    border: 1px solid rgba(255, 255, 255, 0.2) !important;
    box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37) !important;
}}

.card:hover, .glass-panel:hover {{
    border-color: rgba(255, 255, 255, 0.3) !important;
}}
"""
        return css
