"""Socket.IO combat namespace registration.

Provides a dedicated namespace "/adventure" for combat session updates.
Clients connect via: io('/adventure')
Server emits combat_update / combat_end / combat_complete events already using this namespace.

We keep handlers minimal for now; future extensions may include room joins per combat id
(e.g., join_combat { id }) so we can emit only to involved parties instead of broadcasting
combat traffic to all connected players on the namespace.
"""

from flask_login import current_user
from flask_socketio import Namespace, emit, join_room, leave_room

from app import socketio
from app.instrumentation.socket_stats import socket_stats  # lightweight runtime tracker


class CombatNamespace(Namespace):  # pragma: no cover - thin glue
    namespace = "/adventure"
    # Dedupe Strategy (client + server):
    #  - Client keeps window._combatJoinedIds set and only emits 'combat_join' once per combat id
    #    for the lifecycle of the page (see adventure.js initCombatSocket()).
    #  - Server maintains per-SID membership map (_sid_rooms) so that if a reconnection or
    #    racing frontend script re-emits 'combat_join', we acknowledge via a lightweight
    #    'combat_joined' payload with {cached: True} and suppress the expensive full
    #    'combat_update' snapshot broadcast. This eliminates redundant multi-hundred KB
    #    state payloads observed during rapid navigation or hot reload.
    # The in-memory map is best-effort (resets on process restart). For multi-worker scaling
    # a shared store (Redis) would be appropriate.
    # This is a best-effort in-memory cache; on process restart or if a SID
    # changes (e.g., due to transport upgrade) an initial full snapshot is
    # re-sent, which is acceptable. For large scale or multi-worker, a
    # distributed presence map would be needed.
    _sid_rooms: dict[str, set] = {}

    def on_connect(self):  # noqa: D401
        try:
            _ = getattr(current_user, "username", "Anonymous")
        except Exception:
            pass
        # Instrumentation: record SID; user id may be None if unauthenticated
        try:
            from flask import request as _rq

            socket_stats.on_connect(
                user_id=getattr(current_user, "id", None),
                username=getattr(current_user, "username", None),
                sid=getattr(_rq, "sid", "unknown"),
                namespace=self.namespace,
            )
        except Exception:
            pass
        return None

    def on_disconnect(self, *args, **kwargs):  # noqa: D401
        """Handle client disconnect.

        Accept arbitrary args to stay compatible across python-socketio /
        engineio versions which may pass (reason) or nothing. We intentionally
        suppress disconnect noise; future enhancement could track active
        combat rooms and auto-leave here.
        """
        # Instrumentation cleanup
        try:
            from flask import request as _rq

            socket_stats.on_disconnect(getattr(_rq, "sid", "unknown"))
        except Exception:
            pass
        return None

    # ---- Room management ----
    def on_combat_join(self, data):  # data: { combat_id }
        from flask import current_app, request

        sid = getattr(request, "sid", None)
        try:
            combat_id = int(data.get("combat_id")) if isinstance(data, dict) else None
        except Exception:
            combat_id = None
        if not combat_id:
            emit("combat_error", {"error": "combat_id_required"})
            return
        try:
            from app.models.models import CombatSession as _CS

            row = _CS.query.filter_by(id=combat_id, archived=False, user_id=current_user.id).first()
            if not row:
                emit("combat_error", {"error": "not_found"})
                return
            room = f"combat:{combat_id}"
            # Guard: if this SID already in room, acknowledge without rebroadcasting full state.
            sid_rooms = self._sid_rooms.setdefault(sid, set()) if sid else set()
            if sid and room in sid_rooms:
                current_app.logger.debug(f"[combat] duplicate join suppressed sid={request.sid} combat_id={combat_id}")
                emit("combat_joined", {"combat_id": combat_id, "cached": True})
                return
            join_room(room, sid=sid)
            if sid is not None:
                try:
                    self._sid_rooms.setdefault(sid, set()).add(room)
                except Exception:
                    pass
            current_app.logger.debug(f"[combat] first join sid={request.sid} combat_id={combat_id}")
            emit("combat_joined", {"combat_id": combat_id})
            # Only send the full state snapshot on first join to reduce bandwidth spam.
            try:
                emit("combat_update", {"state": row.to_dict(), "combat_id": combat_id})
            except Exception:
                pass
        except Exception:
            emit("combat_error", {"error": "join_failed"})

    def on_combat_leave(self, data):  # data optional { combat_id }
        from flask import request

        sid = getattr(request, "sid", None)
        try:
            combat_id = int(data.get("combat_id")) if isinstance(data, dict) else None
        except Exception:
            combat_id = None
        if combat_id:
            room = f"combat:{combat_id}"
            leave_room(room, sid=sid)
            # Remove tracking so a future rejoin will broadcast fresh state.
            if sid in self._sid_rooms:
                try:
                    self._sid_rooms[sid].discard(room)
                except Exception:
                    pass
        emit("combat_left", {"combat_id": combat_id})

    # ---- Action helpers ----
    def _perform_action(self, action: str, combat_id: int, payload: dict):
        from app import db  # local import to avoid circulars at module load
        from app.services import combat_service as _svc

        version = payload.get("version") if isinstance(payload, dict) else None
        if not isinstance(version, int):
            version = 0
        actor_id = payload.get("actor_id") if isinstance(payload, dict) else None
        extra = {}
        try:
            if action == "attack":
                result = _svc.player_attack(combat_id, current_user.id, version, actor_id=actor_id)
            elif action == "flee":
                result = _svc.player_flee(combat_id, current_user.id, version, actor_id=actor_id)
            elif action == "defend":
                result = _svc.player_defend(combat_id, current_user.id, version, actor_id=actor_id)
            elif action == "cast":
                spell = payload.get("spell") if isinstance(payload, dict) else None
                result = _svc.player_cast_spell(combat_id, current_user.id, version, spell, actor_id=actor_id)
            elif action == "use_item":
                slug = payload.get("slug") if isinstance(payload, dict) else None
                result = _svc.player_use_item(combat_id, current_user.id, version, slug, actor_id=actor_id)
            elif action == "end_turn":
                # Reuse existing end_turn route logic by mimicking minimal phases
                from app.services.combat_service import (
                    _advance_turn,
                    _check_end,
                    _load_session,
                    _progress_phase,
                )

                session_row = _load_session(combat_id)
                if not session_row:
                    result = {"error": "not_found"}
                elif session_row.user_id != current_user.id:
                    result = {"error": "forbidden"}
                else:
                    import json as _json

                    init = _json.loads(session_row.initiative_json or "[]")
                    if not init:
                        result = {"error": "no_initiative"}
                    else:
                        actor = init[session_row.active_index]
                        if actor.get("type") != "player" or actor.get("controller_id") != current_user.id:
                            result = {"error": "not_your_turn"}
                        else:
                            advanced = _progress_phase(session_row)
                            if not advanced and session_row.phase != "start":
                                advanced = _progress_phase(session_row)
                            if not advanced and session_row.phase != "end":
                                _advance_turn(session_row)
                            _check_end(session_row)
                            db.session.commit()
                            result = {"ok": True}
                            extra["state"] = session_row.to_dict()
            else:
                result = {"error": "bad_action"}
        except Exception:
            result = {"error": "action_failed"}
        return result, extra

    def on_combat_action(self, data):  # data: { action, combat_id, version, ... }
        from flask import request

        _sid = getattr(request, "sid", None)  # reserved for future auditing/logging
        if not isinstance(data, dict):
            emit("combat_error", {"error": "bad_payload"})
            return
        combat_id = data.get("combat_id")
        action = (data.get("action") or "").lower()
        try:
            combat_id = int(combat_id)
        except Exception:
            emit("combat_error", {"error": "combat_id_required"})
            return
        result, extra = self._perform_action(action, combat_id, data)
        room = f"combat:{combat_id}"
        emit("combat_action_ack", {"action": action, "combat_id": combat_id, **result}, room=room)
        if extra.get("state"):
            emit("combat_update", {"combat_id": combat_id, "state": extra["state"]}, room=room)


# Register the namespace instance
socketio.on_namespace(CombatNamespace(CombatNamespace.namespace))
