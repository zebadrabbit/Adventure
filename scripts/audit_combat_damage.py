"""Measure mean damage per combat action, through the real service functions.

Not a reimplementation of the formulas: this drives combat_service the way the
API does, samples many rounds, and reports the average damage a single action
actually removes from a monster's HP. Run it before and after any balance
change.

    PYTHONPATH=. DATABASE_URL=... python scripts/audit_combat_damage.py
"""

from __future__ import annotations

import json
import random
import statistics
import sys

from app import create_app, db
from app.models.models import Character, User
from app.services import combat_service

SAMPLES = 60
LEVELS = (1, 5, 10, 20)
DUMMY_HP = 10_000_000


def _dummy_monster():
    # armor 0 keeps the accuracy roll out of the damage question; misses are
    # measured separately because they are part of an action's real value.
    return {
        "slug": "audit-dummy",
        "name": "Audit Dummy",
        "level": 1,
        "hp": DUMMY_HP,
        "damage": 0,
        "armor": 0,
        "speed": 1,
        "xp": 0,
    }


def _character(user, level: int, cls: str) -> Character:
    stats = {"str": 14, "dex": 10, "int": 14, "wis": 10, "con": 12, "cha": 10, "class": cls}
    char = Character(
        user_id=user.id,
        name=f"{cls.title()}L{level}",
        stats=json.dumps(stats),
        gear=json.dumps({}),
        items="[]",
        level=level,
        xp=0,
    )
    db.session.add(char)
    db.session.commit()
    return char


def _sample(fn, session_factory, samples=SAMPLES):
    """Average HP removed per action, and the miss rate."""
    amounts, misses = [], 0
    for _ in range(samples):
        session = session_factory()
        before = session.monster_hp
        result = fn(session)
        if result is None:
            continue
        session = combat_service._load_session(session.id)
        dealt = before - (session.monster_hp or 0)
        if dealt <= 0:
            misses += 1
        amounts.append(max(0, dealt))
    return (statistics.mean(amounts) if amounts else 0.0), (misses / len(amounts) if amounts else 0.0)


def main():
    app = create_app()
    with app.app_context():
        from werkzeug.security import generate_password_hash

        user = User.query.filter_by(username="_damage_audit").first()
        if not user:
            user = User(username="_damage_audit", password=generate_password_hash("x"))
            db.session.add(user)
            db.session.commit()
        from app.models.skill import CharacterSkill as _CS

        stale = [c.id for c in Character.query.filter_by(user_id=user.id).all()]
        if stale:
            _CS.query.filter(_CS.character_id.in_(stale)).delete(synchronize_session=False)
            db.session.commit()
        Character.query.filter_by(user_id=user.id).delete()
        db.session.commit()

        print(f"{'level':<6}{'attack':>10}{'firebolt':>11}{'lightning':>11}{'skill b5':>11}{'skill b22':>11}")
        print("-" * 60)

        for level in LEVELS:
            char = _character(user, level, "fighter")

            def fresh():
                random.seed()
                session = combat_service.start_session(user.id, _dummy_monster())
                # Force this character to be the active actor.
                initiative = json.loads(session.initiative_json)
                for i, entry in enumerate(initiative):
                    if entry.get("type") == "player" and entry.get("id") == char.id:
                        session.active_index = i
                        break
                db.session.commit()
                return session

            atk, atk_miss = _sample(
                lambda s: combat_service.player_attack(s.id, user.id, s.version, actor_id=char.id), fresh
            )

            def cast(spell):
                def run(s):
                    party = json.loads(s.party_snapshot_json)
                    for m in party["members"]:
                        m["mana"] = m["current_mana"] = 999
                    s.party_snapshot_json = json.dumps(party)
                    db.session.commit()
                    return combat_service.player_cast_spell(s.id, user.id, s.version, spell, actor_id=char.id)

                return run

            fire, fire_miss = _sample(cast("firebolt"), fresh)
            light, light_miss = _sample(cast("lightning"), fresh)

            # Skills go through the real cast path so their scaling (or lack of
            # it) is measured the same way as everything else.
            from app.models.skill import CharacterSkill, Skill

            def skill_damage(base_field, base_value, mana=0):
                from app.models.skill import SkillTree

                tree = SkillTree.query.filter_by(name="_audit_tree").first()
                if not tree:
                    tree = SkillTree(name="_audit_tree", description="damage audit")
                    db.session.add(tree)
                    db.session.commit()
                slug = f"_audit_{base_field}_{base_value}"
                skill = Skill.query.filter_by(name=slug).first()
                if not skill:
                    skill = Skill(
                        tree_id=tree.id,
                        name=slug,
                        description="damage audit fixture",
                        skill_type="active",
                        effect_json=json.dumps({base_field: base_value}),
                        mana_cost=mana,
                        cooldown=0,
                    )
                    db.session.add(skill)
                    db.session.commit()
                if not CharacterSkill.query.filter_by(character_id=char.id, skill_id=skill.id).first():
                    db.session.add(CharacterSkill(character_id=char.id, skill_id=skill.id))
                    db.session.commit()

                def run(s):
                    party = json.loads(s.party_snapshot_json)
                    for m in party["members"]:
                        m["mana"] = m["current_mana"] = 999
                    s.party_snapshot_json = json.dumps(party)
                    db.session.commit()
                    return combat_service.player_cast_skill(s.id, user.id, s.version, skill.id, actor_id=char.id)

                mean, _ = _sample(run, fresh, samples=20)
                return mean

            print(
                f"{level:<6}{atk:>10.1f}{fire:>11.1f}{light:>11.1f}"
                f"{skill_damage('damage', 5):>11.1f}{skill_damage('spell_damage', 22):>11.1f}"
            )
            print(f"{'':<6}{'miss ' + format(atk_miss, '.0%'):>10}{'miss ' + format(fire_miss, '.0%'):>11}")

            from app.models.skill import CharacterSkill as _CS

            _CS.query.filter_by(character_id=char.id).delete()
            db.session.commit()
            db.session.delete(char)
            db.session.commit()

        print("\nskill b5  = a physical skill with effect_json {'damage': 5}")
        print("skill b22 = a caster skill with effect_json {'spell_damage': 22}")


if __name__ == "__main__":
    sys.exit(main())
