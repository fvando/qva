"""Endpoints de histórico (secção 19). Opcional no MVP (`STORE_HISTORY`)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.dependencies import get_history
from app.history import HistoryStore

router = APIRouter(prefix="/api/history", tags=["history"])


@router.get("")
async def list_history(store: HistoryStore = Depends(get_history)) -> list[dict]:
    return store.list()


@router.get("/{entry_id}")
async def get_history_entry(
    entry_id: str, store: HistoryStore = Depends(get_history)
) -> dict:
    entry = store.get(entry_id)
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="não encontrado")
    return entry


@router.delete("/{entry_id}")
async def delete_history_entry(
    entry_id: str, store: HistoryStore = Depends(get_history)
) -> Response:
    if not store.delete(entry_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="não encontrado")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
