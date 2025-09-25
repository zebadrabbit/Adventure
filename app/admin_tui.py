"""Textual-based VT102-compatible Admin Console (TUI).

Panels:
 - Users Online
 - Dungeon Seeds In Progress
 - Chat (via Socket.IO client if server is reachable)
 - Event Log (bottom)

Run with: `python run.py admin-tui`
"""
from __future__ import annotations

import asyncio
import os
from datetime import datetime
from typing import Optional

from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Static, Input, TextLog
from textual.containers import Horizontal, Vertical

# Optional Socket.IO client for chat/events
try:
    import socketio  # type: ignore
except Exception:  # pragma: no cover
    socketio = None

from app import app as flask_app, db
from app.models.models import User
from app.models.dungeon_instance import DungeonInstance


class AdminConsole(App):
    CSS = """
    Screen { layout: vertical; }
    .top-row { height: 3fr; }
    .bottom-row { height: 1fr; }
    .panel { border: tall $primary; padding: 1 1; }
    .panel-title { content-align: center middle; text-style: bold; }
    #users-panel, #seeds-panel, #chat-panel { width: 1fr; }
    #log-panel { height: 100%; }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("r", "refresh", "Refresh Now"),
    ]

    def __init__(self, server_url: Optional[str] = None) -> None:
        super().__init__()
        self.server_url = server_url or os.getenv("ADMIN_TUI_SERVER", "http://127.0.0.1:5000")
        self.sio: Optional["socketio.AsyncClient"] = None
        self._chat_connected = False

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Vertical(classes="top-row"):
            with Horizontal():
                with Vertical(id="users-panel", classes="panel"):
                    yield Static("Users Online", classes="panel-title")
                    self.users_body = TextLog(highlight=False, markup=False, wrap=False)
                    yield self.users_body
                with Vertical(id="seeds-panel", classes="panel"):
                    yield Static("Dungeon Seeds", classes="panel-title")
                    self.seeds_body = TextLog(highlight=False, markup=False, wrap=False)
                    yield self.seeds_body
                with Vertical(id="chat-panel", classes="panel"):
                    yield Static("Chat (Socket.IO)", classes="panel-title")
                    self.chat_body = TextLog(highlight=False, markup=False, wrap=True)
                    self.chat_input = Input(placeholder="Type message and press Enter…")
                    yield self.chat_body
                    yield self.chat_input
        with Vertical(id="log-panel", classes="panel bottom-row"):
            yield Static("Event Log", classes="panel-title")
            self.event_log = TextLog(highlight=False, markup=False, wrap=True)
            yield self.event_log
        yield Footer()

    async def on_mount(self) -> None:
        # Kick off periodic refresh tasks
        self.call_after_refresh(self.refresh_all)
        self._refresh_task = asyncio.create_task(self._periodic_refresh())
        self._chat_task = asyncio.create_task(self._chat_connect())

    async def _periodic_refresh(self) -> None:
        while True:
            await self.refresh_all()
            await asyncio.sleep(5.0)

    async def refresh_all(self) -> None:
        await asyncio.gather(self.refresh_users(), self.refresh_seeds())

    async def refresh_users(self) -> None:
        # For now, show registered users and mark those with role=admin; online tracking can be added later.
        def _query():
            with flask_app.app_context():
                rows = User.query.order_by(User.username.asc()).all()
                return [f"- {u.username} [{getattr(u,'role','user')}]" for u in rows]
        lines = await asyncio.to_thread(_query)
        self.users_body.clear()
        if lines:
            for ln in lines:
                self.users_body.write(ln)
        else:
            self.users_body.write("(no users)")

    async def refresh_seeds(self) -> None:
        def _query():
            with flask_app.app_context():
                rows = db.session.query(DungeonInstance).all()
                return [f"- seed={r.seed} pos=({r.pos_x},{r.pos_y},{r.pos_z}) user_id={r.user_id}" for r in rows]
        try:
            lines = await asyncio.to_thread(_query)
        except Exception:
            lines = ["(no data)"]
        self.seeds_body.clear()
        if lines:
            for ln in lines:
                self.seeds_body.write(ln)

    async def _chat_connect(self) -> None:
        if socketio is None:
            self.chat_body.write("python-socketio not available; chat disabled.")
            return
        try:
            self.sio = socketio.AsyncClient()

            @self.sio.event
            async def connect():
                self._chat_connected = True
                self.chat_body.write(f"[connected to {self.server_url}]")

            @self.sio.event
            async def disconnect():
                self._chat_connected = False
                self.chat_body.write("[disconnected]")

            @self.sio.on("chat_message")
            async def _on_chat_message(data):  # noqa: N802
                ts = datetime.now().strftime("%H:%M:%S")
                self.chat_body.write(f"[{ts}] {data}")

            # Try to connect; ignore errors (server may not be running)
            await self.sio.connect(self.server_url, transports=["websocket", "polling"], wait=False)
        except Exception as e:  # pragma: no cover
            self.chat_body.write(f"[chat disabled: {e}]")

    async def action_quit(self) -> None:
        try:
            if self.sio is not None:
                await self.sio.disconnect()
        finally:
            await self.shutdown()

    async def action_refresh(self) -> None:
        await self.refresh_all()

    async def on_input_submitted(self, message: Input.Submitted) -> None:
        if message.input is self.chat_input:
            content = (message.value or "").strip()
            if not content:
                return
            self.chat_input.value = ""
            ts = datetime.now().strftime("%H:%M:%S")
            # Echo locally
            self.chat_body.write(f"[{ts}] (you) {content}")
            # Emit to server if connected and the backend listens to this event
            try:
                if self.sio and self._chat_connected:
                    await self.sio.emit("admin_chat", {"text": content})
            except Exception:
                pass
            # Log it in the event log, too
            self.event_log.write(f"chat> {content}")


def run_admin_tui(server_url: Optional[str] = None) -> None:  # pragma: no cover (interactive)
    app = AdminConsole(server_url=server_url)
    app.run()
