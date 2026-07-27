/*
 * project: Adventure MUD
 * module: equipment-shared.js
 *
 * Shared equipment logic used by both equipment.js (adventure page modal)
 * and equipment-enhanced.js (dashboard EquipmentManager). Each consumer
 * keeps its own DOM template; only the previously-duplicated logic lives
 * here so the two can't drift apart again (encumbrance thresholds, affix
 * totaling). Load before either consumer.
 */
(function () {
  "use strict";

  /**
   * Classify an encumbrance payload for display.
   * Returns null when the payload is unusable, else:
   * { pct, barClass, textClass, statusLabel, penaltyNote, weightLabel, status }
   */
  function encumbranceView(enc) {
    if (!enc || typeof enc.weight !== "number" || typeof enc.capacity !== "number") return null;
    const pct = enc.capacity > 0 ? Math.min(100, (enc.weight / enc.capacity) * 100) : 0;
    const barClass = enc.status === "blocked" ? "bg-danger" : (enc.status === "encumbered" ? "bg-warning" : "bg-success");
    const textClass = enc.status === "blocked" ? "text-danger" : (enc.status === "encumbered" ? "text-warning" : "");
    const statusLabel = enc.status === "blocked"
      ? "Overloaded — cannot carry more"
      : (enc.status === "encumbered" ? "Encumbered" : "");
    const penaltyNote = (enc.status !== "normal" && enc.dex_penalty) ? ` (-${enc.dex_penalty} DEX)` : "";
    return {
      pct,
      barClass,
      textClass,
      statusLabel,
      penaltyNote,
      weightLabel: `${enc.weight.toFixed(1)} / ${enc.capacity.toFixed(1)}`,
      status: enc.status,
    };
  }

  /**
   * Sum equipped-gear affix bonuses into a display string like
   * "+2 STR, +1.5 DEX" (empty string when there are no bonuses).
   */
  function gearBonusText(gear) {
    const totals = {};
    Object.values(gear || {}).forEach((inst) => {
      if (!inst) return;
      const affixes = Array.isArray(inst.affixes) ? inst.affixes
        : (inst.effects && typeof inst.effects === "object"
          ? Object.entries(inst.effects).map(([stat, val]) => ({ stat, val }))
          : []);
      affixes.forEach((a) => {
        if (!a || !a.stat || typeof a.val !== "number") return;
        totals[a.stat] = (totals[a.stat] || 0) + a.val;
      });
    });
    return Object.entries(totals)
      .filter(([, v]) => v !== 0)
      .map(([stat, v]) => {
        const num = Number.isInteger(v) ? v : Math.round(v * 10) / 10;
        return `${num >= 0 ? "+" : ""}${num} ${stat.toUpperCase()}`;
      })
      .join(", ");
  }

  window.EquipmentShared = { encumbranceView, gearBonusText };
})();
