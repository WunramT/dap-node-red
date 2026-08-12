"""
Socket.IO server configuration and event management.

Provides real-time WebSocket communication for warehouse dashboard updates.
Clients join warehouse rooms and receive data_changed events when backend
operations modify relevant data.
"""

import asyncio
from uuid import UUID
from typing import Optional

import socketio

from app.core.logging import get_logger
from app.config import settings

logger = get_logger(__name__)

# Global Socket.IO async server instance
_sio: Optional[socketio.AsyncServer] = None
_socket_manager: Optional["SocketManager"] = None


class SocketManager:
    """
    Manages Socket.IO server, rooms, and event broadcasting.

    Thread-safe event ID generation per warehouse. Event IDs allow clients
    to detect missed events during disconnection and decide whether to refresh.
    """

    def __init__(self, sio: socketio.AsyncServer):
        self.sio = sio
        self._event_counters: dict[str, int] = {}
        self._counter_lock = asyncio.Lock()
        self._register_handlers()

    def _register_handlers(self):
        """Register Socket.IO event handlers."""

        @self.sio.on("connect")
        async def handle_connect(sid, environ, auth):
            logger.info(f"Socket client connected: {sid}")
            await self.sio.emit(
                "message",
                {"message": f"Hello from {settings.app_name}!"},
                room=sid,  # Send only to the connecting client
            )

        @self.sio.on("disconnect")
        async def handle_disconnect(sid):
            logger.info(f"Socket client disconnected: {sid}")

        @self.sio.on("join_warehouse")
        async def handle_join_warehouse(sid, data):
            """
            Client joins a warehouse room. Returns current event_id.

            Expected data: {"warehouse_id": "uuid-string"}
            Response: {"event_id": int, "warehouse_id": "uuid-string"}
            """
            try:
                warehouse_id = UUID(data.get("warehouse_id"))
                room = f"warehouse:{warehouse_id}"

                await self.sio.enter_room(sid, room)

                event_id = await self.get_latest_event_id(warehouse_id)
                await self.sio.emit(
                    "joined",
                    {"event_id": event_id, "warehouse_id": str(warehouse_id)},
                    room=sid,
                )

                logger.info(f"Socket client {sid} joined {room}, event_id={event_id}")

            except (ValueError, TypeError) as e:
                logger.error(f"Invalid join_warehouse from {sid}: {data}, error: {e}")
                await self.sio.emit(
                    "error",
                    {"message": "Invalid warehouse_id"},
                    room=sid,
                )

    async def get_next_event_id(self, warehouse_id: UUID) -> int:
        """Get next event ID for a warehouse (thread-safe)."""
        async with self._counter_lock:
            key = str(warehouse_id)
            self._event_counters[key] = self._event_counters.get(key, 0) + 1
            return self._event_counters[key]

    async def get_latest_event_id(self, warehouse_id: UUID) -> int:
        """Get current event ID for a warehouse."""
        async with self._counter_lock:
            return self._event_counters.get(str(warehouse_id), 0)

    async def emit_data_changed(self, warehouse_id: UUID, change_type: str) -> None:
        """
        Emit a data_changed event to all clients in a warehouse room.

        Args:
            warehouse_id: Target warehouse UUID
            change_type: One of:
                - request_created: Operator created request(s)
                - pick_list_created: Pick list created (requests locked)
                - pick_list_status_changed: Pick list status advanced
                - request_status_changed: Request status updated
        """
        room = f"warehouse:{warehouse_id}"
        event_id = await self.get_next_event_id(warehouse_id)

        payload = {
            "event_id": event_id,
            "warehouse_id": str(warehouse_id),
            "change_type": change_type,
        }

        logger.debug(f"Emitting data_changed to {room}: {payload}")
        await self.sio.emit("data_changed", payload, room=room)


def init_socketio() -> socketio.AsyncServer:
    """Initialize and configure the Socket.IO async server."""
    global _sio

    if _sio is not None:
        return _sio

    logger.info("Initializing Socket.IO server")

    _sio = socketio.AsyncServer(
        async_mode="asgi",
        cors_allowed_origins="*",
        logger=False,
        engineio_logger=False,
    )

    logger.info("Socket.IO server initialized successfully")
    return _sio


def get_socket_manager() -> SocketManager:
    """Get or create the singleton SocketManager instance."""
    global _socket_manager

    if _socket_manager is None:
        sio = init_socketio()
        _socket_manager = SocketManager(sio)

    return _socket_manager
