"""Neglect-detection engine — the most prominent feature.

The rule evaluation itself now lives in Postgres (fn_neglect_evaluate(), see
supabase/migrations/*_compute_layer.sql), reading the neglect_rule_specs table
that FastAPI mirrors from each provider's declared Rule list on startup
(db.sync_metric_catalog()). This keeps the result identical and available to
any client (FastAPI or Flutter) without this process running; this module is
now a one-query wrapper so callers (api/neglect.py) don't need to change.
"""
from __future__ import annotations

from .db import query


def evaluate() -> list[dict]:
    return query(
        """
        SELECT * FROM fn_neglect_evaluate()
        ORDER BY CASE severity WHEN 'critical' THEN 0 WHEN 'warning' THEN 1 ELSE 2 END,
                 COALESCE(value, 0) DESC
        """
    )
