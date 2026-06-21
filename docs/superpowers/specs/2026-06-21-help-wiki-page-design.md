# Help / wiki page — design

## Problem

The footer's "Support" link is a dead `#` placeholder in both
`app/templates/index.html:129` and `app/templates/partials/footer.html:28`
— confirmed via grep, no support route, page, or contact email exists
anywhere in the codebase (originally logged in
`docs/superpowers/TODO.md`). There are no live GMs/support staff for this
game, so "Support" in practice means self-serve help: explaining what's
going on, not a contact channel.

## Goal

Give new and returning players a single in-app page that explains the
core mechanics that are easy to get wrong without a human to ask —
particularly the hoard/extraction permadeath model and the
recently-added skill-tree combat actions — with real screenshots of the
actual UI, not just prose.

## Scope (v1)

Four sections, in this order:

1. **Getting Started** — creating an account/character, the dashboard
   layout (Recruit/Roster, the Hub Actions tabs added in the dashboard
   hub layout pass), how to deploy into a dungeon.
2. **Dungeon Exploration & Combat** — movement, ambient encounters,
   the combat action panel: Attack/Defend, the universal caster spells
   (Firebolt/Ice Shard/Lightning), Potion, Flee, and the per-character
   unlocked skill buttons added in the prior session.
3. **Hoard & Extraction** — the risk model: a character's carried gold
   (`Character.gold`) and gear are at risk on a run; dying loses the
   run's purse; extracting "secures" loot to the persistent per-user
   Hoard; loot-the-body lets a survivor recover a downed party member's
   items mid-run. This is the single most important concept for a new
   player to understand before they lose something they cared about.
4. **Skills & Progression** — XP and leveling, talent points, unlocking
   skills via the skill tree, and using unlocked active skills in combat.

Explicitly out of scope for v1 (future sections, not blocking this page):
trading, repair/durability, equipment/encumbrance details, themes. The
page structure (anchor nav) accommodates adding more `<section>` blocks
later without redesign.

## Route & template

- New route `GET /help` (endpoint `main.help`) in
  `app/routes/main.py`, placed alongside the existing
  `--- Legal and Info Pages ---` block (`licenses`/`privacy`/`terms`/
  `conduct`), following the identical pattern: a bare
  `return render_template("help.html")`, no view-model logic needed since
  content is static.
- New template `app/templates/help.html`, extending `base.html` exactly
  like `conduct.html` does. Structure: an intro paragraph, a sticky
  in-page anchor nav (`<nav>` with 4 links to `#getting-started`,
  `#combat`, `#hoard-extraction`, `#skills-progression`), then one
  `<section id="...">` per topic with prose + embedded screenshots.

## Screenshots

- New static directory `app/static/img/help/`.
- Captured live during implementation using the `run`/`verify` skill
  against a real running dev server — not mocked or hand-drawn. Expected
  shots: dashboard overview, the dungeon exploration view, the combat
  action panel mid-fight (showing both universal spells and an unlocked
  skill button if one is available on the dev DB), the extraction/hoard
  confirmation panel, and the skill-tree unlock screen.
- Each `<img>` gets descriptive `alt` text (accessibility + fallback if a
  capture is skipped). If a particular screen can't be reasonably
  captured (e.g. requires a specific game state that's awkward to set up
  in the dev DB), the section ships with prose only and a one-line note
  in the implementation report — not a placeholder broken-image tag.

## Wiring

- `app/templates/index.html:129`: `<a href="#" class="footer-link">Support</a>`
  → `<a href="{{ url_for('main.help') }}" class="footer-link">Support</a>`
- `app/templates/partials/footer.html:28`: `<li><a href="#">Support</a></li>`
  → `<li><a href="{{ url_for('main.help') }}">Support</a></li>`
- No other footer links are touched (Getting Started/Classes/Items/Rules/
  News/Events/Leaderboard remain dead placeholders — a separate, broader
  footer-completeness gap already noted as out of scope in
  `docs/superpowers/TODO.md`).

## Testing

- A render test following the existing pattern for other static info
  pages (grep `tests/test_main_pages.py` for the existing
  `test_info_pages`-style assertions): GET `/help` returns 200 and the
  response body contains each section's heading text, confirming the
  template renders without a Jinja error and all four sections are
  present.
- No test asserts screenshot files exist on disk (out of scope — image
  presence is a content-authoring concern, not a behavioral one); the
  `<img>` tags' `src` paths are covered implicitly by the render test
  rendering without error if Jinja references a `url_for('static', ...)`
  path, which doesn't require the file to exist to render successfully.
- Footer link changes are covered by extending whatever existing test (if
  any) asserts footer content on the index page; if none exists, this is
  not a new requirement to invent — out of scope.

## Out of scope

- Search functionality, versioning, or a CMS — this is static Jinja
  content like the existing legal pages.
- Multi-page navigation (index + sub-pages) — deferred per the chosen
  single-page-with-anchors structure; revisit only if content outgrows
  one page.
- Any other dead footer link besides Support.
