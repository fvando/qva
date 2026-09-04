"""Captura de questões com várias páginas."""

import cv2
import numpy as np
import pytest

from app.llm.base import LLMRequest
from app.services.pages import PageBuffer
from app.vision.processor import ProcessedImage


def _jpeg(text="pagina"):
    img = np.full((200, 300, 3), 240, dtype=np.uint8)
    cv2.putText(img, text, (10, 100), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 0), 2)
    return cv2.imencode(".jpg", img)[1].tobytes()


# -- PageBuffer -------------------------------------------------------
def test_buffer_add_and_take():
    b = PageBuffer()
    assert b.count == 0
    b.add(ProcessedImage(image=np.zeros((4, 4, 3), dtype=np.uint8)))
    b.add(ProcessedImage(image=np.zeros((4, 4, 3), dtype=np.uint8)))
    assert b.count == 2
    taken = b.take_all()
    assert len(taken) == 2
    assert b.count == 0  # esvaziou


def test_buffer_limit():
    b = PageBuffer()
    for _ in range(8):
        b.add(ProcessedImage(image=np.zeros((2, 2, 3), dtype=np.uint8)))
    with pytest.raises(ValueError):
        b.add(ProcessedImage(image=np.zeros((2, 2, 3), dtype=np.uint8)))


# -- LLMRequest: várias imagens -------------------------------------
def test_llm_request_all_images():
    assert LLMRequest(image_b64="a").all_images == ["a"]
    assert LLMRequest(images_b64=["a", "b"]).all_images == ["a", "b"]
    assert LLMRequest(images_b64=["a"], image_b64="ignorado").all_images == ["a"]
    assert LLMRequest().all_images == []


# -- endpoints -------------------------------------------------------
def test_add_page_from_uploaded_frame(client):
    r = client.post(
        "/api/capture/page",
        content=_jpeg("Questao 3 parte 1"),
        headers={"Content-Type": "image/jpeg"},
    )
    assert r.status_code == 200
    assert r.json()["pages"] == 1

    r = client.post(
        "/api/capture/page",
        content=_jpeg("continua na parte 2"),
        headers={"Content-Type": "image/jpeg"},
    )
    assert r.json()["pages"] == 2

    assert client.get("/api/capture/pages").json()["pages"] == 2


def test_clear_pages(client):
    client.post("/api/capture/page", content=_jpeg(), headers={"Content-Type": "image/jpeg"})
    assert client.get("/api/capture/pages").json()["pages"] == 1
    assert client.delete("/api/capture/pages").status_code == 204
    assert client.get("/api/capture/pages").json()["pages"] == 0


def test_solve_without_pages_is_400(client):
    client.delete("/api/capture/pages")
    assert client.post("/api/capture/solve").status_code == 400


def test_solve_pages_runs_pipeline(client):
    client.post("/api/capture/page", content=_jpeg("p1"), headers={"Content-Type": "image/jpeg"})
    client.post("/api/capture/page", content=_jpeg("p2"), headers={"Content-Type": "image/jpeg"})
    r = client.post("/api/capture/solve")
    assert r.status_code == 202
    cid = r.json()["capture_id"]

    body = client.get("/api/capture/" + cid).json()
    assert body["id"] == cid
    # FakeLLM devolve a questão LIFO -> B
    assert body["status"] in ("completed", "error")
    # o buffer foi esvaziado
    assert client.get("/api/capture/pages").json()["pages"] == 0


def test_simple_capture_clears_pending_pages(client):
    client.post("/api/capture/page", content=_jpeg(), headers={"Content-Type": "image/jpeg"})
    client.post("/api/capture")  # captura simples
    assert client.get("/api/capture/pages").json()["pages"] == 0
