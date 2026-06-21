# Adventure

[![CI](https://github.com/zebadrabbit/Adventure/actions/workflows/ci.yml/badge.svg)](https://github.com/zebadrabbit/Adventure/actions/workflows/ci.yml)

A web-based multiplayer dungeon crawler. Build a party of up to four characters, descend into a procedurally generated dungeon, fight your way through turn-based combat, and decide how far to push your luck before extracting with the loot you've found — or losing it all to a party wipe.

> **Quick links:** [Changelog](CHANGELOG.md) · [Development Workflow](docs/DEVELOPMENT.md) · [Architecture](docs/architecture.md) · [Economy & Progression](docs/ECONOMY_PROGRESSION.md) · [Dungeon Generation](docs/DUNGEON_GENERATION.md) · [Combat & Monster AI](docs/MONSTER_AI.md) · [Contributing](docs/CONTRIBUTING.md)

## What is Adventure?

Adventure is a browser-based MUD-style dungeon crawler built with Flask and Socket.IO. Everything happens in real time over WebSockets — movement, combat, chat, loot — with no page reloads. Dungeons are procedurally generated and deterministic per seed, so the same seed always produces the same layout, but every party's choices inside it play out differently.

## Gameplay

**Characters & classes.** Create up to four characters per account and field a party of up to four at once. Six core classes (fighter, rogue, mage, cleric, ranger, druid) each start with class-appropriate gear, auto-equipped on creation so you're dungeon-ready immediately.

**Combat.** Turn-based, initiative-driven encounters where every character in your party acts independently (not as a single "party turn"). Attack, defend, flee, cast spells, or use items — each action is server-authoritative with optimistic-concurrency versioning so the UI never desyncs from the real combat state. Monsters run their own AI: ambush, spellcasting, fleeing at low HP, calling for help, and persistent status effects like poison.

**Dungeon exploration.** Each dungeon is procedurally generated from a seed — rooms, corridors, doors, secret passages, and teleport pads, all deterministic and reproducible. Movement, searching, and other actions advance a shared game clock that paces random encounters and monster patrols, so the world only moves when you do.

**Loot & economy.** Items drop with level-aware, rarity-weighted placement (common through mythic) so rewards stay relevant to your party's progress. Gear wears down with use and can be repaired. Your run-purse is at risk the moment you enter a dungeon — only what you successfully extract makes it into your permanent Hoard; a party wipe loses the run's haul.

**Progression.** Characters earn XP from kills and successful extractions, leveling up into talent and stat points you allocate yourself. A skill system layers in passive bonuses and active combat abilities on top of your base class.

**Party play.** Bring multiple characters into the same dungeon run, share a single combat initiative order, and coordinate who acts when — see [Economy & Progression](docs/ECONOMY_PROGRESSION.md) for how loot, currency, and XP are split across a party.

## Prerequisites

- **Python 3.10+**
- **PostgreSQL 13+** (required — SQLite is not supported)
- A PostgreSQL database and credentials

## Quick Start

```bash
# 1. Set up PostgreSQL database
createdb adventure

# 2. Configure environment
export DATABASE_URL="postgresql://username:password@localhost/adventure"
export SECRET_KEY="your-secret-key-here"

# 3. Install dependencies
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 4. Run migrations
alembic upgrade head

# 5. Seed catalog + economy data (items, vendors, skills) — idempotent
python run.py reseed-items
python run.py seed-merchants
python run.py seed-skills
# (or all three at once: ./manage.sh db seed)

# 6. Start the server
python run.py server  # visit http://localhost:5000
```

Or use the interactive bootstrap script, which handles `.env` generation, migrations, and an admin account for you:

```bash
python scripts/setup_adventure.py
```

Run tests / lint / format:
```bash
pytest -q
ruff check .
black --check .
```

Full local-dev setup, coding conventions, and the admin CLI are covered in [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md).

## Project Structure

- `app/models/` — Database models
- `app/routes/` — Flask blueprints (auth, dashboard, dungeon API, combat, admin, ...)
- `app/services/` — Game logic (combat, progression, loot, status effects, time/ticks)
- `app/dungeon/` — Procedural dungeon generation pipeline
- `app/websockets/` — Socket.IO event handlers
- `app/static/`, `app/templates/` — Frontend assets and Jinja templates
- `migrations/` — Alembic schema migrations
- `tests/` — pytest suite

## Documentation

| Topic | Doc |
|---|---|
| Release history | [CHANGELOG.md](CHANGELOG.md) |
| Local dev setup, lint/test conventions, admin CLI | [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) |
| System architecture overview | [docs/architecture.md](docs/architecture.md) |
| Economy, currency, hoard, progression | [docs/ECONOMY_PROGRESSION.md](docs/ECONOMY_PROGRESSION.md) |
| Combat system (actions, formulas, balance) | [docs/COMBAT_SYSTEM.md](docs/COMBAT_SYSTEM.md) |
| Combat visual effects (particles/animations) | [docs/COMBAT_EFFECTS.md](docs/COMBAT_EFFECTS.md) |
| Loot system (rarity, placement algorithm) | [docs/LOOT_SYSTEM.md](docs/LOOT_SYSTEM.md) |
| Dungeon generation pipeline & invariants | [docs/DUNGEON_GENERATION.md](docs/DUNGEON_GENERATION.md) |
| Teleports | [docs/TELEPORTS.md](docs/TELEPORTS.md) |
| Monster AI | [docs/MONSTER_AI.md](docs/MONSTER_AI.md) |
| Locked doors & lockpicking | [docs/LOCKED_DOORS.md](docs/LOCKED_DOORS.md) |
| Party system | [docs/PARTY_SYSTEM.md](docs/PARTY_SYSTEM.md) |
| Skill tree system | [docs/SKILL_TREE_SYSTEM.md](docs/SKILL_TREE_SYSTEM.md) |
| Achievements | [docs/ACHIEVEMENT_SYSTEM.md](docs/ACHIEVEMENT_SYSTEM.md) |
| Trading system | [docs/TRADING_SYSTEM.md](docs/TRADING_SYSTEM.md) |
| Frontend style guide | [docs/STYLE_GUIDE.md](docs/STYLE_GUIDE.md) |
| Testing conventions | [docs/TESTING.md](docs/TESTING.md) |
| Deployment | [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) · [docs/DOCKER_SETUP.md](docs/DOCKER_SETUP.md) |
| Release process | [docs/RELEASING.md](docs/RELEASING.md) |

## Contributing

See [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md) for coding conventions, pre-commit policy, asset guidelines, and test instructions.
