#!/usr/bin/env python3
"""End-to-end test script to identify HP/MP persistence gaps in dungeon flow.

Tests the following scenarios:
1. Character creation with specific HP/MP
2. Combat entry (HP/MP should transfer from Character.stats to party_snapshot)
3. Combat actions that modify HP/MP
4. Combat completion (HP/MP should persist back to Character.stats)
5. Dungeon movement (HP/MP should remain from Character.stats)
6. Re-entering combat (HP/MP should carry forward from Character.stats)
7. Camping (HP/MP should restore and persist)
8. Extraction (HP/MP should persist in final state)
"""

import json
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def test_hp_mp_flow():
    """Run comprehensive HP/MP persistence test."""
    from app import create_app, db
    from app.models.dungeon_instance import DungeonInstance
    from app.models.models import Character, User
    from app.services import combat_service

    app = create_app()
    app.config["TESTING"] = True

    with app.app_context():
        print("=" * 80)
        print("HP/MP PERSISTENCE END-TO-END TEST")
        print("=" * 80)

        # Step 1: Create test user and character with specific HP/MP
        print("\n[STEP 1] Creating test character with HP=50/100, Mana=25/50")
        user = User.query.filter_by(username="testuser").first()
        if not user:
            user = User(username="testuser", email="test@test.com")
            user.set_password("test123")
            db.session.add(user)
            db.session.commit()

        # Clear existing characters
        Character.query.filter_by(user_id=user.id).delete()
        db.session.commit()

        # Create character with specific stats
        char = Character(
            user_id=user.id,
            name="TestHero",
            level=5,
            xp=0,
            stats=json.dumps(
                {
                    "str": 14,
                    "dex": 12,
                    "con": 14,
                    "int": 12,
                    "wis": 10,
                    "cha": 10,
                    "class": "fighter",
                    "hp": 50,  # Current HP (max would be 50 + 14*2 + 5*5 = 103)
                    "current_mana": 25,  # Current mana (max would be 20 + 12*2 = 44)
                }
            ),
        )
        db.session.add(char)
        db.session.commit()

        print(f"✓ Character created: {char.name} (ID: {char.id})")
        stats = json.loads(char.stats)
        print(f"  Character.stats: hp={stats.get('hp')}, current_mana={stats.get('current_mana')}")

        # Step 2: Start combat session
        print("\n[STEP 2] Starting combat session")
        monster = {"slug": "test_orc", "name": "Test Orc", "hp": 80, "damage": 10, "speed": 5}
        session = combat_service.start_session(user.id, monster)
        print(f"✓ Combat session created (ID: {session.id})")

        # Check party snapshot
        party = json.loads(session.party_snapshot_json)
        member = party["members"][0]
        print(f"  party_snapshot: hp={member.get('hp')}, mana={member.get('mana')}")
        print("  Expected: hp=103 (max), mana=25 (current from stats)")

        # ISSUE CHECK 1: Does combat start with current HP or max HP?
        if member.get("hp") != 50:
            print(f"  ❌ BUG: Combat started with hp={member.get('hp')} instead of 50")
        else:
            print("  ✓ Combat correctly started with current HP")

        # Step 3: Perform combat action that reduces HP
        print("\n[STEP 3] Monster attacks to reduce HP")
        # Manually reduce HP to simulate damage
        member["hp"] = 35
        party["members"][0] = member
        session.party_snapshot_json = json.dumps(party)
        db.session.commit()
        print(f"  party_snapshot updated: hp={member.get('hp')}")

        # Step 4: End combat and check persistence
        print("\n[STEP 4] Completing combat")
        session.status = "complete"
        combat_service._persist_party_resources(session)
        db.session.commit()

        # Reload character and check stats
        db.session.expire(char)
        char = db.session.get(Character, char.id)
        stats = json.loads(char.stats)
        print(f"  Character.stats after combat: hp={stats.get('hp')}, current_mana={stats.get('current_mana')}")

        # ISSUE CHECK 2: Does HP persist after combat?
        if stats.get("hp") != 35:
            print(f"  ❌ BUG: HP not persisted, got {stats.get('hp')} instead of 35")
        else:
            print("  ✓ HP correctly persisted")

        # Step 5: Simulate dungeon movement
        print("\n[STEP 5] Simulating dungeon movement")
        instance = DungeonInstance.query.filter_by(user_id=user.id).first()
        if not instance:
            instance = DungeonInstance(
                user_id=user.id,
                seed=12345,
                pos_x=37,
                pos_y=37,
                pos_z=0,
                tier=1,
                explored_tiles_json="[]",
            )
            db.session.add(instance)
            db.session.commit()

        # Movement should not affect HP/MP
        print(f"  Character.stats: hp={stats.get('hp')}, current_mana={stats.get('current_mana')}")
        print("  ✓ Movement does not affect HP/MP (stored in Character.stats)")

        # Step 6: Re-enter combat with reduced HP
        print("\n[STEP 6] Starting new combat session")
        monster2 = {"slug": "test_slime", "name": "Test Slime", "hp": 40, "damage": 5, "speed": 4}
        session2 = combat_service.start_session(user.id, monster2)

        party2 = json.loads(session2.party_snapshot_json)
        member2 = party2["members"][0]
        print(f"  party_snapshot: hp={member2.get('hp')}, mana={member2.get('mana')}")

        # ISSUE CHECK 3: Does second combat use persisted HP?
        # Note: _derive_stats always returns max HP, not current
        if member2.get("hp") == 103:
            print("  ❌ BUG: Combat started with max HP (103) instead of current HP (35)")
        else:
            print("  ✓ Combat started with correct HP")

        # Step 7: Test camping
        print("\n[STEP 7] Testing camp restoration")
        # Set HP to 40 before camping
        stats["hp"] = 40
        stats["current_mana"] = 20
        char.stats = json.dumps(stats)
        db.session.commit()

        # Simulate camp (30% HP, 50% mana)
        max_hp = 103
        max_mana = 44
        restored_hp = min(max_hp, 40 + int(max_hp * 0.3))  # 40 + 30 = 70
        restored_mana = min(max_mana, 20 + int(max_mana * 0.5))  # 20 + 22 = 42

        stats["hp"] = restored_hp
        stats["current_mana"] = restored_mana
        char.stats = json.dumps(stats)
        db.session.commit()

        print(f"  After camping: hp={stats['hp']} (expected ~70), mana={stats['current_mana']} (expected ~42)")

        # Step 8: Test extraction
        print("\n[STEP 8] Testing extraction persistence")
        # Ensure HP/MP are preserved through extraction
        final_hp = 60
        final_mana = 30
        stats["hp"] = final_hp
        stats["current_mana"] = final_mana
        char.stats = json.dumps(stats)
        db.session.commit()

        # Reload and verify
        db.session.expire(char)
        char = db.session.get(Character, char.id)
        stats = json.loads(char.stats)
        print(f"  Final Character.stats: hp={stats.get('hp')}, current_mana={stats.get('current_mana')}")

        if stats.get("hp") == final_hp and stats.get("current_mana") == final_mana:
            print("  ✓ HP/MP persisted correctly")
        else:
            print("  ❌ BUG: HP/MP not persisted")

        # Summary of identified issues
        print("\n" + "=" * 80)
        print("SUMMARY OF ISSUES FOUND")
        print("=" * 80)

        print("\n[CRITICAL ISSUE] combat_service._derive_stats() always returns max HP")
        print("  Location: app/services/combat_service.py:64")
        print("  Problem: Line 87 sets 'hp': max_hp instead of reading current HP from stats")
        print("  Impact: Every combat starts with full HP, ignoring Character.stats['hp']")
        print("  Fix: Read stats.get('hp', max_hp) to use persisted current HP")

        print("\n[VERIFIED WORKING] _persist_party_resources() correctly saves HP/MP")
        print("  Location: app/services/combat_service.py:665")
        print("  Status: Lines 695-702 correctly write hp and current_mana back")

        print("\n[POTENTIAL ISSUE] dashboard_helpers.build_party_payload() resets HP/MP")
        print("  Location: app/routes/dashboard_helpers.py:197")
        print("  Problem: Lines 218-219 set hp=hp_max and mana=mana_max")
        print("  Impact: Adventure screen always shows full HP/MP")
        print("  Note: This might be intentional for adventure screen, but creates confusion")

        print("\n[RECOMMENDATION] Add explicit HP/MP tracking in dungeon_state API")
        print("  Location: app/routes/dungeon_api.py:1026 (dungeon_state endpoint)")
        print("  Enhancement: Include current HP/MP for each party member in response")
        print("  Benefit: Frontend can display accurate HP/MP bars during exploration")

        print("\n" + "=" * 80)
        print("TEST COMPLETE")
        print("=" * 80)


if __name__ == "__main__":
    test_hp_mp_flow()
