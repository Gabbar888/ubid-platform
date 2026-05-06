"""Cadence-aware exponential decay for activity signals.

Formula (from proposal):
    cT(Δt) = wT · exp( −Δt / (α · τT) )

Where:
    wT         = per-signal weight (continuity strength)
    Δt         = days since the event
    α          = forgiveness factor (configurable; default 1.5)
    τT         = expected cadence in days

For event-driven signals (τT is None), we use a default decay window of 365 days.
"""
from __future__ import annotations
import math
from datetime import date
from typing import Optional

from ubid.activity.signal_catalog import SignalConfig

DEFAULT_CADENCE_DAYS = 365


def contribution(
    config: SignalConfig,
    event_date: date,
    reference_date: date,
    alpha: float = 1.5,
) -> float:
    """Compute the decayed contribution of a single event."""
    if config.terminal:
        return config.weight  # terminal signals don't decay

    delta_t = (reference_date - event_date).days
    if delta_t < 0:
        delta_t = 0  # future events (clock skew) treated as today

    tau = config.cadence_days or DEFAULT_CADENCE_DAYS
    decay = math.exp(-delta_t / (alpha * tau))
    return config.weight * decay * config.sign


def aggregate_contributions(
    events: list[tuple[SignalConfig, date]],
    reference_date: date,
    alpha: float = 1.5,
) -> float:
    """Sum decayed contributions from all events for a UBID."""
    return sum(contribution(cfg, dt, reference_date, alpha) for cfg, dt in events)
