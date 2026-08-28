"""TASK-014 — HistoryStore e endpoints /api/history."""

from app.history import HistoryStore
from app.models.question import Question, QuestionType
from app.models.result import ConsolidatedResponse, SolveResult, Timing


def _completed(id_: str) -> ConsolidatedResponse:
    return ConsolidatedResponse(
        id=id_,
        status="completed",
        question=Question(type=QuestionType.MULTIPLE_CHOICE, question="?"),
        result=SolveResult(answer="B", confidence=0.9),
        timing=Timing(total_ms=1234),
    )


def test_saves_only_completed():
    s = HistoryStore()
    s.save(_completed("a"))
    s.save(ConsolidatedResponse(id="b", status="error", error="x"))
    entries = s.list()
    assert [e["id"] for e in entries] == ["a"]


def test_never_stores_images():
    s = HistoryStore()
    s.save(_completed("a"))
    entry = s.list()[0]
    assert set(entry) == {"id", "created_at", "question", "result", "timing"}


def test_disabled_store_is_noop():
    s = HistoryStore(enabled=False)
    s.save(_completed("a"))
    assert s.list() == []


def test_get_and_delete():
    s = HistoryStore()
    s.save(_completed("a"))
    assert s.get("a")["id"] == "a"
    assert s.delete("a") is True
    assert s.get("a") is None
    assert s.delete("a") is False


def test_newest_first_and_bounded():
    s = HistoryStore()
    for i in range(150):
        s.save(_completed(str(i)))
    entries = s.list()
    assert entries[0]["id"] == "149"
    assert len(entries) == 100


# -- endpoints --------------------------------------------------------
def test_history_endpoints_flow(client):
    assert client.get("/api/history").json() == []

    client.post("/api/capture")  # completa com FakeCamera + FakeLLM

    listing = client.get("/api/history").json()
    assert len(listing) == 1
    entry_id = listing[0]["id"]

    assert client.get(f"/api/history/{entry_id}").status_code == 200
    assert client.get("/api/history/inexistente").status_code == 404
    assert client.delete(f"/api/history/{entry_id}").status_code == 204
    assert client.get("/api/history").json() == []
