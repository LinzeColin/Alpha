from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from backend.app.services.display_locale import zh_data_quality, zh_market_data_source, zh_status, zh_strategy_id


DEFAULT_MAX_STRATEGY_HISTORY_ROWS = 10_000


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def append_strategy_tournament_history(
    tournament: dict,
    *,
    history_path: str | Path,
    run_id: str,
    market_data: dict | None = None,
    max_rows: int = DEFAULT_MAX_STRATEGY_HISTORY_ROWS,
) -> dict:
    path = Path(history_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    winner = tournament.get("winner") or {}
    validation = tournament.get("validation_summary") or {}
    market = market_data or {}
    record = _localized_record({
        "run_id": run_id,
        "generated_at": utc_now_iso(),
        "status": tournament.get("status"),
        "candidate_count": tournament.get("candidate_count", 0),
        "validated_count": validation.get("validated_count", 0),
        "winner_strategy_id": winner.get("strategy_id"),
        "winner_symbol": winner.get("symbol"),
        "winner_score": winner.get("score"),
        "winner_decision": winner.get("decision"),
        "winner_hit_rate": winner.get("hit_rate"),
        "winner_oos_return": winner.get("oos_return"),
        "winner_validation_windows": winner.get("validation_windows", 0),
        "winner_max_drawdown": winner.get("max_drawdown"),
        "market_data_source_kind": market.get("source_kind"),
        "market_data_quality": market.get("data_quality"),
        "market_data_latest_date": market.get("latest_date"),
        "real_market_data": bool(market.get("real_market_data", False)),
    })
    rows = _read_jsonl(path)
    rows.append(record)
    if max_rows > 0:
        rows = rows[-max_rows:]
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows) + "\n", encoding="utf-8")
    return {
        "status": "written",
        "status_zh": "已写入",
        "path": str(path),
        "row_count": len(rows),
        "latest_record": record,
    }


def summarize_strategy_tournament_history(history_path: str | Path, *, limit: int = 20) -> dict:
    path = Path(history_path)
    rows = _read_jsonl(path)
    recent = rows[-limit:] if limit > 0 else rows
    latest = rows[-1] if rows else None
    localized_recent = [_localized_record(row) for row in recent]
    localized_latest = _localized_record(latest) if latest else {}
    winner_ids = [row.get("winner_strategy_id") for row in recent if row.get("winner_strategy_id")]
    latest_winner = latest.get("winner_strategy_id") if latest else None
    latest_winner_recent_count = sum(1 for value in winner_ids if value == latest_winner) if latest_winner else 0
    current_streak = _current_winner_streak(rows)
    denominator = len(winner_ids) or 1
    stability_ratio = latest_winner_recent_count / denominator if latest_winner else 0.0
    return {
        "status": "ready" if rows else "empty",
        "status_zh": "就绪" if rows else "暂无记录",
        "path": str(path),
        "exists": path.exists(),
        "run_count": len(rows),
        "recent_count": len(recent),
        "unique_winner_count": len(set(winner_ids)),
        "latest_winner_strategy_id": latest_winner,
        "latest_winner_strategy_id_zh": localized_latest.get("winner_strategy_id_zh"),
        "latest_winner_symbol": latest.get("winner_symbol") if latest else None,
        "latest_winner_decision": latest.get("winner_decision") if latest else None,
        "latest_winner_decision_zh": localized_latest.get("winner_decision_zh"),
        "latest_winner_hit_rate": latest.get("winner_hit_rate") if latest else None,
        "latest_winner_oos_return": latest.get("winner_oos_return") if latest else None,
        "latest_winner_validation_windows": latest.get("winner_validation_windows") if latest else 0,
        "latest_market_data_quality": latest.get("market_data_quality") if latest else None,
        "latest_market_data_quality_zh": localized_latest.get("market_data_quality_zh"),
        "latest_generated_at": latest.get("generated_at") if latest else None,
        "latest_winner_recent_count": latest_winner_recent_count,
        "current_winner_streak": current_streak,
        "stability_ratio": round(stability_ratio, 6),
        "stability_ratio_zh": f"{stability_ratio * 100:.2f}%",
        "recent": localized_recent,
    }


def _localized_record(record: dict | None) -> dict:
    if not record:
        return {}
    localized = dict(record)
    localized["status_zh"] = zh_status(localized.get("status"))
    localized["winner_strategy_id_zh"] = zh_strategy_id(localized.get("winner_strategy_id"))
    localized["winner_decision_zh"] = zh_status(localized.get("winner_decision"))
    localized["market_data_source_kind_zh"] = zh_market_data_source(localized.get("market_data_source_kind"))
    localized["market_data_quality_zh"] = zh_data_quality(localized.get("market_data_quality"))
    localized["real_market_data_zh"] = "是" if localized.get("real_market_data") else "否"
    return localized


def _current_winner_streak(rows: list[dict]) -> int:
    if not rows:
        return 0
    latest_winner = rows[-1].get("winner_strategy_id")
    if not latest_winner:
        return 0
    streak = 0
    for row in reversed(rows):
        if row.get("winner_strategy_id") != latest_winner:
            break
        streak += 1
    return streak


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            rows.append(value)
    return rows
