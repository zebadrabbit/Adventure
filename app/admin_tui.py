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

try:
    # Textual >= 0.50 uses Log
    from textual.widgets import Footer, Header, Input, Log, Static
except Exception:  # pragma: no cover
    # Older Textual used TextLog; alias it for compatibility
    from textual.widgets import Footer, Header, Input, Static  # type: ignore
    from textual.widgets import TextLog as Log
from textual.containers import Horizontal, Vertical

# Optional Socket.IO client for chat/events
try:
    import socketio  # type: ignore
except Exception:  # pragma: no cover
    socketio = None

from app import app as flask_app
from app import db
from app.models.dungeon_instance import DungeonInstance
from app.models.models import User


class AdminConsole(App):
    """Interactive Textual admin console.

    Provides a lightweight operational view into the running game server:
      * Users panel – lists registered users (future: online state).
      * Dungeon Seeds – shows active dungeon instances with user positions.
      * Chat – optional Socket.IO chat relay if the server is reachable.
      * Event Log – tail of internal application events (login/logout, etc.).

    The console periodically refreshes panels on a 5 second cadence and keeps
    a background Socket.IO client (if available) to receive real-time chat and
    event messages. All heavy DB queries run in a thread via ``asyncio.to_thread``
    to avoid blocking the UI loop.
    """

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
        # Socket.IO async client (created lazily if library available)
        self.sio = None  # type: ignore[assignment]
        self._chat_connected = False

    def compose(self) -> ComposeResult:  # type: ignore[override]
        yield Header(show_clock=True)
        with Vertical(classes="top-row"):
            with Horizontal():
                with Vertical(id="users-panel", classes="panel"):
                    yield Static("Users Online", classes="panel-title")
                    self.users_body = Log()
                    yield self.users_body
                with Vertical(id="seeds-panel", classes="panel"):
                    yield Static("Dungeon Seeds", classes="panel-title")
                    self.seeds_body = Log()
                    yield self.seeds_body
                with Vertical(id="chat-panel", classes="panel"):
                    yield Static("Chat (Socket.IO)", classes="panel-title")
                    self.chat_body = Log()
                    self.chat_input = Input(placeholder="Type message and press Enter…")
                    yield self.chat_body
                    yield self.chat_input
        with Vertical(id="log-panel", classes="panel bottom-row"):
            yield Static("Event Log", classes="panel-title")
            self.event_log = Log()
            yield self.event_log
        yield Footer()

    async def on_mount(self) -> None:  # type: ignore[override]
        """Lifecycle hook: schedule periodic refresh & chat connection tasks."""
        self.call_after_refresh(self.refresh_all)
        self._refresh_task = asyncio.create_task(self._periodic_refresh())
        self._chat_task = asyncio.create_task(self._chat_connect())

    async def _periodic_refresh(self) -> None:
        """Loop performing panel refreshes until the app exits."""
        while True:
            await self.refresh_all()
            await asyncio.sleep(5.0)

    async def refresh_all(self) -> None:
        """Refresh all dynamic panels concurrently."""
        await asyncio.gather(self.refresh_users(), self.refresh_seeds())

    async def refresh_users(self) -> None:
        """Update the Users panel with current registered users.

        Notes:
            Online/offline distinction is not yet implemented; future versions
            may integrate with websocket presence tracking.
        """

        def _query():
            with flask_app.app_context():
                rows = User.query.order_by(User.username.asc()).all()
                return [f"- {u.username} [{getattr(u,'role','user')}]" for u in rows]

        lines = await asyncio.to_thread(_query)
        self.users_body.clear()
        if lines:
            for ln in lines:
                self.users_body.write_line(ln)
        else:
            self.users_body.write_line("(no users)")

    async def refresh_seeds(self) -> None:
        """Update the Dungeon Seeds panel with instance summaries."""

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
                self.seeds_body.write_line(ln)
        else:
            self.seeds_body.write_line("(no seeds)")

    async def _chat_connect(self) -> None:
        if socketio is None:
            self.chat_body.write_line("python-socketio not available; chat disabled.")
            return
        try:
            self.sio = socketio.AsyncClient()

            @self.sio.event
            async def connect():
                self._chat_connected = True
                self.chat_body.write_line(f"[connected to {self.server_url}]")

            @self.sio.event
            async def disconnect():
                self._chat_connected = False
                self.chat_body.write_line("[disconnected]")

            @self.sio.on("chat_message")
            async def _on_chat_message(data):  # noqa: N802
                ts = datetime.now().strftime("%H:%M:%S")
                self.chat_body.write_line(f"[{ts}] {data}")

            # Try to connect; ignore errors (server may not be running)
            await self.sio.connect(self.server_url, transports=["websocket", "polling"], wait=False)
        except Exception as e:  # pragma: no cover
            self.chat_body.write_line(f"[chat disabled: {e}]")

    async def action_quit(self) -> None:
        try:
            if self.sio is not None:
                await self.sio.disconnect()
        finally:
            await self.shutdown()

    async def action_refresh(self) -> None:
        await self.refresh_all()

    async def on_input_submitted(self, message: Input.Submitted) -> None:  # type: ignore[override]
        if message.input is self.chat_input:
            content = (message.value or "").strip()
            if not content:
                return
            self.chat_input.value = ""
            ts = datetime.now().strftime("%H:%M:%S")
            # Echo locally
            self.chat_body.write_line(f"[{ts}] (you) {content}")
            # Emit to server if connected and the backend listens to this event
            try:
                if self.sio and self._chat_connected:
                    await self.sio.emit("admin_chat", {"text": content})
            except Exception:
                pass
            # Log it in the event log, too
            self.event_log.write_line(f"chat> {content}")


def run_admin_tui(
    server_url: Optional[str] = None,
) -> None:  # pragma: no cover (interactive)
    app = AdminConsole(server_url=server_url)
    app.run()
