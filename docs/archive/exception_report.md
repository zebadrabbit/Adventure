# Exception Handling Issues Report

Found 148 silent exception handlers
in 21 files


## app/__init__.py
Found 11 issue(s):

Line 39 (OSError):
```python
    try:
        os.makedirs(app.instance_path, exist_ok=True)
>>> except OSError:
        # In some constrained environments this might fail; ignore
        pass
```

Line 114 (Exception):
```python
                cursor.execute("PRAGMA busy_timeout=10000")  # 10 seconds
                cursor.close()
>>>         except Exception:
                pass

```

Line 117 (Exception):
```python
                pass

>>> except Exception:
        pass

```

Line 264 (Exception):
```python
                    db.session.execute(text("INSERT INTO schema_version (id, version) VALUES (1, 1)"))
                db.session.commit()
>>>     except Exception:
            pass

```

Line 276 (Exception):
```python
                )
                db.session.commit()
>>>     except Exception:
            pass

```

Line 307 (Exception):
```python
            try:
                apply_migrations()
>>>         except Exception:
                pass
            seed_items()
```

Line 311 (Exception):
```python
            seed_items()
            _seed_game_config()
>>> except Exception:
        pass

```

Line 395 (Exception):
```python
        try:
            db.session.rollback()
>>>     except Exception:
            pass

```

Line 411 (Exception):
```python
                seed_items()
                _seed_game_config()
>>>     except Exception:
            pass

```

Line 433 (Exception):
```python
                try:
                    apply_migrations()
>>>             except Exception:
                    pass
                seed_items()
```

Line 437 (Exception):
```python
                seed_items()
                _seed_game_config()
>>>     except Exception:  # swallow; normal startup path will also attempt
            pass
        return app
```


## app/admin_tui.py
Found 1 issue(s):

Line 209 (Exception):
```python
                    if self.sio and self._chat_connected:
                        await self.sio.emit("admin_chat", {"text": content})
>>>             except Exception:
                    pass
                # Log it in the event log, too
```


## app/dungeon/api_helpers/encounters.py
Found 6 issue(s):

Line 57 (Exception):
```python
                    if k in parsed:
                        base_cfg[k] = parsed[k]
>>>     except Exception:
            pass
        return base_cfg
```

Line 104 (Exception):
```python
                    if gap > 1:
                        miss_streak += gap - 1
>>>             except Exception:
                    pass
            cfg = _load_spawn_config()
```

Line 140 (Exception):
```python
                    resp["encounter_chance"] = base_chance
                    resp["encounter_roll"] = roll_val
>>>     except Exception:
            pass

```

Line 182 (Exception):
```python
                    if callable(persist):
                        persist()
>>>             except Exception:
                    pass
                try:
```

Line 196 (Exception):
```python
                        full_list = [{"slug": slug, "x": mx, "y": my} for slug, mx, my in changed_positions]
                    socketio.emit("entities_update", {"monsters": full_list, "instance_id": instance.id}, namespace="/game")
>>>             except Exception:
                    pass
        except Exception:
```

Line 198 (Exception):
```python
                except Exception:
                    pass
>>>     except Exception:
            pass
```


## app/dungeon/api_helpers/perception.py
Found 3 issue(s):

Line 141 (Exception):
```python
            try:
                session.modified = True
>>>         except Exception:
                pass
            return True, "You notice a glint of something hidden. You can Search this area.", roll_info
```

Line 152 (Exception):
```python
                    db.session.delete(r)
                    removed += 1
>>>             except Exception:
                    pass
        if removed:
```

Line 214 (Exception):
```python
        try:
            advance_for("search", actor_id=None)
>>>     except Exception:
            pass
        return True, {"found": True, "items": items, "message": msg}, 200
```


## app/dungeon/api_helpers/treasure.py
Found 1 issue(s):

Line 79 (Exception):
```python
                    hidden_flag = bool(meta.get("hidden", False))
                    loot_table_override = meta.get("loot_table") or None
>>>     except Exception:
            pass
        # If player is standing directly on the treasure tile, allow claiming even if hidden (skip perception gate)
```


