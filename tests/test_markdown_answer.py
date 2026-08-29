"""Explicação em Markdown — servida e usada nas duas páginas."""


def test_md_js_served(client):
    assert client.get("/md.js").status_code == 200


def test_pages_load_md(client):
    for path in ("/", "/answer"):
        html = client.get(path).text
        assert 'src="/md.js"' in html


def test_answer_js_renders_markdown(client):
    assert "renderMarkdown" in client.get("/answer.js").text


def test_app_js_renders_markdown(client):
    assert "renderMarkdown" in client.get("/app.js").text


def test_prompt_asks_for_markdown_explanation():
    from app.llm.prompts import COMBINED_SYSTEM, SOLVE_SYSTEM

    for p in (COMBINED_SYSTEM, SOLVE_SYSTEM):
        assert "Markdown" in p
        assert "tabela" in p.lower()  # menciona tabelas (Karnaugh / verdade)


def test_md_js_has_table_and_code_support(client):
    js = client.get("/md.js").text
    assert "md-table-wrap" in js
    assert "<pre><code>" in js
    # escapa HTML antes de tudo
    assert 'replace(/</g, "&lt;")' in js
