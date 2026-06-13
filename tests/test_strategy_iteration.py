from backend.app.services.strategy_iteration import run_strategy_tournament


def test_strategy_tournament_returns_ranked_winner():
    result = run_strategy_tournament("data/sample_prices.csv")

    assert result["status"] == "completed"
    assert result["candidate_count"] > 0
    assert result["winner"]["strategy_id"].startswith("momentum_")
    assert result["candidates"][0] == result["winner"]
    assert result["validation_summary"]["validated_count"] > 0
    assert result["winner"]["validation_windows"] > 0
    assert 0 <= result["winner"]["hit_rate"] <= 1
    assert "oos_return" in result["winner"]
