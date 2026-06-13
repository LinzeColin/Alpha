from pathlib import Path

from backend.app.services.strategy_iteration import run_strategy_tournament
from backend.app.services.strategy_journal import append_strategy_tournament_history, summarize_strategy_tournament_history


def test_strategy_journal_records_tournament_winner_and_stability(tmp_path):
    history_path = tmp_path / "runtime" / "strategy_tournament_history.jsonl"
    tournament = run_strategy_tournament(Path("data/sample_prices.csv"))
    market_data = {"source_kind": "fixture", "data_quality": "sample", "latest_date": "2024-02-09", "real_market_data": False}

    first = append_strategy_tournament_history(tournament, history_path=history_path, run_id="run_1", market_data=market_data)
    second = append_strategy_tournament_history(tournament, history_path=history_path, run_id="run_2", market_data=market_data)
    summary = summarize_strategy_tournament_history(history_path)

    assert first["status"] == "written"
    assert second["row_count"] == 2
    assert summary["status"] == "ready"
    assert summary["status_zh"] == "就绪"
    assert summary["run_count"] == 2
    assert summary["latest_winner_strategy_id"] == tournament["winner"]["strategy_id"]
    assert summary["latest_winner_strategy_id_zh"].startswith("动量策略 ")
    assert summary["latest_winner_decision_zh"] == "可进入模拟交易"
    assert summary["latest_market_data_quality_zh"] == "样例"
    assert summary["current_winner_streak"] == 2
    assert summary["stability_ratio"] == 1.0
    assert summary["stability_ratio_zh"] == "100.00%"
    assert summary["recent"][-1]["market_data_quality"] == "sample"
    assert summary["recent"][-1]["market_data_quality_zh"] == "样例"
    assert summary["recent"][-1]["winner_decision_zh"] == "可进入模拟交易"


def test_strategy_journal_empty_summary_is_chinese_readable(tmp_path):
    summary = summarize_strategy_tournament_history(tmp_path / "missing.jsonl")

    assert summary["status"] == "empty"
    assert summary["status_zh"] == "暂无记录"
    assert summary["run_count"] == 0
    assert summary["stability_ratio_zh"] == "0.00%"


def test_strategy_journal_localizes_broker_quote_cache_source(tmp_path):
    history_path = tmp_path / "runtime" / "strategy_tournament_history.jsonl"
    tournament = run_strategy_tournament(Path("data/sample_prices.csv"))

    append_strategy_tournament_history(
        tournament,
        history_path=history_path,
        run_id="run_broker_quote",
        market_data={
            "source_kind": "broker_quote_cache",
            "data_quality": "fresh",
            "latest_date": "2026-06-12",
            "real_market_data": True,
        },
    )
    summary = summarize_strategy_tournament_history(history_path)

    assert summary["latest_market_data_source_kind"] == "broker_quote_cache"
    assert summary["latest_market_data_source_kind_zh"] == "经纪商只读行情缓存"
    assert summary["recent"][-1]["market_data_source_kind_zh"] == "经纪商只读行情缓存"
