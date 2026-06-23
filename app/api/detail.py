"""/api/detail — generic drill-down. Renders any provider's declared panel."""
from __future__ import annotations

from dataclasses import asdict
from typing import Optional

from fastapi import APIRouter, HTTPException

from ..providers.base import registry

router = APIRouter()


@router.get("/detail/{provider_key}")
async def detail(provider_key: str, day: Optional[str] = None):
    provider = registry.get(provider_key)
    if not provider:
        raise HTTPException(404, "unknown provider")
    result = await provider.fetch_detail(day)
    return {
        "provider": provider_key,
        "color": provider.metrics[0].color if provider.metrics else "slate",
        **asdict(result),
    }
