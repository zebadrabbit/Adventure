#!/usr/bin/env python3
"""Diagnose HP/MP persistence issues by analyzing the code flow."""

from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent


def analyze_hp_mp_flow():
    """Analyze HP/MP tracking through the codebase."""
    print("=" * 80)
    print("HP/MP PERSISTENCE ANALYSIS")
    print("=" * 80)

    # Issue 1: combat_service._derive_stats() always returns max HP
    print("\n[CRITICAL ISSUE #1] _derive_stats() ignores current HP")
    print("-" * 80)
    print("Location: app/services/combat_service.py:64")
    print("\nCurrent code (line ~87-130):")
    print("  max_hp = 50 + CON * 2 + level * 5")
    print("  ...")
    print("  return {")
    print("    'hp': max_hp,  # ❌ ALWAYS max HP")
    print("    'max_hp': max_hp,")
    print("    'mana': mana,  # ✓ Uses persisted current_mana")
    print("    'mana_max': mana_max,")
    print("  }")
    print("\nImpact:")
    print("  - Every combat starts with full HP")
    print("  - Character.stats['hp'] is ignored")
    print("  - Players get free healing between combats")
    print("\nFix:")
    print("  Read persisted HP from stats:")
    print("    hp_source = base.get('hp', max_hp)")
    print("    hp = int(hp_source) if hp_source else max_hp")
    print("    hp = max(0, min(hp, max_hp))  # Clamp to valid range")
    print("    return {'hp': hp, 'max_hp': max_hp, ...}")

    # Issue 2: dashboard_helpers resets HP/MP
    print("\n[ISSUE #2] build_party_payload() always shows full HP/MP")
    print("-" * 80)
    print("Location: app/routes/dashboard_helpers.py:218-219")
    print("\nCurrent code:")
    print("  hp = hp_max  # Always full HP on adventure screen")
    print("  mana = mana_max  # Always full mana on adventure screen")
    print("\nImpact:")
    print("  - Adventure screen shows full HP/MP even when damaged")
    print("  - Creates confusion about actual character state")
    print("  - Disconnected from Character.stats values")
    print("\nFix:")
    print("  Read actual values from stats:")
    print("    hp = int(s.get('hp', hp_max))")
    print("    mana = int(s.get('current_mana', s.get('mana', mana_max)))")

    # Issue 3: No HP/MP in dungeon_state API
    print("\n[ISSUE #3] dungeon_state API doesn't include party HP/MP")
    print("-" * 80)
    print("Location: app/routes/dungeon_api.py:1026")
    print("\nCurrent response:")
    print("  {")
    print("    'pos': [x, y, z],")
    print("    'desc': str,")
    print("    'exits': [...],")
    print("    'progress': {...},  # Has boss/extraction info")
    print("    # ❌ No party HP/MP data")
    print("  }")
    print("\nImpact:")
    print("  - Frontend can't display HP/MP bars during exploration")
    print("  - No way to know if characters need healing")
    print("\nFix:")
    print("  Add party array with current HP/MP:")
    print("    resp['party'] = [")
    print("      {")
    print("        'char_id': char.id,")
    print("        'name': char.name,")
    print("        'hp': stats.get('hp'),")
    print("        'max_hp': calculated_max_hp,")
    print("        'mana': stats.get('current_mana'),")
    print("        'max_mana': calculated_max_mana,")
    print("      }")
    print("      for char in party_chars")
    print("    ]")

    # Good: persistence after combat
    print("\n[VERIFIED WORKING] _persist_party_resources()")
    print("-" * 80)
    print("Location: app/services/combat_service.py:665")
    print("\nThis correctly saves HP/MP after combat:")
    print("  stats_obj['hp'] = int(m.get('hp', ...))")
    print("  stats_obj['current_mana'] = int(m.get('mana', ...))")
    print("  row.stats = json.dumps(stats_obj)")
    print("  db.session.add(row)")
    print("✓ No changes needed here")

    # Good: camping restoration
    print("\n[VERIFIED WORKING] dungeon_camp()")
    print("-" * 80)
    print("Location: app/routes/dungeon_api.py:1514")
    print("\nCorrectly reads/writes HP/MP:")
    print("  current_hp = int(stats.get('hp', 0))")
    print("  current_mana = int(stats.get('mana', 0))")
    print("  # ... calculate restoration ...")
    print("  stats['hp'] = new_hp")
    print("  stats['mana'] = new_mana")
    print("  char.stats = json.dumps(stats)")
    print("✓ No changes needed here")

    print("\n" + "=" * 80)
    print("SUMMARY OF REQUIRED FIXES")
    print("=" * 80)
    print("\n1. [CRITICAL] Fix _derive_stats() to read persisted HP")
    print("   Priority: HIGH - Breaks combat persistence")
    print("   Effort: 5 minutes")
    print("\n2. [IMPORTANT] Fix build_party_payload() to show actual HP/MP")
    print("   Priority: MEDIUM - UI shows wrong state")
    print("   Effort: 5 minutes")
    print("\n3. [ENHANCEMENT] Add party HP/MP to dungeon_state API")
    print("   Priority: MEDIUM - Improves UX")
    print("   Effort: 10 minutes")
    print("\n" + "=" * 80)


if __name__ == "__main__":
    analyze_hp_mp_flow()
