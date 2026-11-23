import pytest
from unittest.mock import patch
from fastapi import HTTPException
from app.main import validate_url, split_bytes

def public_dns(*args, **kwargs):
    return [(None, None, None, None, ("93.184.216.34", 443))]

def private_dns(*args, **kwargs):
    return [(None, None, None, None, ("127.0.0.1", 443))]

def test_reject_localhost():
    with pytest.raises(HTTPException) as exc:
        validate_url("http://localhost/")
    assert exc.value.status_code == 403

def test_reject_file_scheme():
    with pytest.raises(HTTPException) as exc:
        validate_url("file:///etc/passwd")
    assert exc.value.status_code == 400

def test_reject_private_dns():
    with patch("app.main.socket.getaddrinfo", private_dns):
        with pytest.raises(HTTPException) as exc:
            validate_url("https://private.example/")
    assert exc.value.status_code == 403

def test_accept_public_host_when_dns_is_public():
    with patch("app.main.socket.getaddrinfo", public_dns):
        assert validate_url("https://public.example/") == "https://public.example/"

def test_chunks_under_limit_utf8():
    parts = split_bytes("Vietnamese text dài " * 60, limit=120)
    assert parts
    assert all(len(p.encode("utf-8")) <= 120 for p in parts)
