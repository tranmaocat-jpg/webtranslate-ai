import pytest
from unittest.mock import patch
from fastapi import HTTPException
from app.main import validate_url, split_bytes, translate_document

def public_dns(*args, **kwargs):
    return [(None, None, None, None, ("93.184.216.34", 443))]

def private_dns(*args, **kwargs):
    return [(None, None, None, None, ("127.0.0.1", 443))]

def assert_http_error(url, code):
    with pytest.raises(HTTPException) as exc:
        validate_url(url)
    assert exc.value.status_code == code

def test_reject_localhost():
    assert_http_error("http://localhost/", 403)

def test_reject_file_scheme():
    assert_http_error("file:///etc/passwd", 400)

def test_reject_private_dns():
    with patch("app.main.socket.getaddrinfo", private_dns):
        assert_http_error("https://private.example/", 403)

def test_accept_public_host_when_dns_is_public():
    with patch("app.main.socket.getaddrinfo", public_dns):
        assert validate_url("https://public.example/") == "https://public.example/"

def test_reject_credentials_in_url():
    assert_http_error("https://user:secret@example.com/", 400)

def test_reject_unsupported_port():
    assert_http_error("https://example.com:8080/", 400)

def test_reject_invalid_port_syntax():
    assert_http_error("https://example.com:abc/", 400)

def test_split_chunks_respect_utf8_byte_limit():
    parts = split_bytes("Vietnamese text dài " * 60, limit=120)
    assert parts
    assert all(len(part.encode("utf-8")) <= 120 for part in parts)

@pytest.mark.asyncio
async def test_document_preserves_markup_and_external_links(monkeypatch):
    async def fake_translate(text, source, target):
        return f"VI:{text.strip()}"
    monkeypatch.setattr("app.main.translate_text", fake_translate)
    html = '<html><head><title>Title</title></head><body><h1>Hello</h1><a href="/inside">Internal</a><a href="https://other.example/">External</a><img src="/img.png" alt="Photo"><script>alert(1)</script></body></html>'
    out = await translate_document(html, "https://site.example/page", "en", "vi")
    assert "<h1>VI:Hello</h1>" in out
    assert "/translate?url=https%3A%2F%2Fsite.example%2Finside" in out
    assert 'href="https://other.example/"' in out
    assert 'src="https://site.example/img.png"' in out
    assert "VI:Photo" in out
    assert "<script" not in out
