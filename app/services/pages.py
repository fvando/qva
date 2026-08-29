"""Buffer de páginas para questões que ocupam mais de um ecrã (multi-página).

O operador captura cada página (`POST /api/capture/page`), o servidor processa
o frame e acumula a `ProcessedImage` aqui. Ao carregar em "Resolver"
(`POST /api/capture/solve`) o pipeline recebe todas as páginas e o modelo de
visão junta-as numa só questão.

Em memória, um buffer por processo. As imagens só existem enquanto o buffer
não é resolvido ou limpo.
"""

from __future__ import annotations

import threading

from app.vision.processor import ProcessedImage

# Máximo de páginas por questão — evita acumular sem limite.
_MAX_PAGES = 8


class PageBuffer:
    def __init__(self) -> None:
        self._pages: list[ProcessedImage] = []
        self._lock = threading.Lock()

    @property
    def count(self) -> int:
        with self._lock:
            return len(self._pages)

    def add(self, page: ProcessedImage) -> int:
        """Adiciona uma página. Devolve o total. Levanta se exceder o limite."""
        with self._lock:
            if len(self._pages) >= _MAX_PAGES:
                raise ValueError(f"máximo de {_MAX_PAGES} páginas por questão")
            self._pages.append(page)
            return len(self._pages)

    def take_all(self) -> list[ProcessedImage]:
        """Devolve todas as páginas e esvazia o buffer."""
        with self._lock:
            pages, self._pages = self._pages, []
            return pages

    def clear(self) -> None:
        with self._lock:
            self._pages = []
