"""Boss combat abilities and special mechanics.

This module provides boss-specific combat abilities, phase transitions,
and enhanced AI behaviors that make boss encounters more engaging.

Boss Ability Types:
- AOE attacks (hit multiple party members)
- Self-buffs (increase damage, defense, resistance)
- Summon minions (spawn weaker enemies)
- Heal (restore HP)
- Phase transitions (change behavior at HP thresholds)
- Environmental effects (apply status to all combatants)

Integration:
- Called during monster_auto_turn() for boss entities
- Abilities gated by cooldowns and HP thresholds
- Enhanced loot on boss defeat
"""

from __future__ import annotations

import random
from typing import Any, Dict, List, Optional

import structlog

logger = structlog.get_logger(__name__)

# Boss ability cooldowns (in turns)
ABILITY_COOLDOWNS = {
    "aoe_attack": 3,
    "self_buff": 4,
    "summon_minion": 5,
    "heal": 6,
    "enrage": 1,  # Only triggers once at threshold
}

# HP thresholds for phase transitions
PHASE_THRESHOLDS = {
    "enrage": 0.25,  # Below 25% HP
    "desperate": 0.10,  # Below 10% HP
}


def is_boss(monster: Dict[str, Any]) -> bool:
    """Check if monster is a boss."""
    return monster.get("archetype") == "Boss" or monster.get("is_boss", False)


def get_boss_abilities(monster: Dict[str, Any]) -> List[str]:
    """Get available abilities for a boss based on level and type."""
    if not is_boss(monster):
        return []

    level = monster.get("level", 1)
    abilities = ["aoe_attack"]  # All bosses get AOE

    if level >= 3:
        abilities.append("self_buff")
    if level >= 5:
        abilities.append("summon_minion")
    if level >= 7:
        abilities.append("heal")

    return abilities


def check_ability_ready(monster: Dict[str, Any], ability: str, turn_count: int) -> bool:
    """Check if ability is off cooldown."""
    cooldowns = monster.get("ability_cooldowns", {})
    last_used = cooldowns.get(ability, -999)
    cooldown = ABILITY_COOLDOWNS.get(ability, 3)

    return (turn_count - last_used) >= cooldown


def set_ability_cooldown(monster: Dict[str, Any], ability: str, turn_count: int):
    """Mark ability as used this turn."""
    if "ability_cooldowns" not in monster:
        monster["ability_cooldowns"] = {}
    monster["ability_cooldowns"][ability] = turn_count


def check_phase_transition(monster: Dict[str, Any], current_hp: int, max_hp: int) -> Optional[str]:
    """Check if boss should transition to a new phase."""
    if not max_hp or current_hp <= 0:
        return None

    hp_percent = current_hp / max_hp
    phases = monster.get("phases_triggered", [])

    # Check enrage phase
    if hp_percent <= PHASE_THRESHOLDS["enrage"] and "enrage" not in phases:
        if "phases_triggered" not in monster:
            monster["phases_triggered"] = []
        monster["phases_triggered"].append("enrage")
        return "enrage"

    # Check desperate phase
    if hp_percent <= PHASE_THRESHOLDS["desperate"] and "desperate" not in phases:
        if "phases_triggered" not in monster:
            monster["phases_triggered"] = []
        monster["phases_triggered"].append("desperate")
        return "desperate"

    return None


def apply_phase_effects(monster: Dict[str, Any], phase: str):
    """Apply stat modifications for phase transition."""
    if phase == "enrage":
        # Increase damage by 50%
        current_dmg = monster.get("damage_bonus", 0)
        monster["damage_bonus"] = current_dmg + 0.5
        monster["phase_description"] = f"{monster.get('name', 'Boss')} enters a rage!"

    elif phase == "desperate":
        # Increase damage by 75%, reduce defense
        current_dmg = monster.get("damage_bonus", 0)
        monster["damage_bonus"] = current_dmg + 0.75
        monster["defense_penalty"] = monster.get("defense_penalty", 0) - 2
        monster["phase_description"] = f"{monster.get('name', 'Boss')} becomes desperate and reckless!"


