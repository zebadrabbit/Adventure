from app.models.theme import Theme


def test_to_css_variables_includes_ui_namespace():
    theme = Theme(
        name="Cold Steel Test",
        primary="#5ad1c9",
        secondary="#2e3440",
        success="#4caf82",
        danger="#c0392b",
        warning="#d6a23a",
        info="#5ad1c9",
        light="#dfe4ea",
        dark="#0c0e12",
        body_bg="#0c0e12",
        body_color="#dfe4ea",
        link_color="#5ad1c9",
        link_hover_color="#7adbd4",
        border_color="#2e3440",
        card_bg="#1b1f27",
        card_opacity=1.0,
        gradient_angle=135,
        gradient_start="#0c0e12",
        gradient_end="#1b1f27",
    )

    css = theme.to_css_variables()

    assert "--ui-bg: #0c0e12;" in css
    assert "--ui-panel: #1b1f27;" in css
    assert "--ui-elevated: #2e3440;" in css
    assert "--ui-accent: #5ad1c9;" in css
    assert "--ui-danger: #c0392b;" in css
    assert "--ui-success: #4caf82;" in css
    assert "--ui-warning: #d6a23a;" in css
    assert "--ui-text: #dfe4ea;" in css
    assert "--ui-font: 'Segoe UI', system-ui, -apple-system, sans-serif;" in css
