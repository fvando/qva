"""Geração de certificado TLS self-signed."""

from pathlib import Path

from app.tls import _local_ipv4_addresses, ensure_cert


def test_local_ipv4_includes_loopback():
    assert "127.0.0.1" in _local_ipv4_addresses()


def test_ensure_cert_generates_pair(tmp_path: Path):
    cert = tmp_path / "c.crt"
    key = tmp_path / "c.key"
    c, k = ensure_cert(str(cert), str(key))
    assert Path(c).is_file() and Path(k).is_file()
    assert cert.read_bytes().startswith(b"-----BEGIN CERTIFICATE-----")
    assert b"PRIVATE KEY" in key.read_bytes()


def test_ensure_cert_is_idempotent(tmp_path: Path):
    cert = tmp_path / "c.crt"
    key = tmp_path / "c.key"
    ensure_cert(str(cert), str(key))
    first = cert.read_bytes()
    ensure_cert(str(cert), str(key))  # não regenera
    assert cert.read_bytes() == first


def test_cert_has_san_with_ip(tmp_path: Path):
    from cryptography import x509

    cert = tmp_path / "c.crt"
    key = tmp_path / "c.key"
    ensure_cert(str(cert), str(key))
    parsed = x509.load_pem_x509_certificate(cert.read_bytes())
    san = parsed.extensions.get_extension_for_class(x509.SubjectAlternativeName)
    names = san.value.get_values_for_type(x509.DNSName)
    assert "localhost" in names
