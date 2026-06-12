from backend.app.services.strategy_iteration import run_strategy_tournament


def test_strategy_tournament_returns_ranked_winner():
    result = run_strategy_tournament("data/sample_prices.csv")

    assert result["status"] == "completed"
    assert result["candidate_count"] > 0
    assert result["winner"]["strategy_id"].startswith("momentum_")
    assert result["candidates"][0] == result["winner"]
