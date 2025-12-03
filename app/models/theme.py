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
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def to_css_variables(self):
        """Generate CSS custom properties string."""
        return f"""
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
}}
"""
