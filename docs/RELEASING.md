# Releasing Adventure

This guide details the lightweight release process. All releases should be traceable, tested, and reflected in the changelog.

## 1. Prerequisites
- All tests green: `pytest -q`
- `docs/CHANGELOG.md` updated under the UNRELEASED section with meaningful entries (Added / Changed / Fixed / Removed) referencing issues where possible.
- No TODO/FIXME items introduced for the tagged commit (unless explicitly documented in changelog).

## 2. Versioning Strategy
Semantic Versioning (MAJOR.MINOR.PATCH)
- PATCH: Bug fixes & internal-only refactors.
- MINOR: Backwards-compatible features / migrations.
- MAJOR: Backwards-incompatible API or gameplay changes.

## 3. Bump the Version
Use the helper script:
```
python scripts/bump_version.py <part>
```
Where `<part>` is one of: `patch`, `minor`, `major`.

The script will:
1. Parse current version from `VERSION`.
2. Update `VERSION` file and search `docs/CHANGELOG.md` first for matching version section.
3. Fail if the target version already exists.

## 4. Finalize Changelog
- Replace the `UNRELEASED` header with the concrete version & date (YYYY-MM-DD).
- Immediately add a new `UNRELEASED` stub at the top if desired for ongoing work.

Example snippet:
```
## [0.3.9] - 2025-09-21
### Added
- WebSocket payload validation helpers.
```

## 5. Commit & Tag
```
git add VERSION docs/CHANGELOG.md
git commit -m "release: vX.Y.Z"
git tag -a vX.Y.Z -m "Adventure vX.Y.Z"
```

## 6. Push
```
git push origin main --tags
```

## 7. Post-Release
- Announce changes (README badges, release notes page, etc. – future automation).
- Monitor error logs for regressions.

## 8. Fast Checklist
- [ ] Tests pass
- [ ] Changelog updated
- [ ] Version bumped
- [ ] Tag created & pushed

---
_This document will evolve as the project matures (CI/CD, packaging, Docker images, PyPI, etc.)._
