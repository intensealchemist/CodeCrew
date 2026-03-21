"""
Quality Telemetry for free_ha mode.

Tracks per-model success / rate-limit / context-exceeded counts across all
runs and persists them to ~/.codecrew/quality_stats.json.

The router uses these stats to break ties when multiple providers are at the
same quality rank: a model with a 95% success rate is preferred over one
sitting at 60%, even if they share the same nominal rank.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

_STATS_FILE = Path.home() / ".codecrew" / "quality_stats.json"

_EMPTY_ENTRY: dict = {
    "attempts": 0,
    "successes": 0,
    "rate_limits": 0,
    "context_exceeded": 0,
}


def _load() -> dict:
    try:
        if _STATS_FILE.exists():
            return json.loads(_STATS_FILE.read_text("utf-8"))
    except Exception:
        pass
    return {}


def _save(stats: dict) -> None:
    try:
        _STATS_FILE.parent.mkdir(parents=True, exist_ok=True)
        _STATS_FILE.write_text(json.dumps(stats, indent=2), "utf-8")
    except Exception:
        pass  # Telemetry must never crash the main process


def _bump(model_key: str, field: str, extra: dict | None = None) -> None:
    stats = _load()
    entry = stats.setdefault(model_key, dict(_EMPTY_ENTRY))
    entry["attempts"] = entry.get("attempts", 0) + 1
    entry[field] = entry.get(field, 0) + 1
    if extra:
        entry.update(extra)
    _save(stats)


# ── Public API ────────────────────────────────────────────────────────────────

def record_success(model_key: str) -> None:
    _bump(model_key, "successes", {"last_success": datetime.now(timezone.utc).isoformat()})


def record_rate_limit(model_key: str) -> None:
    _bump(model_key, "rate_limits")


def record_context_exceeded(model_key: str) -> None:
    _bump(model_key, "context_exceeded")


def success_rate(model_key: str) -> float:
    """
    Returns [0.0, 1.0].  Defaults to 1.0 (optimistic prior) when fewer than
    5 attempts have been recorded — not enough data to penalise a model.
    """
    entry = _load().get(model_key, {})
    attempts = entry.get("attempts", 0)
    if attempts < 5:
        return 1.0
    return entry.get("successes", 0) / attempts


def print_quality_report() -> None:
    stats = _load()
    if not stats:
        return
    print("\n  📊 free_ha Quality Stats (cumulative across all runs):")
    for model_key, d in sorted(stats.items()):
        n = d.get("attempts", 0)
        if n == 0:
            continue
        s = d.get("successes", 0)
        rate = s / n * 100
        bar = "█" * int(rate / 10) + "░" * (10 - int(rate / 10))
        print(
            f"     {model_key:<40} {bar} {rate:4.0f}%  "
            f"({s}/{n} ok | RL:{d.get('rate_limits', 0)} CTX:{d.get('context_exceeded', 0)})"
        )
    last_success_ts = max(
        (d.get("last_success", "") for d in stats.values()), default=""
    )
    if last_success_ts:
        print(f"\n     Last successful call: {last_success_ts}")