## app/inventory/utils.py
Found 1 issue(s):

Line 207 (Exception):
```python
                    base_stats = dict(base_stats)
                    base_stats["dex"] = max(0, int(base_stats.get("dex", 0)) - pen)
>>>             except Exception:
                    pass
        return base_stats
```


## app/models/models.py
Found 1 issue(s):

Line 101 (Exception):
```python
                            break
                        n += 1
>>>         except Exception:
                pass

```


## app/routes/admin.py
Found 2 issue(s):

Line 233 (Exception):
```python
                        try:
                            obj.weight = float(w_raw)
>>>                     except Exception:
                            pass
                    changed += 1
```

Line 316 (Exception):
```python
                if lmax < lmin:
                    errors.append(f"Line {line}: level_max < level_min")
>>>         except Exception:
                pass
            # Optional boolean boss
```


## app/routes/combat_api.py
Found 2 issue(s):

Line 41 (Exception):
```python
            # Refresh row if mutated
            row = CombatSession.query.filter_by(id=combat_id, archived=False).first() or row
>>>     except Exception:
            pass
        data = row.to_dict()
```

Line 95 (Exception):
```python
            if init and 0 <= idx < len(init):
                data["active_entity"] = init[idx]
>>>     except Exception:
            pass
        return jsonify({"ok": True, "state": data})
```


## app/routes/dashboard.py
Found 1 issue(s):

Line 58 (Exception):
```python

                            login_user(user, remember=False)
>>>     except Exception:
            # Non-fatal; fall through to normal @login_required handling
            pass
```


## app/routes/dungeon_api.py
Found 24 issue(s):

Line 188 (Exception):
```python
                if gc:
                    pre_tick_val = gc.tick
>>>     except Exception:
            pass
        # If we successfully moved (or remained on a tile) check for a monster entity at current location.
```

Line 221 (Exception):
```python
                    except Exception:
                        db.session.rollback()
>>>         except Exception:
                pass
        # Roll for random encounter if movement attempted (moved flag) and no collision encounter already started
```

Line 265 (Exception):
```python
                    desc = (desc + "\n" + "You notice something suspicious here.").strip()
                    break
>>>     except Exception:
            pass
        resp = {
```

Line 288 (Exception):
```python
            try:
                print(f"[collision] user={current_user.id} pos=({x},{y}) combat_started id={combat_id}")
>>>         except Exception:
                pass
        else:
```

Line 421 (Exception):
```python
                    if chars:
                        avg_level = max(1, sum(c.level for c in chars) // len(chars))
>>>             except Exception:
                    pass
                cfg = LootConfig(
```

Line 563 (Exception):
```python
                            if chars:
                                avg_level_seed = max(1, sum(c.level for c in chars) // len(chars))
>>>                     except Exception:
                            pass
                        # Monsters
```

Line 640 (Exception):
```python
                        if not entities_rows:  # All invalid & removed -> reseed for current seed
                            entities_rows = _seed_entities()
>>>                 except Exception:
                        pass
                entities_json = [e.to_dict() for e in entities_rows]
```

Line 1013 (Exception):
```python
        try:
            tick_val = advance_non_combat_time(instance, tick_amount=2)
>>>     except Exception:
            pass
        resp = {"revealed_caches": revealed, "noticed_loot": noticed_loot}
```

Line 1026 (Exception):
```python
                resp["encounter_chance"] = enc_dbg["encounter_chance"]
                resp["encounter_roll"] = enc_dbg.get("encounter_roll")
>>>     except Exception:
            pass
        return jsonify(resp)
```

Line 1056 (Exception):
```python
        try:
            db.session.refresh(instance)
>>>     except Exception:
            pass
        status, payload = _claim_treasure_entity(entity_id, instance)
```

Line 1063 (Exception):
```python
            if tick_val is not None:
                payload["game_tick"] = int(tick_val)
>>>     except Exception:
            pass
        # Encounter attempt
```

