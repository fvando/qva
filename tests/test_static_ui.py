"""TASK-011 — a interface mobile é servida."""


def test_index_served(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "Question Vision Assistant" in r.text
    assert 'id="capture"' in r.text


def test_assets_served(client):
    for path in ("/app.js", "/styles.css", "/manifest.webmanifest"):
        assert client.get(path).status_code == 200


def test_index_has_all_status_dots(client):
    html = client.get("/").text
    for service in ("camera", "llm", "server"):
        assert f'data-service="{service}"' in html
