"""TASK-011 — a interface mobile é servida."""


def test_index_served(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "Question Vision Assistant" in r.text
    assert 'id="capture"' in r.text


def test_assets_served(client):
    for path in (
        "/app.js",
        "/styles.css",
        "/manifest.webmanifest",
        "/sw.js",
        "/icon-192.png",
        "/icon-512.png",
        "/icon-maskable-512.png",
    ):
        assert client.get(path).status_code == 200, path


def test_manifest_has_icons(client):
    import json

    m = json.loads(client.get("/manifest.webmanifest").text)
    assert len(m["icons"]) >= 2
    assert any(i.get("purpose") == "maskable" for i in m["icons"])


def test_sw_does_not_cache_api(client):
    sw = client.get("/sw.js").text
    assert "/api/" in sw and "return; // deixa passar" in sw


def test_index_registers_service_worker(client):
    assert 'serviceWorker.register("/sw.js")' in client.get("/app.js").text


def test_index_has_all_status_dots(client):
    html = client.get("/").text
    for service in ("camera", "llm", "server"):
        assert f'data-service="{service}"' in html
