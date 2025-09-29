# Data Import CSV Formats

This directory contains canonical CSV templates for bulk importing game content (items and monster catalog entries) into the Adventure database. The templates aim to be:

- Idempotent: Importing the same CSV multiple times (with UPSERT logic) should not create duplicates.
- Human‑authorable: Friendly to spreadsheet tools (Excel, LibreOffice, Google Sheets) without exotic quoting.
- Forward‑compatible: Extra columns should be safely ignorable; missing optional columns fall back to defaults.

> NOTE: Current project code does not yet include an automated CSV ingest route. Use the Python snippets below or craft your own management command. Future admin tooling will add validation and web upload.

---
## 1. Item Import (`item_import_template.csv`)

### Columns
| Name | Required | Type | Description | Notes |
|------|----------|------|-------------|-------|
| slug | Yes | text | Unique stable identifier. Lowercase, underscores, prefix by type (e.g. `weapon_sword_l1`). | Primary key surrogate. Avoid spaces. |
| name | Yes | text | Player‑facing display name. | Capitalization & spacing allowed. |
| type | Yes | text | Broad item category (e.g. `weapon`, `armor`, `potion`, `scroll`, `material`, `tool`, `quest`). | Should match or extend existing category logic. |
| description | Yes | text | Short descriptive string. | Keep under ~120 chars for UI. |
| value_copper | Yes | integer | Base economic value in copper units. | 100 copper = 1 silver style future conversion. |
| extra_json | No | JSON object | Freeform metadata (e.g., rarity overrides, quest flags). | Empty cell allowed. Must be valid JSON if present. |

### Sample Rows
```
slug,name,type,description,value_copper,extra_json
weapon_sword_l1,Rusty Shortsword,weapon,A worn but serviceable blade.,35,
quest_goblin_totem,Goblin Totem,quest,Totemic carving taken from goblin shaman.,0,{"quest_flag":"goblin_totem"}
```

### Validation Recommendations
1. Uniqueness: All `slug` values must be unique (case‑sensitive compare).
2. Naming Consistency: Prefer hierarchical slugs: `<domain>_<subtype>[_l<level>]`.
3. Economic Curve: Verify new items do not create sharp discontinuities in `value_copper` progression relative to peers.
4. JSON Integrity: Attempt `json.loads(extra_json)` for non‑empty cells—reject on failure.
5. Reserved Characters: Avoid commas in `slug`; commas in `name` or `description` are fine (they will be quoted automatically by proper CSV writers).

### Suggested UPSERT (SQLite)
```python
import csv, json, sqlite3
conn = sqlite3.connect('instance/mud.db')
cur = conn.cursor()
with open('data_templates/item_import_template.csv', newline='') as f:
    reader = csv.DictReader(f)
    for row in reader:
        # Basic required field presence
        if not row['slug'] or not row['name']:
            raise ValueError(f"Missing required fields in row: {row}")
        value = int(row['value_copper'] or 0)
        cur.execute('''INSERT INTO item (slug,name,type,description,value_copper)
                       VALUES (?,?,?,?,?)
                       ON CONFLICT(slug) DO UPDATE SET
                         name=excluded.name,
                         type=excluded.type,
                         description=excluded.description,
                         value_copper=excluded.value_copper''',
                    (row['slug'], row['name'], row['type'], row['description'], value))
        # Optional metadata hook (pseudo – adjust if item table gains JSON column)
        # if row['extra_json']:
        #     meta = json.loads(row['extra_json'])
        #     ... apply metadata logic ...
conn.commit()
```

---
## 2. Monster Catalog Import (`monster_catalog_template.csv`)

### Columns
| Name | Required | Type | Description | Notes |
|------|----------|------|-------------|-------|
| slug | Yes | text | Unique monster identifier. Suggest family + role + tier (e.g. `goblin_scout_t1`). | Unique index enforced. |
| name | Yes | text | Display name. | Capitalization allowed. |
| level_min | Yes | integer | Minimum spawn level. | >=1 |
| level_max | Yes | integer | Maximum spawn level. | >= level_min |
| base_hp | Yes | integer | Baseline HP before scaling. | Tier curve guidelines below. |
| base_damage | Yes | integer | Baseline damage before scaling. | Roughly level * (1 + tier_mod). |
| armor | Yes | integer | Flat armor / mitigation proxy. | 0+ |
| speed | Yes | integer | Initiative influence. | Typical 8–15 range. |
| rarity | Yes | text | `common|uncommon|rare|elite|boss` | Drives spawn weighting & UI tint. |
| family | Yes | text | Biological / thematic group (e.g. `undead`, `beast`, `construct`). | Used by loot tables. |
| traits | Yes | text | CSV string of keyword traits (`flying,fire_breath`). | Future: move to join table. |
| loot_table | Yes | text | Key used by loot logic (e.g. `undead_basic`). | Stub ok until implemented. |
| special_drop_slug | No | text | Guaranteed/high-chance unique item. | NULL when absent. |
| xp_base | Yes | integer | Base XP pre scaling. | Roughly proportional to threat. |
| boss | Yes | integer (0/1) | Boss flag (1 = boss). | `rarity` should also be `boss` for clarity. |