Line 1073 (Exception):
```python
                payload["encounter_chance"] = enc_dbg["encounter_chance"]
                payload["encounter_roll"] = enc_dbg.get("encounter_roll")
>>>     except Exception:
            pass
        return jsonify(payload), status
```

Line 1130 (Exception):
```python
            if tick_val is not None:
                payload["game_tick"] = int(tick_val)
>>>     except Exception:
            pass
        try:
```

Line 1139 (Exception):
```python
                payload["encounter_chance"] = enc_dbg["encounter_chance"]
                payload["encounter_roll"] = enc_dbg.get("encounter_roll")
>>>     except Exception:
            pass
        return jsonify(payload), status
```

Line 1263 (Exception):
```python
            if tick_val is not None and isinstance(payload, dict):
                payload["game_tick"] = int(tick_val)
>>>     except Exception:
            pass
        try:
```

Line 1272 (Exception):
```python
                payload["encounter_chance"] = enc_dbg["encounter_chance"]
                payload["encounter_roll"] = enc_dbg.get("encounter_roll")
>>>     except Exception:
            pass
        return jsonify(payload), status
```

Line 1325 (Exception):
```python
                    if isinstance(loaded, list):
                        party = loaded
>>>             except Exception:
                    pass
            if isinstance(party, tuple):
```

Line 1331 (Exception):
```python
            if isinstance(party, (set,)):  # pragma: no cover - defensive
                party = list(party)
>>>     except Exception:
            pass
        reconstructed = False
```

Line 1373 (Exception):
```python
                        party = norm
                        reconstructed = True
>>>         except Exception:
                pass
        # Fallback: if party missing or empty, populate from all user characters so UI still shows panels.
```

Line 1402 (Exception):
```python
                if tmp:
                    party = tmp
>>>         except Exception:
                pass
        seed = session.get("dungeon_seed")
```

Line 1417 (Exception):
```python
                    session["dungeon_instance_id"] = inst.id
                    dungeon_instance_id = inst.id
>>>         except Exception:
                pass
        if dungeon_instance_id:
```

Line 1499 (Exception):
```python
                        tmp_stats = json.loads(stats_s)
                        cls_name = (tmp_stats.get("class") or "adventurer").capitalize()
>>>                 except Exception:
                        pass
                    enriched_party.append(
```

Line 1518 (Exception):
```python
                        }
                    )
>>>         except Exception:
                pass
        try:
```

Line 1524 (Exception):
```python
                f"[adventure] raw_party_type={type(raw_party).__name__} reconstructed={reconstructed} raw_len={len(raw_party) if isinstance(raw_party, list) else 'n/a'} enriched_len={len(enriched_party) if isinstance(enriched_party, list) else 'n/a'}"
            )
>>>     except Exception:
            pass
        return render_template("adventure.html", party=enriched_party, seed=seed, pos=pos, game_clock=clock)
```


## app/routes/inventory_api.py
Found 5 issue(s):

Line 151 (Exception):
```python
            try:
                out[k] = int(out.get(k, 0)) + int(v)
>>>         except Exception:
                pass
        return out
```

Line 256 (Exception):
```python
                        ch.items = dump_inventory(inv_objs)
                        db.session.flush()
>>>             except Exception:
                    pass
            except Exception:
```

Line 316 (Exception):
```python
        try:
            advance_for("equip")
>>>     except Exception:
            pass
        return jsonify({"ok": True, "slot": slot, "equipped": slug})
```

Line 346 (Exception):
```python
        try:
            advance_for("unequip")
>>>     except Exception:
            pass
        return jsonify({"ok": True, "slot": slot, "unequipped": slug})
```

Line 392 (Exception):
```python
        try:
            advance_for("consume")
>>>     except Exception:
            pass
        return jsonify({"ok": True, "consumed": slug, "effects": {"hp": heal, "mana": mana}})
```


## app/routes/loot_api.py
Found 3 issue(s):

Line 37 (Exception):
```python
                generate_loot_for_seed(cfg, walkables)
                rows = DungeonLoot.query.filter_by(seed=inst.seed, claimed=False).all()
>>>         except Exception:
                pass
        loot = []
```

