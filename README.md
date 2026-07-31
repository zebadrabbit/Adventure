<div align="center">

```
    ▄▄▄       ▓█████▄  ██▒   █▓▓█████  ███▄    █ ▄▄▄█████▓ █    ██  ██▀███  ▓█████
   ▒████▄     ▒██▀ ██▌▓██░   █▒▓█   ▀  ██ ▀█   █ ▓  ██▒ ▓▒ ██  ▓██▒▓██ ▒ ██▒▓█   ▀
   ▒██  ▀█▄   ░██   █▌ ▓██  █▒░▒███   ▓██  ▀█ ██▒▒ ▓██░ ▒░▓██  ▒██░▓██ ░▄█ ▒▒███
   ░██▄▄▄▄██  ░▓█▄   ▌  ▒██ █░░▒▓█  ▄ ▓██▒  ▐▌██▒░ ▓██▓ ░ ▓▓█  ░██░▒██▀▀█▄  ▒▓█  ▄
    ▓█   ▓██▒ ░▒████▓    ▒▀█░  ░▒████▒▒██░   ▓██░  ▒██▒ ░ ▒▒█████▓ ░██▓ ▒██▒░▒████▒
    ▒▒   ▓▒█░  ▒▒▓  ▒    ░ ▐░  ░░ ▒░ ░░ ▒░   ▒ ▒   ▒ ░░   ░▒▓▒ ▒ ▒ ░ ▒▓ ░▒▓░░░ ▒░ ░
```

### ⚔️  *Four heroes. One seed. Everything you carry is at risk.*

