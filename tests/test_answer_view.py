"""App de consulta (/answer) + reenvio da última resposta."""

from app.models.question import Question, QuestionType
from app.models.result import ConsolidatedResponse, SolveResult, Timing
from app.websocket_manager import WebSocketManager


class FakeWS:
    def __init__(self):
        self.accepted = False
        self.sent = []

    async def accept(self):
        self.accepted = True

    async def send_json(self, data):
        self.sent.append(data)


def _answer_msg():
    return ConsolidatedResponse(
        id="x",
        status="completed",
        question=Question(type=QuestionType.MULTIPLE_CHOICE, question="?"),
        result=SolveResult(answer="B", confidence=0.9),
        timing=Timing(total_ms=1000),
    )


# -- página --------------------------------------------------------
def test_answer_page_served(client):
    r = client.get("/answer")
    assert r.status_code == 200
    assert "QVA" in r.text
    assert 'src="/answer.js"' in r.text


def test_answer_js_only_receives(client):
    js = client.get("/answer.js").text
    # não deve ter nada de captura/câmera — só consulta
    assert "/api/capture" not in js
    assert "getUserMedia" not in js
    assert "WebSocket" in js


def test_answer_is_chat_feed(client):
    html = client.get("/answer").text
    assert 'id="feed"' in html
    assert 'id="tpl-msg"' in html  # template de mensagem
    js = client.get("/answer.js").text
    assert "seen" in js  # dedup por id — não repete a última ao reconectar
    assert "addAnswer" in js


# -- reenvio da última resposta -----------------------------------
async def test_new_connection_gets_last_result():
    m = WebSocketManager()
    await m.broadcast("answer_ready", {"response": _answer_msg().model_dump(mode="json")})

    late = FakeWS()
    await m.connect(late)
    assert late.sent  # recebeu logo o último resultado
    assert late.sent[0]["event"] == "answer_ready"


async def test_connection_without_prior_result_gets_nothing():
    m = WebSocketManager()
    ws = FakeWS()
    await m.connect(ws)
    assert ws.sent == []


async def test_intermediate_events_are_not_sticky():
    m = WebSocketManager()
    await m.broadcast("capture_started", {})
    await m.broadcast("question_detected", {"question": {}})

    late = FakeWS()
    await m.connect(late)
    assert late.sent == []  # só answer_ready/error são reenviados


async def test_resend_last_broadcasts_to_all():
    m = WebSocketManager()
    a, b = FakeWS(), FakeWS()
    await m.connect(a)
    await m.connect(b)
    await m.broadcast("answer_ready", {"response": {}})
    a.sent.clear()
    b.sent.clear()

    assert await m.resend_last() is True
    assert a.sent and b.sent


async def test_resend_last_false_when_no_result():
    assert await WebSocketManager().resend_last() is False


def test_resend_endpoint(client):
    r = client.post("/api/answer/resend")
    assert r.status_code == 200
    assert "resent" in r.json()