Line 105 (Exception):
```python
                if sess_int != effective_user_id:
                    effective_user_id = sess_int
>>>         except Exception:
                pass
        if effective_user_id is None:
```

Line 178 (Exception):
```python
                    row.claimed = False
                    db.session.flush()
>>>             except Exception:
                    pass
                return (
```


## app/routes/seed_api.py
Found 1 issue(s):

Line 80 (Exception):
```python
                    # Remove loot rows for old seed only (avoid nuking other seeds from other instances in multi-user future)
                    DungeonLoot.query.filter_by(seed=old_seed).delete(synchronize_session=False)
>>>             except Exception:
                    pass
            instance.seed = seed
```


## app/server.py
Found 9 issue(s):

Line 46 (Exception):
```python
            try:
                apply_migrations()  # structured versioned migrations
>>>         except Exception:
                pass
            seed_items()
```

Line 52 (Exception):
```python
            try:
                apply_migrations()
>>>         except Exception:
                pass
            _load_sql_item_seeds()
```

Line 58 (Exception):
```python
            try:
                apply_migrations()
>>>         except Exception:
                pass
            _seed_game_config()
```

Line 83 (Exception):
```python
                    }
                    GameConfig.set("monster_ai", _json.dumps(default_cfg))
>>>         except Exception:
                pass
        try:
```

Line 102 (OSError):
```python
        try:
            os.makedirs(log_dir, exist_ok=True)
>>>     except OSError:
            pass
        log_path = os.path.join(log_dir, "app.log")
```

Line 772 (Exception):
```python
                    )
                )
>>>     except Exception:
            pass
        # Add new columns to combat_session if table already existed (older deployments)
```

Line 802 (Exception):
```python
                if "version" not in existing:
                    _add("version INTEGER NOT NULL DEFAULT 1")
>>>     except Exception:
            pass
        # Add 'xp' and 'level' columns to character if missing
```

Line 941 (Exception):
```python
                except Exception:
                    db.session.rollback()
>>>     except Exception:
            # Swallow any inspection/create failures; earlier logic may already have succeeded.
            pass
```

Line 989 (Exception):
```python
                try:
                    db.create_all()
>>>             except Exception:
                    pass
            else:
```


## app/services/combat_service.py
Found 37 issue(s):

Line 59 (Exception):
```python
        try:
            socketio.emit(event, {"id": session.id, "state": session.to_dict()}, namespace="/adventure")
>>>     except Exception:
            pass

```

Line 280 (Exception):
```python
                    session, f"Turn {session.combat_turn}: {actor.get('name','Monster')}'s turn.", code=COMBAT_TURN_START
                )
>>>     except Exception:
            pass
        # Emit lightweight turn_change event (non-critical). Clients may ignore if unimplemented.
```

Line 294 (Exception):
```python
                namespace="/adventure",
            )
>>>     except Exception:
            pass

```

Line 321 (Exception):
```python
                else:
                    _append_log(session, f"{actor.get('name','Monster')} is acting (AI).", code=ACTOR_START_ACTION)
>>>         except Exception:
                pass
        elif session.phase == "action":
```

Line 353 (Exception):
```python
                        try:
                            xp_map[str(m.get("char_id") or m.get("id"))] = share
>>>                     except Exception:
                            pass
                if rewards.get("items") and char_rows:
```

Line 383 (Exception):
```python
                try:
                    rewards["xp"] = {"total": xp_total, "per_member": xp_map}
>>>             except Exception:
                    pass
            except Exception:
```

Line 410 (Exception):
```python
                                        except Exception:
                                            potion_count += 1
>>>                     except Exception:
                            pass
                    counts = party.setdefault("item_counts", {})
```

Line 415 (Exception):
```python
                    counts["potion-healing"] = potion_count
                    session.party_snapshot_json = json.dumps(party)
>>>         except Exception:
                pass
            # Direct write-through of snapshot HP/mana for members to guarantee persistence even if helper fails later
```

Line 437 (Exception):
```python
                        try:
                            stats_obj["hp"] = int(m.get("hp"))
>>>                     except Exception:
                            pass
                    mana_val = m.get("mana", m.get("current_mana"))
```

