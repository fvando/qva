"""Permite `python -m app` (TASK-001)."""

from __future__ import annotations

import logging

import uvicorn

from app.config import get_settings
from app.tls import ensure_cert, _local_ipv4_addresses

logger = logging.getLogger(__name__)


def main() -> None:
    settings = get_settings()

    kwargs: dict = {
        "host": settings.host,
        "port": settings.port,
        "log_level": settings.log_level.lower(),
    }

    scheme = "http"
    if settings.https:
        certfile, keyfile = ensure_cert(settings.ssl_certfile, settings.ssl_keyfile)
        kwargs["ssl_certfile"] = certfile
        kwargs["ssl_keyfile"] = keyfile
        scheme = "https"

    for ip in _local_ipv4_addresses():
        print(f"  {scheme}://{ip}:{settings.port}/")
    if settings.https:
        print("  (o telemóvel vai avisar do certificado — aceita para continuar)")

    uvicorn.run("app.main:app", **kwargs)


if __name__ == "__main__":
    main()
