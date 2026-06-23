"""/api/entry — fast keyboard-driven manual entry.

Routes a single line (``g`` / ``s 7.5`` / ``d 3`` / ``s 7 -1``) to the manual
provider whose ``trigger`` matches the first token. The second numeric token is
the value (for sleep/deep work); a trailing ``-N``, ``yesterday`` or ``today``
back-dates the entry.
"""
from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .. import aggregates as agg
from ..providers.base import registry
from ..providers.manual import ManualProvider

router = APIRouter()


class EntryIn(BaseModel):
    cmd: str


def _manual_providers() -> dict[str, ManualProvider]:
    return {
        p.trigger: p
        for p in registry.all()
        if isinstance(p, ManualProvider) and p.trigger
    }


@router.get("/commands")
def commands():
    out = []
    for p in _manual_providers().values():
        example = f"{p.trigger} 7.5" if p.takes_value else p.trigger
        out.append({
            "trigger": p.trigger,
            "provider": p.key,
            "label": p.display_name,
            "takes_value": p.takes_value,
            "unit": p.metrics[0].unit if p.metrics else "",
            "example": example,
        })
    return {"commands": sorted(out, key=lambda c: c["trigger"])}


@router.post("/entry")
def entry(body: EntryIn):
    tokens = body.cmd.strip().split()
    if not tokens:
        raise HTTPException(400, "empty command")

    provider = _manual_providers().get(tokens[0].lower())
    if not provider:
        raise HTTPException(400, f"unknown command '{tokens[0]}'")

    value: float | None = None
    offset = 0
    for tok in tokens[1:]:
        low = tok.lower()
        if low == "yesterday":
            offset = 1
        elif low == "today":
            offset = 0
        elif low.lstrip("-").isdigit() and low.startswith("-"):
            offset = abs(int(low))
        else:
            try:
                value = float(tok)
            except ValueError:
                raise HTTPException(400, f"could not parse '{tok}'")

    if provider.takes_value and value is None:
        raise HTTPException(400, f"'{provider.trigger}' needs a value, e.g. "
                                 f"'{provider.trigger} 7.5'")

    day = (agg.today() - timedelta(days=offset)).strftime("%Y-%m-%d")
    result = provider.apply_entry(value, day)
    result["title"] = provider.event_title(result["value"])
    result["current_streak"] = agg.current_streak(provider.key, result["metric"])
    return {"ok": True, "entry": result}
