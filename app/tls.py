"""Certificado TLS self-signed para servir o QVA por HTTPS na LAN.

A câmera do browser (`getUserMedia`) só funciona em `localhost` ou HTTPS — para
usar o telemóvel como câmera via `http://<ip>:8080` o browser bloqueia. Com
HTTPS (mesmo self-signed) já funciona: o telemóvel mostra um aviso de
"certificado não confiável" que aceitas uma vez.

`ensure_cert()` gera o par certificado/chave se não existir, com um SAN que
cobre `localhost`, `127.0.0.1` e os IPs IPv4 desta máquina.
"""

from __future__ import annotations

import datetime as dt
import ipaddress
import logging
import socket
from pathlib import Path

logger = logging.getLogger(__name__)


def _local_ipv4_addresses() -> list[str]:
    addrs: set[str] = {"127.0.0.1"}
    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
            addrs.add(info[4][0])
    except OSError:
        pass
    # também a rota de saída (IP na LAN, mesmo sem DNS do hostname)
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        addrs.add(s.getsockname()[0])
        s.close()
    except OSError:
        pass
    return sorted(addrs)


def ensure_cert(certfile: str, keyfile: str) -> tuple[str, str]:
    """Garante que existe um par cert/chave válido. Devolve (certfile, keyfile)."""
    cert_path = Path(certfile)
    key_path = Path(keyfile)
    if cert_path.is_file() and key_path.is_file():
        return str(cert_path), str(key_path)

    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    cert_path.parent.mkdir(parents=True, exist_ok=True)

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "qva.local")])

    san_entries: list[x509.GeneralName] = [x509.DNSName("localhost")]
    for ip in _local_ipv4_addresses():
        try:
            san_entries.append(x509.IPAddress(ipaddress.ip_address(ip)))
        except ValueError:
            continue

    now = dt.datetime.now(dt.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - dt.timedelta(days=1))
        .not_valid_after(now + dt.timedelta(days=3650))
        .add_extension(x509.SubjectAlternativeName(san_entries), critical=False)
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )

    key_path.write_bytes(
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    logger.info(
        "TLS_CERT_GENERATED",
        extra={"model": ",".join(_local_ipv4_addresses())},
    )
    return str(cert_path), str(key_path)