Line 443 (Exception):
```python
                        try:
                            stats_obj["current_mana"] = int(mana_val)
>>>                     except Exception:
                            pass
                    row.stats = _json.dumps(stats_obj)
```

Line 451 (Exception):
```python
                except Exception:
                    db.session.rollback()
>>>         except Exception:
                pass
            try:
```

Line 455 (Exception):
```python
            try:
                persist_snapshot_resources(session, propagate_single_to_all=False)
>>>         except Exception:
                pass
            set_combat_state(False)
```

Line 468 (Exception):
```python
            try:
                persist_snapshot_resources(session, propagate_single_to_all=False)
>>>         except Exception:
                pass
            set_combat_state(False)
```

Line 476 (Exception):
```python
        try:
            socketio.emit(event, session.to_dict(), namespace="/adventure")
>>>     except Exception:
            pass

```

Line 493 (Exception):
```python
            try:
                _emit_session("combat_complete", session)
>>>         except Exception:
                pass

```

Line 518 (Exception):
```python
                try:
                    print(f"[combat:persist] {msg}")
>>>             except Exception:
                    pass

```

Line 546 (Exception):
```python
                try:
                    stats_obj["hp"] = int(m.get("hp", stats_obj.get("hp", 0)))
>>>             except Exception:
                    pass
                mana_val = m.get("mana", m.get("current_mana"))
```

Line 552 (Exception):
```python
                    try:
                        stats_obj["current_mana"] = int(mana_val)
>>>                 except Exception:
                        pass
                row.stats = _json.dumps(stats_obj)
```

Line 569 (Exception):
```python
                    try:
                        stats_obj["hp"] = int(src.get("hp", stats_obj.get("hp", 0)))
>>>                 except Exception:
                        pass
                    mana_val = src.get("mana", src.get("current_mana"))
```

Line 575 (Exception):
```python
                        try:
                            stats_obj["current_mana"] = int(mana_val)
>>>                     except Exception:
                            pass
                    row.stats = _json.dumps(stats_obj)
```

Line 707 (Exception):
```python
                        }
                print(f"[combat:flee] entry combat_id={combat_id} first_member={first_dbg}")
>>>         except Exception:
                pass
        initiative = json.loads(session.initiative_json or "[]")
```

Line 749 (Exception):
```python
                                try:
                                    stats_obj["hp"] = int(hp_val)
>>>                             except Exception:
                                    pass
                            mana_val = active.get("mana", active.get("current_mana"))
```

Line 755 (Exception):
```python
                                try:
                                    stats_obj["current_mana"] = int(mana_val)
>>>                             except Exception:
                                    pass
                            row.stats = _json.dumps(stats_obj)
```

Line 763 (Exception):
```python
                            except Exception:
                                db.session.rollback()
>>>         except Exception:
                pass
            try:
```

Line 769 (Exception):
```python
                try:
                    db.session.refresh(session)
>>>             except Exception:
                    pass
                # Re-enable single-member propagation (narrow) to handle tests that still
```

Line 774 (Exception):
```python
                # rely on first-row queries for HP.
                persist_snapshot_resources(session, propagate_single_to_all=True)
>>>         except Exception:
                pass
            set_combat_state(False)
```

Line 784 (Exception):
```python
            try:
                db.session.refresh(session)
>>>         except Exception:
                pass
            _emit_session("combat_update", session)
```

Line 882 (Exception):
```python
                    char_row.items = json.dumps(new_inv)
                    db.session.add(char_row)
>>>     except Exception:
            pass
        # Decrement surfaced party item counts if present and we actually removed an item.
```

Line 891 (Exception):
```python
                    current = int(counts.get("potion-healing", 0))
                    counts["potion-healing"] = max(0, current - 1)
>>>     except Exception:
            pass
        session.party_snapshot_json = json.dumps(party)
```

Line 979 (Exception):
```python
        try:
            dmg = int(apply_resistances(dmg, ["fire"], resistances))
>>>     except Exception:
            pass
        session.monster_hp = max(0, (session.monster_hp or 0) - dmg)
```