def select_boss_ability(monster: Dict[str, Any], party: Dict[str, Any], turn_count: int) -> Optional[Dict[str, Any]]:
    """Select a boss ability to use this turn.

    Returns:
        Ability action dict or None if no ability should be used
    """
    if not is_boss(monster):
        return None

    current_hp = monster.get("hp", 0)
    max_hp = monster.get("max_hp", current_hp)

    # Check for phase transitions first
    phase = check_phase_transition(monster, current_hp, max_hp)
    if phase:
        apply_phase_effects(monster, phase)
        # Phase transition is a "free" action, still select an ability

    available_abilities = get_boss_abilities(monster)
    if not available_abilities:
        return None

    # Filter to ready abilities
    ready_abilities = [ability for ability in available_abilities if check_ability_ready(monster, ability, turn_count)]

    if not ready_abilities:
        return None

    # Prioritize based on HP and situation
    hp_percent = current_hp / max_hp if max_hp > 0 else 1.0

    # Low HP: prioritize heal
    if hp_percent < 0.3 and "heal" in ready_abilities:
        set_ability_cooldown(monster, "heal", turn_count)
        return {"type": "boss_heal", "ability": "heal"}

    # Check if party has many low-HP members: use AOE
    alive_members = [m for m in party.get("members", []) if m.get("hp", 0) > 0]
    low_hp_count = sum(1 for m in alive_members if m.get("hp", 0) < m.get("max_hp", 1) * 0.4)

    if low_hp_count >= 2 and "aoe_attack" in ready_abilities:
        set_ability_cooldown(monster, "aoe_attack", turn_count)
        return {"type": "boss_aoe", "ability": "aoe_attack"}

    # Random selection from ready abilities
    chosen = random.choice(ready_abilities)
    set_ability_cooldown(monster, chosen, turn_count)

    ability_map = {
        "aoe_attack": {"type": "boss_aoe", "ability": "aoe_attack"},
        "self_buff": {"type": "boss_buff", "ability": "self_buff"},
        "summon_minion": {"type": "boss_summon", "ability": "summon_minion"},
        "heal": {"type": "boss_heal", "ability": "heal"},
    }

    return ability_map.get(chosen)


def execute_boss_aoe(monster: Dict[str, Any], party: Dict[str, Any], session: Any) -> tuple[List[str], Dict[str, Any]]:
    """Execute AOE attack hitting all party members.

    Returns:
        (log_messages, updated_party)
    """
    logs = []
    monster_name = monster.get("name", "Boss")
    base_damage = monster.get("damage", 10)
    damage_bonus = monster.get("damage_bonus", 0)
    aoe_damage = int(base_damage * 0.7 * (1 + damage_bonus))  # AOE does 70% damage per target

    members = party.get("members", [])
    hit_count = 0

    # Only target alive members
    alive_indices = [idx for idx, m in enumerate(members) if m.get("hp", 0) > 0]
    if not alive_indices:
        return [f"{monster_name} unleashes an AOE but finds no targets!"], party

    for idx in alive_indices:
        member = members[idx]
        if member.get("hp", 0) <= 0:
            continue

        # Roll to hit
        attack_roll = random.randint(1, 20)
        member_ac = member.get("ac", 10)

        if attack_roll >= member_ac or attack_roll == 20:  # Hit or crit
            damage = aoe_damage * 2 if attack_roll == 20 else aoe_damage
            member["hp"] = max(0, member.get("hp", 0) - damage)
            crit_text = " (CRIT)" if attack_roll == 20 else ""
            logs.append(f"{monster_name}'s AOE hits {member.get('name', 'Character')} for {damage}{crit_text} damage!")
            hit_count += 1
        else:
            logs.append(f"{monster_name}'s AOE misses {member.get('name', 'Character')}!")

        members[idx] = member

    if hit_count == 0:
        logs = [f"{monster_name} unleashes an AOE attack but everyone dodges!"]
    else:
        logs.insert(0, f"{monster_name} unleashes a devastating AOE attack!")

    party["members"] = members
    return logs, party


def execute_boss_buff(monster: Dict[str, Any]) -> List[str]:
    """Execute self-buff ability."""
    monster_name = monster.get("name", "Boss")

    # Apply damage and defense buffs
    monster["damage_bonus"] = monster.get("damage_bonus", 0) + 0.3
    monster["defense_bonus"] = monster.get("defense_bonus", 0) + 2
    monster["buff_turns"] = 3  # Buff lasts 3 turns

    return [f"{monster_name} channels dark energy and grows stronger! (+30% damage, +2 AC)"]


def execute_boss_heal(monster: Dict[str, Any]) -> List[str]:
    """Execute self-heal ability."""
    monster_name = monster.get("name", "Boss")
    current_hp = monster.get("hp", 0)
    max_hp = monster.get("max_hp", current_hp)

    heal_amount = int(max_hp * 0.25)  # Heal 25% of max HP
    new_hp = min(max_hp, current_hp + heal_amount)
    monster["hp"] = new_hp

    return [f"{monster_name} regenerates {heal_amount} HP! (HP: {new_hp}/{max_hp})"]


def execute_boss_summon(monster: Dict[str, Any], session: Any) -> List[str]:
    """Execute summon minion ability.

    Note: Actual minion spawning would require integration with combat system.
    For now, just log the event.
    """
    monster_name = monster.get("name", "Boss")

    # Mark that minions were summoned (future: spawn actual minions)
    monster["minions_summoned"] = monster.get("minions_summoned", 0) + 1

    return [f"{monster_name} summons reinforcements! (Minion system pending)"]


__all__ = [
    "is_boss",
    "get_boss_abilities",
    "select_boss_ability",
    "execute_boss_aoe",
    "execute_boss_buff",
    "execute_boss_heal",
    "execute_boss_summon",
]
