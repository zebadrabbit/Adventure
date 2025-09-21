# Adventure MUD Frontend & Template Style Guide

This guide defines conventions for HTML templates, CSS utilities, and JavaScript modules.

## 1. Templates (Jinja2)
- No inline `style="..."` attributes. Use utilities in `static/utilities.css`.
- No inline `<script>` blocks with code. All logic belongs in `static/js/*.js` and is referenced with `<script src="{{ asset_url('path.js') }}"></script>`.
- Use `asset_url()` for all local static assets (CSS/JS/images that need cache busting).
- Keep template logic (conditionals/loops) presentation-focused; move data shaping into view functions.
- Prefer semantic HTML and Bootstrap utility classes over custom ad-hoc classes when equivalent.

## 2. CSS & Utilities
- Repeated style (appearing ≥2 times) becomes a utility class in `utilities.css`.
- Name utilities with a neutral, structural purpose (e.g., `.mw-240`, `.u-flex-center`, `.icon-28`).
- Avoid color names unless the color is part of a semantic domain (e.g., coin metals: `.coin-gold`).
- Add component-scoped classes only when structure/styling cannot be expressed via Bootstrap + utilities.

## 3. JavaScript
- Each functional area gets its own module (e.g., `adventure.js`, `admin-settings.js`, `dashboard.js`).
- Avoid embedding template variables directly in large scripts; if needed, expose via `data-*` attributes or lightweight JSON script tags (not currently used—prefer API fetches).
- Prefer event delegation for dynamically inserted elements (e.g., chat tabs, party members).
- Fetch APIs return JSON; handle errors gracefully with console warnings and user-safe messages.

## 4. Asset Versioning
- Never append manual `?v=...` tokens. The `asset_url()` helper appends a `?v=<mtime>` automatically.
- If a file does not require cache busting (e.g., external CDN), leave it as-is.

## 5. Icons & Imagery
- Use `svg_icon` macro for SVG images located under `static/iconography/`.
- Do not reintroduce a style parameter—extend utilities if new filters/visual effects are needed.
- Keep icons accessible: ensure `alt` text is meaningful.

## 6. Lint & Enforcement
Automated checks (pre-commit):
- Trailing whitespace & EOF normalization
- Inline style attribute prohibition
- Inline script block prohibition
- Manual version token prohibition

Run manually:
```bash
pre-commit run --all-files
```

## 7. Adding New Utilities
1. Verify no Bootstrap + existing utility combination can achieve the result.
2. Add the rule to `static/utilities.css` with a short comment if non-obvious.
3. Replace all occurrences of the previous inline or duplicated pattern.
4. Avoid over-specific utilities (e.g., `.margin-left-7px`). Round to a design token or use Bootstrap spacing utilities.

## 8. Performance Considerations
- Keep DOM queries scoped (e.g., `container.querySelector`) when possible.
- Avoid large synchronous loops inside animation frames; batch updates if needed.
- Use passive event listeners for scroll/touch if introduced in the future.

## 9. Accessibility
- Maintain proper heading order inside cards/sections.
- Buttons vs links: navigation uses `<a>`, actions use `<button type="button">` or or appropriate `<form>` submit.
- Provide `aria-` labels for non-textual interactive elements where context is not obvious.

## 10. Future Enhancements (Planned)
- Automated CSS purge / bundling step if asset size grows.
- Light/dark theme tokens extracted into CSS variables.
- Lint rule for unused utilities.

---
Questions / proposals: open a GitHub issue or add a PR referencing this guide.