Line 1019 (Exception):
```python
                if refreshed:
                    return refreshed
>>>     except Exception:
            pass
        return session
```

Line 1076 (Exception):
```python
                        try:
                            persist_snapshot_resources(session, propagate_single_to_all=False)
>>>                     except Exception:
                            pass
                        set_combat_state(False)
```

Line 1083 (Exception):
```python
                        _emit_if_completed(session)
                        return
>>>         except Exception:
                pass
            # Spell attempt
```

Line 1126 (Exception):
```python
                                )
                        used_spell = True
>>>             except Exception:
                    pass
            if not used_spell:
```

Line 1163 (Exception):
```python
                monster["last_turn"] = session.combat_turn
                session.monster_json = json.dumps(monster)
>>>         except Exception:
                pass
            _emit_session("combat_update", session)
```

Line 1167 (Exception):
```python
            _emit_session("combat_update", session)
            _emit_if_completed(session)
>>>     except Exception:
            pass

```

Line 1226 (Exception):
```python
            if _is_monster_turn(session):
                monster_auto_turn(session)
>>>     except Exception:
            pass
```


## app/services/monster_ai.py
Found 1 issue(s):

Line 38 (Exception):
```python
                if isinstance(raw, dict):
                    return raw
>>>     except Exception:
            pass
        return {}
```


## app/services/monster_patrol.py
Found 1 issue(s):

Line 51 (Exception):
```python
                if isinstance(raw, dict):
                    return raw
>>>     except Exception:
            pass
        return {}
```


## app/services/time_service.py
Found 3 issue(s):

Line 102 (Exception):
```python
        try:
            socketio.emit("time_update", payload, namespace="/adventure")
>>>     except Exception:
            # Emission failure should not rollback time advancement
            pass
```

Line 128 (Exception):
```python
            try:
                db.session.rollback()
>>>         except Exception:
                pass
            return bool(getattr(clock, "combat", False))
```

Line 134 (Exception):
```python
        try:
            socketio.emit("combat_state", {"combat": new_val}, namespace="/adventure")
>>>     except Exception:
            pass
        return new_val
```


## app/websockets/game.py
Found 9 issue(s):

Line 99 (Exception):
```python
                        room=room,
                    )
>>>     except Exception:
            pass

```

Line 260 (Exception):
```python
                    except Exception:
                        db.session.rollback()
>>>         except Exception:
                pass
        encounter_debug = {}
```

Line 297 (Exception):
```python
                    desc = (desc + "\n" + "You notice something suspicious here.").strip()
                    break
>>>     except Exception:
            pass
        resp = {
```

Line 318 (Exception):
```python
                if tick_val is not None:
                    resp["game_tick"] = int(tick_val)
>>>         except Exception:
                pass
        emit("dungeon_move_result", resp)
```

Line 356 (Exception):
```python
        try:
            tick_val = advance_non_combat_time(instance, tick_amount=2)
>>>     except Exception:
            pass
        resp = {"revealed_caches": revealed, "noticed_loot": noticed_loot}
```

Line 368 (Exception):
```python
                resp["encounter_chance"] = enc_dbg["encounter_chance"]
                resp["encounter_roll"] = enc_dbg.get("encounter_roll")
>>>     except Exception:
            pass
        emit("dungeon_search_result", resp)
```

Line 393 (Exception):
```python
        try:
            db.session.refresh(instance)
>>>     except Exception:
            pass
        status, payload_resp = _claim_treasure_entity(entity_id, instance)
```

Line 404 (Exception):
```python
            if tick_val is not None:
                payload_resp["game_tick"] = int(tick_val)
>>>     except Exception:
            pass
        try:
```

Line 413 (Exception):
```python
                payload_resp["encounter_chance"] = enc_dbg["encounter_chance"]
                payload_resp["encounter_roll"] = enc_dbg.get("encounter_roll")
>>>     except Exception:
            pass
        # Character assignment side effect (inventory update notification) isn't handled server push yet;
```


