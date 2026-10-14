"""A stand-in for the SukaRise bot gateway, served over real websockets in tests.

It speaks the protocol of ``internal/botapi/wire.go``: a SessionMetadata first,
then one answer per request that carries a ``rid``. Tests script its behaviour:
refuse a handshake, drop a connection, refuse a request, or go silent.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field

from aiohttp import WSMsgType, web


@dataclass(slots=True)
class Handshake:
    api_token: str
    room_id: str
    query: str


@dataclass(slots=True)
class FakeGateway:
    handshakes: list[Handshake] = field(default_factory=list[Handshake])
    requests: list[dict[str, object]] = field(default_factory=list[dict[str, object]])
    sockets: list[web.WebSocketResponse] = field(default_factory=list[web.WebSocketResponse])
    connections: int = 0
    rate_limits: dict[str, list[float]] = field(default_factory=dict[str, list[float]])
    room_content: list[object] = field(default_factory=list[object])
    # HTTP status returned instead of a websocket upgrade (for example 401).
    refuse_status: int | None = None
    # Error frame sent instead of SessionMetadata, after the upgrade.
    refuse_frame: dict[str, object] | None = None
    # Refuse only the first connection with ``refuse_frame``; later ones are accepted.
    refuse_first_only: bool = False
    # Request type -> refusal message: that request gets an Error with its rid.
    error_for: dict[str, str] = field(default_factory=dict[str, str])
    # Close the first connection right after its session, to force a reconnect.
    drop_first_connection: bool = False
    # Keep the first connection open but send and answer nothing after its session: a host
    # that vanished without a reset.
    freeze_first_connection: bool = False
    # Never answer a request (to test timeouts).
    silent: bool = False

    def app(self) -> web.Application:
        application = web.Application()
        application.router.add_get("/web/botapi", self._socket)
        return application

    async def push(self, frame: dict[str, object]) -> None:
        """Send an event frame to every open connection."""
        for ws in list(self.sockets):
            if not ws.closed:
                await ws.send_str(json.dumps(frame))

    def _session_frame(self) -> dict[str, object]:
        return {
            "_type": "SessionMetadata",
            "user_id": "bot-1",
            "room_info": {"owner_id": "owner-1", "room_name": "Test room"},
            "rate_limits": self.rate_limits,
            "connection_id": f"connection-{self.connections}",
            "sdk_version": None,
        }

    async def _socket(self, request: web.Request) -> web.StreamResponse:
        self.connections += 1
        self.handshakes.append(
            Handshake(
                api_token=request.headers.get("api-token", ""),
                room_id=request.headers.get("room-id", ""),
                query=request.query_string,
            )
        )
        if self.refuse_status is not None:
            return web.Response(status=self.refuse_status)
        ws = web.WebSocketResponse(heartbeat=None)
        await ws.prepare(request)
        if self.refuse_frame is not None and (not self.refuse_first_only or self.connections == 1):
            await ws.send_str(json.dumps(self.refuse_frame))
            await ws.close()
            return ws
        await ws.send_str(json.dumps(self._session_frame()))
        self.sockets.append(ws)
        if self.drop_first_connection and self.connections == 1:
            await ws.close()
            return ws
        if self.freeze_first_connection and self.connections == 1:
            await asyncio.sleep(3600)
            return ws
        async for message in ws:
            if message.type is not WSMsgType.TEXT:
                continue
            frame = json.loads(message.data)
            self.requests.append(frame)
            await self._answer(ws, frame)
        return ws

    async def _answer(self, ws: web.WebSocketResponse, frame: dict[str, object]) -> None:
        kind = frame.get("_type")
        rid = frame.get("rid")
        if kind == "KeepaliveRequest":
            # The real gateway answers every keepalive; the SDK counts any inbound frame as life.
            await ws.send_str(json.dumps({"_type": "KeepaliveResponse"}))
            return
        if not isinstance(kind, str) or rid is None or self.silent:
            return
        if kind in self.error_for:
            await ws.send_str(json.dumps({"_type": "Error", "message": self.error_for[kind], "rid": rid}))
            return
        response: dict[str, object] = {"_type": kind.removesuffix("Request") + "Response", "rid": rid}
        if kind == "GetRoomUsersRequest":
            response["content"] = self.room_content
        if kind == "GetWalletRequest":
            response["content"] = [{"type": "gold", "amount": 42}]
        await ws.send_str(json.dumps(response))