### Sample Rows
```
slug,name,level_min,level_max,base_hp,base_damage,armor,speed,rarity,family,traits,loot_table,special_drop_slug,xp_base,boss
example_goblin_scout,Goblin Scout,1,2,18,4,0,12,common,humanoid,"nimble,low_light_vision",goblin_basic,,15,0
example_boss_dragon,Ancient Flame Wyrm,20,20,1800,120,14,12,boss,dragon,"flying,breath_fire,frightful_presence",boss_dragon,weapon_bow_l20,4000,1
```

### Tiering Guidance (Approximate)
| Tier | Level Band | Base HP Range | Base Damage Range |
|------|------------|---------------|-------------------|
| T1 | 1–3 | 15–30 | 3–7 |
| T2 | 4–6 | 50–90 | 10–16 |
| T3 | 7–9 | 110–190 | 18–28 |
| T4 | 10–12 | 240–420 | 32–50 |
| T5 | 13–15 | 480–700 | 48–70 |
| T6 | 16–18 | 900–1300 | 74–105 |
| T7 | 19–20 | 1500–2000 | 110–140 |

### Validation Checklist
1. `level_min <= level_max`.
2. Rarity `boss` must have `boss=1` and vice versa.
3. HP & damage fall roughly inside the tier bands (outliers flagged for manual review).
4. Traits list only contains recognized keywords (maintain a reference list in code).
5. `loot_table` maps to an implemented or planned table to avoid silent fallback.
6. Avoid duplicate thematic roles (e.g., two different `*_scout_t1` goblins) unless intentional.

### Suggested UPSERT (SQLite)
```python
import csv, sqlite3
conn = sqlite3.connect('instance/mud.db')
cur = conn.cursor()
with open('data_templates/monster_catalog_template.csv', newline='') as f:
    reader = csv.DictReader(f)
    for r in reader:
        cur.execute('''INSERT INTO monster_catalog
            (slug,name,level_min,level_max,base_hp,base_damage,armor,speed,rarity,family,traits,loot_table,special_drop_slug,xp_base,boss)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(slug) DO UPDATE SET
              name=excluded.name,
              level_min=excluded.level_min,
              level_max=excluded.level_max,
              base_hp=excluded.base_hp,
              base_damage=excluded.base_damage,
              armor=excluded.armor,
              speed=excluded.speed,
              rarity=excluded.rarity,
              family=excluded.family,
              traits=excluded.traits,
              loot_table=excluded.loot_table,
              special_drop_slug=excluded.special_drop_slug,
              xp_base=excluded.xp_base,
              boss=excluded.boss''', (
            r['slug'], r['name'], int(r['level_min']), int(r['level_max']), int(r['base_hp']), int(r['base_damage']),
            int(r['armor']), int(r['speed']), r['rarity'], r['family'], r['traits'], r['loot_table'],
            r['special_drop_slug'] or None, int(r['xp_base']), int(r['boss'])
        ))
conn.commit()
```

---
## 3. Spreadsheet Authoring Tips
- Freeze header row while editing.
- Use data validation drop‑downs for `rarity`, `family`, `boss` to reduce typos.
- Create conditional formatting bands for HP/damage columns to highlight outliers.
- Keep a separate sheet with canonical trait keywords.

## 4. Common Pitfalls
| Issue | Symptom | Fix |
|-------|---------|-----|
| Trailing spaces in slug | INSERT conflicts unexpectedly | Trim cells or use CLEAN/TRIM in spreadsheet. |
| Non‑UTF8 export | Import script crashes on decode | Ensure UTF‑8 or UTF‑8 BOM export option. |
| Unescaped quotes in description | Malformed CSV line | Spreadsheet export handles quoting automatically—avoid manual editing in raw text editors. |
| JSON parsing failure | extra_json ignored / exception | Validate with an online JSON linter before import. |

## 5. Future Enhancements
Planned tooling (roadmap):
- Admin web UI for CSV upload + dry‑run diff.
- Automatic curve validation & anomaly report.
- Reference data endpoint (`/api/admin/reference/traits`) to centralize dynamic validation.
- Content pack versioning (bundle multiple CSVs with manifest).

---
## 6. Quick Verification Script
Run after import to spot obvious structural issues:
```python
import sqlite3
conn = sqlite3.connect('instance/mud.db')
cur = conn.cursor()
print('Item count:', cur.execute('select count(*) from item').fetchone()[0])
print('Monster count:', cur.execute('select count(*) from monster_catalog').fetchone()[0])
# Find overlapping monster slugs (should be 0)
print('Duplicate monsters (expect 0):', cur.execute('''select slug,count(*) c from monster_catalog group by slug having c>1''').fetchall())
# Spot out-of-band HP rows
print('High HP anomalies:', cur.execute('select slug,base_hp from monster_catalog where base_hp>2200').fetchall())
```

---
## 7. Contributing New Categories
If you introduce a new item type or monster family:
1. Add representative rows to the CSV templates (comment with `#` NOT allowed inside CSV body, so document in README instead).
2. Update loot logic (for item types) or spawn weighting (for monster families) in code.
3. Open a PR with both SQL and CSV updates plus adjusted documentation.

---
**Questions?** Open a GitHub issue with `[content]` in the title describing the addition or discrepancy you found.