## app/websockets/lobby.py
Found 26 issue(s):

Line 60 (Exception):
```python
            if len(_dungeon_runtime_samples) > 200:
                del _dungeon_runtime_samples[:100]
>>>     except Exception:
            pass

```

Line 157 (Exception):
```python
                        room="admins",
                    )
>>>         except Exception:
                pass
        if user in muted_usernames:
```

Line 199 (Exception):
```python
                        if u.muted:
                            muted_usernames.add(username)
>>>             except Exception:
                    pass
            else:
```

Line 213 (Exception):
```python
                        if username in muted_usernames and not u.muted:
                            muted_usernames.discard(username)
>>>             except Exception:
                    pass
            # Reject banned users immediately
```

Line 230 (Exception):
```python
                        banned_usernames.discard(username)
                        allow_admin_override = True
>>>         except Exception:
                pass
            if username in banned_usernames and not allow_admin_override:
```

Line 258 (Exception):
```python
            elif stored_role == "mod":
                join_room("mods")
>>>     except Exception:
            # Silently ignore connect bookkeeping errors
            pass
```

Line 306 (Exception):
```python
            if entry.get("legacy_ok"):
                emit("admin_online_users", payload, room=sid, namespace="/")
>>>     except Exception:
            pass

```

Line 333 (Exception):
```python
                if entry and entry.get("role") == "admin":
                    allow = True
>>>         except Exception:
                pass
        # Removed permissive test bypass and DB lookup fallback to ensure non-admins never receive admin_status.
```

Line 433 (Exception):
```python
                        if dyn_username:
                            entry["username"] = dyn_username
>>>                 except Exception:
                        pass
            except Exception:
```

Line 435 (Exception):
```python
                    except Exception:
                        pass
>>>         except Exception:
                pass
        # Additional guard: if monkeypatched current_user claims admin but username mismatch, deny
```

Line 454 (Exception):
```python
                )
                return
>>>     except Exception:
            pass
        # Final strict check: must have admin role, authenticated entry, and active session user id
```

Line 471 (Exception):
```python
                    is_auth=(entry or {}).get("is_auth"),
                )
>>>         except Exception:
                pass
            return
```

Line 483 (Exception):
```python
                    length=(len(message) if message else 0),
                )
>>>         except Exception:
                pass
            return
```

Line 491 (Exception):
```python
            try:
                _log.warn(event="admin_direct_message_target_missing", target=target)
>>>         except Exception:
                pass
            return
```

Line 505 (Exception):
```python
                length=len(message),
            )
>>>     except Exception:
            pass
        emit(
```

Line 536 (Exception):
```python
                online_size=len(online),
            )
>>>     except Exception:
            pass
        if sid:
```

Line 551 (Exception):
```python
                try:
                    _log.warn(event="admin_kick_disconnect_error", error=str(e))
>>>             except Exception:
                    pass
        else:
```

Line 563 (Exception):
```python
                            room=_sid,
                        )
>>>                 except Exception:
                        pass
        # Aggressive removal: drop any online entries matching username (even if SID lookup failed)
```

Line 576 (Exception):
```python
                remaining=[v.get("username") for v in online.values()],
            )
>>>     except Exception:
            pass

```

Line 598 (Exception):
```python
                u.banned = True
                db.session.commit()
>>>     except Exception:
            pass
        # Disconnect if currently online
```

Line 610 (Exception):
```python
                )
                disconnect(sid=sid)
>>>         except Exception:
                pass

```

Line 631 (Exception):
```python
                u.banned = False
                db.session.commit()
>>>     except Exception:
            pass

```

Line 666 (Exception):
```python
                u.muted = True
                db.session.commit()
>>>     except Exception:
            pass

```

Line 688 (Exception):
```python
                u.muted = False
                db.session.commit()
>>>     except Exception:
            pass

```

Line 746 (Exception):
```python
                    room=sid,
                )
>>>         except Exception:
                pass
            try:
```

Line 750 (Exception):
```python
            try:
                disconnect(sid=sid)
>>>         except Exception:
                pass
        # Hard prune any remaining entries for that username
```