[![CI](https://github.com/zebadrabbit/Adventure/actions/workflows/ci.yml/badge.svg)](https://github.com/zebadrabbit/Adventure/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.10%2B-3776AB?logo=python&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/postgres-13%2B-4169E1?logo=postgresql&logoColor=white)
![Socket.IO](https://img.shields.io/badge/realtime-Socket.IO-010101?logo=socketdotio&logoColor=white)
![Version](https://img.shields.io/badge/version-0.8.13-d8af4f)

[Changelog](CHANGELOG.md) ·
[Development](docs/DEVELOPMENT.md) ·
[Architecture](docs/architecture.md) ·
[Economy](docs/ECONOMY_PROGRESSION.md) ·
[Dungeons](docs/DUNGEON_GENERATION.md) ·
[Contributing](docs/CONTRIBUTING.md)

</div>

---

> *You take four into the dark. What you bring back is yours. What you drop down there stays down there.*

**Adventure** is a browser-based, MUD-style dungeon crawler built on Flask and Socket.IO. Everything happens in real time over WebSockets — movement, combat, chat, loot — with no page reloads. Dungeons are procedurally generated and **deterministic per seed**: the same seed always produces the same layout, but no two parties spend it the same way.

The hook is extraction. Your run-purse is at risk from the moment you step through the door. Only what you carry out becomes permanent, banked into your **Hoard**. A party wipe loses the run's haul — and a character who dies and is not raised can be looted, then left behind for good.

---

## 🎲 The Loop

```mermaid
flowchart LR
    A["🏰 Town<br/>roster · train · trade"] --> B["🗝️ Delve<br/>pick a seed"]
    B --> C["🕯️ Explore<br/>rooms · doors · traps"]
    C --> D["⚔️ Fight<br/>turn-based, per character"]
    D --> C
    C --> E{"Push on<br/>or leave?"}
    E -->|push| C
    E -->|extract| F["💰 Hoard<br/>haul banked, XP kept"]
    E -->|wipe| G["💀 Lost<br/>haul gone"]
    F --> A
    G --> A
```

The whole design lives in that fork. Going deeper is where the good loot is; every step deeper is more you stand to lose.

---

## ⚔️ What You Actually Do

<table>
<tr><td width="50%" valign="top">

#### 🧙 Party & Progression
Roll up to **twelve classes** — fighter, barbarian, monk, mage, sorcerer, cleric, paladin, druid, ranger, rogue, bard, warlock — and field **four at a time**. Each class has its own signature skill tree on top of a shared archetype line, so no two classes play the same.

Twenty levels, and every one of them unlocks something. Talent points buy skills you choose; you will never have enough for all of them.

</td><td width="50%" valign="top">

#### 🗡️ Combat
Turn-based and initiative-driven, where **every character acts on their own turn** — not as one lumpy "party turn". Attack, defend, flee, drink, or spend a skill.

Server-authoritative with optimistic-concurrency versioning, so the screen can never disagree with the real fight.

</td></tr>
<tr><td width="50%" valign="top">

#### 🏰 The Dungeon
Rooms, corridors, locked doors, secret passages and teleport pads — all generated from a seed and fully reproducible.

Movement and searching advance a shared **game clock** that paces encounters and patrols. The world only moves when you do.

</td><td width="50%" valign="top">

#### 💎 Loot
Procedural gear with prefixes and suffixes — *Brutal Longsword of the Bear* — where rarity changes what an item is **worth**, not just how many words it has.

Deeper tiers roll better. Gear wears down and can be repaired.

</td></tr>
</table>

> [!NOTE]
> **Two systems ship switched off** while their numbers get playtested: multi-enemy packs (`combat_pack_max`) and monster AI (`ai_enabled`). The engine handles both; turning either on makes fights markedly harder, so they are deliberately opt-in. Monsters currently attack and nothing else.

---

## 🧭 Getting Started

> [!IMPORTANT]
> **PostgreSQL is required.** SQLite is explicitly rejected at startup — the app raises unless `DATABASE_URL` points at Postgres.

<details open>
<summary><b>📜 Quick start</b></summary>

```bash
# 1. Database
createdb adventure

# 2. Environment
export DATABASE_URL="postgresql://username:password@localhost/adventure"
export SECRET_KEY="your-secret-key-here"

# 3. Dependencies
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 4. Schema
alembic upgrade head

# 5. Seed the world — idempotent, safe to re-run
python run.py reseed-items
python run.py seed-merchants
python run.py seed-skills
# (or all three: ./manage.sh db seed)

# 6. Open the doors
python run.py server        # http://localhost:5000
```

</details>

<details>
<summary><b>🪄 Or let the bootstrap script do it</b></summary>

Handles `.env` generation, migrations and an admin account for you:

```bash
python scripts/setup_adventure.py
```

</details>

<details>
<summary><b>🧪 Tests, lint, format</b></summary>

```bash
pytest -q
ruff check .
black --check .
```

The suite needs an explicit test database — see [docs/TESTING.md](docs/TESTING.md).
Conventions and the admin CLI are in [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md).

</details>

---

## 🗺️ Where Things Live

| | |
|---|---|
| `app/models/` | Database models |
| `app/routes/` | Flask blueprints — auth, dashboard, dungeon, combat, admin |
| `app/services/` | Game logic — combat, progression, loot, status effects, the clock |
| `app/dungeon/` | Procedural generation pipeline |
| `app/websockets/` | Socket.IO event handlers |
| `app/static/`, `app/templates/` | Frontend assets and Jinja templates |
| `migrations/` | Alembic schema migrations |
| `tests/`, `e2e/` | pytest suite and Playwright browser smoke |

---

## 📚 The Library

<details>
<summary><b>Open the full documentation index</b></summary>

<br>

| Topic | Doc |
|---|---|
| Release history | [CHANGELOG.md](CHANGELOG.md) |
| Local dev, lint/test conventions, admin CLI | [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) |
| System architecture | [docs/architecture.md](docs/architecture.md) |
| Economy, currency, hoard, progression | [docs/ECONOMY_PROGRESSION.md](docs/ECONOMY_PROGRESSION.md) |
| Combat system — actions, formulas, balance | [docs/COMBAT_SYSTEM.md](docs/COMBAT_SYSTEM.md) |
| Combat visual effects | [docs/COMBAT_EFFECTS.md](docs/COMBAT_EFFECTS.md) |
| Loot — rarity, placement algorithm | [docs/LOOT_SYSTEM.md](docs/LOOT_SYSTEM.md) |
| Dungeon generation & invariants | [docs/DUNGEON_GENERATION.md](docs/DUNGEON_GENERATION.md) |
| Teleports | [docs/TELEPORTS.md](docs/TELEPORTS.md) |
| Monster AI | [docs/MONSTER_AI.md](docs/MONSTER_AI.md) |
| Locked doors & lockpicking | [docs/LOCKED_DOORS.md](docs/LOCKED_DOORS.md) |
| Party system | [docs/PARTY_SYSTEM.md](docs/PARTY_SYSTEM.md) |
| Skill trees | [docs/SKILL_TREE_SYSTEM.md](docs/SKILL_TREE_SYSTEM.md) |
| Achievements | [docs/ACHIEVEMENT_SYSTEM.md](docs/ACHIEVEMENT_SYSTEM.md) |
| Trading | [docs/TRADING_SYSTEM.md](docs/TRADING_SYSTEM.md) |
| Frontend style guide | [docs/STYLE_GUIDE.md](docs/STYLE_GUIDE.md) |
| Art assets & licences | [docs/ASSETS.md](docs/ASSETS.md) |
| Testing conventions | [docs/TESTING.md](docs/TESTING.md) |
| Deployment | [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) · [docs/DOCKER_SETUP.md](docs/DOCKER_SETUP.md) |
| Release process | [docs/RELEASING.md](docs/RELEASING.md) |

</details>

---

## 🎨 Credits

Dungeon tile art: **Dungeon Gathering — Under The Castle Set** by **[SnowHex](https://snowhex.itch.io/dungeon-gathering)** — lovely 16×16 work, and worth your money.

> [!WARNING]
> The art is licence-restricted and is **not** included in this repository. Run `scripts/import_tiles.sh` against a copy you own to enable it — or just play without it, and the map renders procedurally. See [docs/ASSETS.md](docs/ASSETS.md).

---

## 🤝 Contributing

Coding conventions, pre-commit policy, asset guidelines and test instructions are in **[docs/CONTRIBUTING.md](docs/CONTRIBUTING.md)**.

<div align="center">
<br>
<sub><i>Built with Flask, Socket.IO, PostgreSQL — and an unreasonable number of tests.</i></sub>
</div>
