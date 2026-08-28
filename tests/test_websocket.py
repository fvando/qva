"""TASK-010 — WebSocketManager e endpoint WS /ws."""

import pytest

from app.websocket_manager import WebSocketManager


class FakeWS:
    def __init__(self, fail_on_send: bool = False) -> None:
        self.accepted = False
        self.sent: list[dict] = []
        self._fail = fail_on_send

    async def accept(self) -> None:
        self.accepted = True

    async def send_json(self, data) -> None:
        if self._fail:
            raise RuntimeError("ligação perdida")
        self.sent.append(data)


async def test_connect_accepts_and_registers():
    m = WebSocketManager()
    ws = FakeWS()
    await m.connect(ws)
    assert ws.accepted is True
    assert m.connection_count == 1


async def test_disconnect_removes():
    m = WebSocketManager()
    ws = FakeWS()
    await m.connect(ws)
    await m.disconnect(ws)
    assert m.connection_count == 0


async def test_broadcast_wraps_event_and_data():
    m = WebSocketManager()
    a, b = FakeWS(), FakeWS()
    await m.connect(a)
    await m.connect(b)
    await m.broadcast("answer_ready", {"x": 1})
    assert a.sent == [{"event": "answer_ready", "data": {"x": 1}}]
    assert b.sent == a.sent


async def test_broadcast_prunes_dead_connections():
    m = WebSocketManager()
    good, bad = FakeWS(), FakeWS(fail_on_send=True)
    await m.connect(good)
    await m.connect(bad)
    await m.broadcast("error", {})
    assert m.connection_count == 1
    assert good.sent  # o bom recebeu na mesma


async def test_broadcast_with_no_connections_is_noop():
    await WebSocketManager().broadcast("capture_started")


# -- endpoint ---------------------------------------------------------------
def test_ws_endpoint_receives_pipeline_events(client):
    """Ligado ao /ws, o cliente recebe os eventos emitidos por uma captura."""
    with client.websocket_connect("/ws") as ws:
        client.post("/api/capture")  # BackgroundTasks corre síncrono depois
        events = []
        for _ in range(3):
            events.append(ws.receive_json()["event"])
    assert events[0] == "capture_started"
    assert "answer_ready" in events
