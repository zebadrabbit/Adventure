# Documentation Index

Welcome to the Adventure project documentation. This index links all major docs now consolidated under `docs/`.

## Core Guides
- [Project Overview (Root README)](../README.md)
- [Changelog](CHANGELOG.md)
- [Release Notes](RELEASE_NOTES.md)
- [Contributing Guide](CONTRIBUTING.md)
- [Style Guide](STYLE_GUIDE.md)
- [Architecture Diagram](architecture.md)

## Development
- Version bump script: `scripts/bump_version.py` (auto-inserts UNRELEASED section into `docs/CHANGELOG.md`).
- Pre-commit hooks configured in `.pre-commit-config.yaml` (enforce no inline styles/scripts, static asset cache busting, SVG normalization).

## Dungeon Generation
The pipeline is multi-phase and deterministic for a given (seed, size). See sections in the root `README.md` for detailed phase descriptions. Consider adding deeper docs here in future (e.g., heuristics, performance notes, planned feature phases).

## WebSockets
- Namespaces: `lobby` and `game`. Admin broadcasts are permission-gated.
- Future documentation opportunity: message schema & event contract table.

## Testing & Coverage
- Pytest suite enforces ≥80% coverage; current coverage ~86% after targeted edge-case tests (seed errors, fallback user id, websocket noop, dungeon edge relocation).
- Add new tests mirroring module structure under `tests/`.

## Roadmap Ideas (High-Level)
- External cache or LRU for dungeon instances beyond in-process dict.
- Expanded feature assignment phase (loot tables, encounter seeds, environmental hazards).
- Accessibility refinements (more granular ARIA labeling, high-contrast theme variant).
- Real-time party synchronization & cooperative movement vote / lock-step mode.
- Event schema documentation & typed client (TypeScript) stub.

## Conventions Recap
- No inline template styles/scripts.
- All static assets referenced via `asset_url()` for cache busting.
- Deterministic seeds (string hashing -> int) unify client/server.
- Root documentation files are now stubs; canonical content lives here.

## Contributing Quick Link
See [Contributing](CONTRIBUTING.md) for workflow, branching, and release process.

---
_Last updated: 2025-09-21_
