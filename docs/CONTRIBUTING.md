## Contributing

Moved from project root to `docs/`.

### Getting Started
1. Fork and clone the repository.
2. Create a virtual environment and install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run the test suite:
   ```bash
   pytest -q
   ```

### Development Guidelines
- Write clear, small commits with descriptive messages.
- Maintain or increase test coverage (CI enforces >= 80%).
- Prefer adding tests before or alongside behavior changes.
- Avoid large, mixed commits (split refactors vs. features).

### Coding Standards
- Follow existing code style; keep imports grouped (stdlib, third-party, local).
- Use docstrings for non-trivial functions or modules.
- Keep functions focused; consider splitting if > ~40 lines of complex logic.

### Testing
- Put new tests under `tests/` mirroring app module structure when reasonable.
- Cover edge cases (invalid input, boundary sizes, auth failures) in addition to happy path.

### Database & Migrations
- SQLite is used for dev; schema changes should include lightweight migration helper or defensive add-column logic.

### Branching
- Use feature branches: `feature/<short-description>`.
- For fixes: `fix/<issue-id-or-keyword>`.

### Pull Requests
- Reference related issues.
- Include a brief summary of changes and any follow-up TODOs.
- Ensure lint/tests pass locally before opening.

### Pre-Commit / Quality
- Run any provided formatting or lint scripts (if present) prior to commit.

### Security / Secrets
- Do not commit secrets or real credentials.

### Need Help?
Open a discussion or issue—happy to clarify.
