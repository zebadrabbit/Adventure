# Style Guide

Moved from project root to `docs/`.

## Python
- Use snake_case for functions and variables, PascalCase for classes.
- Keep line length reasonable (PEP8 guidance) but prioritize clarity over strict wrapping.
- Prefer explicit imports; avoid wildcard `*`.
- Return early to reduce nesting.

## Flask / Routes
- Group related endpoints into blueprint modules.
- Keep request handlers thin—delegate logic to helper functions or model methods where possible.

## SQLAlchemy
- Use explicit relationships and backrefs only when they simplify usage.
- Guard optional attributes in templates (`getattr(obj, 'field', None)`).

## Websockets
- Namespace separation for logically distinct domains (e.g., lobby vs game events).
- Validate user/admin permissions server-side before emitting privileged broadcasts.

## JavaScript
- Modularize features: separate files for dashboard logic, widgets, and utilities.
- Avoid inline scripts; all JS belongs in `static/` with cache busting.
- Use data attributes for lightweight state where possible.

## CSS
- Utility classes for spacing, layout, and effects consolidate styling.
- Avoid inline `style` attributes; rely on classes and theming variables.

## Testing
- Mirror module structure in `tests/`.
- Cover both success and failure branches.
- Use fixtures for shared setup (authenticated client, seeded dungeon, etc.).

## Commits
- Present tense imperative ("Add X", "Fix Y").

## Documentation
- Update README sections when feature surfaces change.
- Cross-link new docs in `docs/` as needed.
