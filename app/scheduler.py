"""Background polling. Periodically syncs every non-manual, enabled provider."""
from __future__ import annotations

import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from .config import get_settings
from .providers.base import registry

log = logging.getLogger("devansh.scheduler")
_scheduler: AsyncIOScheduler | None = None


async def sync_all_providers() -> None:
    for provider in registry.enabled():
        if provider.manual:
            continue
        await provider.sync()


def start_scheduler() -> AsyncIOScheduler:
    global _scheduler
    settings = get_settings()
    _scheduler = AsyncIOScheduler(timezone=str(settings.tz))
    _scheduler.add_job(
        sync_all_providers,
        "interval",
        minutes=max(1, settings.poll_minutes),
        id="poll_providers",
        max_instances=1,
        coalesce=True,
    )
    _scheduler.start()
    # Kick an immediate sync so the dashboard has data on first load.
    asyncio.create_task(sync_all_providers())
    log.info("scheduler started: every %d min", settings.poll_minutes)
    return _scheduler


def shutdown_scheduler() -> None:
    if _scheduler:
        _scheduler.shutdown(wait=False)
