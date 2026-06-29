"""API routers, aggregated into one router mounted at /api."""
from fastapi import APIRouter

from . import cards, detail, heatmaps, neglect, protein, rituals, summary, timeline

# NOTE: manual-entry endpoints (entries.router) are intentionally NOT mounted.
# Devansh OS is an observability dashboard, not an editor — data comes from
# real sources (GitHub, LeetCode, Claude), never hand-typed.

api_router = APIRouter(prefix="/api")
api_router.include_router(summary.router)
api_router.include_router(heatmaps.router)
api_router.include_router(cards.router)
api_router.include_router(neglect.router)
api_router.include_router(timeline.router)
api_router.include_router(detail.router)
api_router.include_router(protein.router)
api_router.include_router(rituals.router)
