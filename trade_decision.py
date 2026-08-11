"""
Trade decision gating for risk-bubble signals.

This module turns raw model signals into action/no-action recommendations by
comparing the current signal against the last recorded state for each ticker.
It is intentionally simple and file-backed so the report can run from cron.
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any


DEFAULT_STATE_PATH = os.path.join("output", "trade_decision_state.json")
MIN_ACTION_DAYS = 3
MIN_RISK_DELTA = 0.10
MIN_TARGET_DELTA = 0.20

READINESS_SIZE_MULTIPLIERS = {
    "Validated": 1.0,
    "Thin Edge": 0.5,
    "Return Edge / DD Risk": 0.5,
    "Watch Only": 0.0,
}


def load_decision_state(path: str = DEFAULT_STATE_PATH) -> dict[str, Any]:
    if not os.path.exists(path):
        return {}

    try:
        with open(path, "r", encoding="utf-8") as f:
            state = json.load(f)
            return state if isinstance(state, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def save_decision_state(state: dict[str, Any], path: str = DEFAULT_STATE_PATH) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, sort_keys=True)
        f.write("\n")


def days_since(value: str | None, as_of: datetime) -> int | None:
    if not value:
        return None

    try:
        prior = datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        return None

    return (as_of - prior).days


def scale_target_position(target_position: float, readiness: str) -> float:
    multiplier = READINESS_SIZE_MULTIPLIERS.get(readiness, 0.0)
    return round(target_position * multiplier, 2)


def evaluate_trade_decision(
    *,
    ticker: str,
    name: str,
    sector: str,
    readiness: str,
    signal: str,
    target_position: float,
    risk: float,
    price: float,
    state: dict[str, Any],
    as_of: datetime | None = None,
) -> dict[str, Any]:
    """
    Return a gated trade decision and update state in memory.

    The caller owns persistence via save_decision_state().
    """
    as_of = as_of or datetime.now()
    today = as_of.strftime("%Y-%m-%d")
    previous = state.get(ticker, {})
    scaled_target = scale_target_position(target_position, readiness)

    if readiness == "Watch Only":
        action = "WATCH_ONLY"
        reason = "Sector is watch-only; no trade recommendation."
    elif not previous:
        action = "REVIEW"
        reason = "First recorded signal; review manually before trading."
    else:
        prior_signal = previous.get("signal")
        prior_target = float(previous.get("target_position", 1.0))
        prior_risk = float(previous.get("risk", risk))
        last_action_days = days_since(previous.get("last_action_date"), as_of)

        signal_changed = signal != prior_signal
        target_changed = abs(scaled_target - prior_target) >= MIN_TARGET_DELTA
        risk_moved = abs(risk - prior_risk) >= MIN_RISK_DELTA
        spacing_ok = last_action_days is None or last_action_days >= MIN_ACTION_DAYS

        if signal_changed and target_changed and spacing_ok:
            action = "TRADE"
            reason = f"Signal changed from {prior_signal} to {signal}; target moved materially."
        elif signal_changed and spacing_ok:
            action = "REVIEW"
            reason = f"Signal changed from {prior_signal} to {signal}; target change is modest."
        elif target_changed and spacing_ok:
            action = "REBALANCE"
            reason = "Target position changed materially while signal state stayed stable."
        elif risk_moved and spacing_ok:
            action = "REVIEW"
            reason = f"Risk moved by {abs(risk - prior_risk):.2f}; confirm before trading."
        elif not spacing_ok:
            action = "NO_ACTION"
            reason = f"Minimum {MIN_ACTION_DAYS}-day spacing gate active."
        else:
            action = "NO_ACTION"
            reason = "No meaningful signal, target, or risk change."

    if readiness == "Thin Edge" and action in {"TRADE", "REBALANCE"}:
        action = "REVIEW"
        reason = f"{reason} Thin-edge sector requires manual confirmation."
    elif readiness == "Return Edge / DD Risk" and action in {"TRADE", "REBALANCE"}:
        action = "REVIEW"
        reason = f"{reason} Drawdown-risk sector requires smaller/manual execution."

    last_action_date = previous.get("last_action_date")
    if action in {"TRADE", "REBALANCE", "REVIEW"}:
        last_action_date = today

    state[ticker] = {
        "name": name,
        "sector": sector,
        "readiness": readiness,
        "signal": signal,
        "target_position": scaled_target,
        "raw_target_position": target_position,
        "risk": round(risk, 4),
        "price": round(price, 4),
        "last_seen_date": today,
        "last_action_date": last_action_date,
    }

    return {
        "action": action,
        "reason": reason,
        "target_position": scaled_target,
        "raw_target_position": target_position,
        "readiness": readiness,
        "previous_signal": previous.get("signal"),
        "previous_target": previous.get("target_position"),
        "previous_risk": previous.get("risk"),
    }
