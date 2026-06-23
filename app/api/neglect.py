"""/api/neglect — sorted neglect warnings (the dashboard's headline section)."""
from fastapi import APIRouter

from ..neglect import evaluate

router = APIRouter()


@router.get("/neglect")
def neglect():
    warnings = evaluate()
    counts = {"critical": 0, "warning": 0, "info": 0}
    for w in warnings:
        counts[w["severity"]] = counts.get(w["severity"], 0) + 1
    worst = "ok"
    if counts["critical"]:
        worst = "critical"
    elif counts["warning"]:
        worst = "warning"
    elif counts["info"]:
        worst = "info"
    return {"warnings": warnings, "counts": counts, "worst": worst}
