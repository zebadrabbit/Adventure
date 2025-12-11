# Combat Visual Effects System

## Overview
The combat system now includes a comprehensive visual effects system with floating damage numbers, particle effects, spell animations, and status indicators.

## Features

### 1. Floating Damage Numbers
- **Damage**: Red numbers with shake effect on target
- **Critical Hits**: Large golden numbers with enhanced glow
- **Healing**: Green numbers with upward float
- **Misses**: Gray "MISS!" text with no shake

### 2. Particle Effects

#### Firebolt
- 30 fire particles in orange/red/yellow gradient
- Trails from caster to target
- Explosion effect on impact
- Fire element damage type

#### Ice Shard
- 5 crystalline shards rotating in flight
- Blue/cyan color palette
- Frost explosion on impact
- Ice element damage type

#### Lightning Bolt
- Instant branching lightning effect
- Golden yellow color with glow
- 3 random branch bolts
- Lightning element damage type

#### Heal
- 20 green sparkles rising upward
- Timed release for cascading effect
- Glow effect on target

### 3. Visual Feedback

#### Hit Effects
- **Shake Animation**: Normal (4px) or Strong (8px) based on critical
- **Flash Effect**: Brief color overlay (red for damage, green for heal)
- **Casting Glow**: Pulsing glow on spell buttons during cast

#### Status Indicators
- Circular badges in top-right of character/monster cards
- Icons: poison, burn, freeze, stun, shield, regen, curse, blessed
- Pulse animation for active effects

## Technical Implementation

### Files Created
1. **combat-effects.js** (576 lines)
   - `CombatEffects` class with particle system
   - Canvas-based rendering at 60fps
   - Methods: `showDamage()`, `createParticles()`, `addStatusIndicator()`

2. **combat-effects.css** (147 lines)
   - Keyframe animations for damage floats
   - Shake animations (normal/strong)
   - Status indicator styling

### Integration Points

#### combat.js Updates
- Wired `showDamage()` to monster/party HP changes
- Added spell effect triggers in `doAction()`
- Damage metadata from server state: `last_damage_to_monster`, `last_damage_to_party`

#### combat.html Updates
- Added combat-effects.css and combat-effects.js includes
- Expanded spell buttons: Firebolt, Ice Shard, Lightning Bolt
- Positioned status indicator containers

#### Backend Updates
1. **models.py**: Added `last_damage_json` field to `CombatSession`
2. **combat_service.py**:
   - Track damage in `player_attack()`, `player_cast_spell()`, monster attacks
   - Spell configuration with mana costs and damage dice
   - Support for 3 spell types: firebolt (5 MP), ice_shard (6 MP), lightning (8 MP)

3. **Migration**: `27d036aa8a43_add_damage_tracking_to_combat.py`

## Usage

### Client-Side
```javascript
// Show damage number
window.combatEffects.showDamage(targetElement, 42, {
    isCritical: true,
    isHeal: false,
    isMiss: false
});

// Create spell effect
window.combatEffects.createParticles(
    casterElement,
    targetElement,
    'firebolt' // or 'ice_shard', 'lightning', 'heal'
);

// Add status indicator
window.combatEffects.addStatusIndicator(targetElement, 'burn', 5000);
```

### Server-Side
Damage is automatically tracked in combat state:
```python
# In combat_service.py
session.last_damage_json = json.dumps({
    "to_monster": {
        "amount": dmg,
        "is_miss": False,
        "is_critical": crit
    }
})
```

## Performance
- Canvas rendering: ~60fps even with 50+ particles
- Particle cleanup: Automatic on lifecycle completion
- Memory: Effects container and canvas added to DOM once, reused

## Future Enhancements
- More spell types (Heal spell, Poison Cloud, Meteor)
- Monster spell effects
- Combo/chain attack animations
- Sound effects integration
- Screen shake for massive damage
- Damage over time visual ticks
