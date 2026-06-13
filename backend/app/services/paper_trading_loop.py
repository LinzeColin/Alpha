from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from uuid import uuid4

from backend.app.services.approval_queue import ApprovalQueue
from backend.app.services.audit import MemoryAuditSink
from backend.app.services.backtest import load_price_fixture
from backend.app.services.broker_paper_adapter import LocalSandboxPaperBrokerAdapter, PaperBrokerAdapter
from backend.app.services.display_locale import format_paper_cycle_summary_zh
from backend.app.services.market_data_gateway import MarketDataGateway, MarketDataSnapshot, utc_now_iso as market_data_utc_now_iso
from backend.app.services.order_ticket import BrokerReadyOrderTicket, OrderIntent, utc_now_iso
from backend.app.services.paper_broker import PaperBroker, PaperOrder
from backend.app.services.policy import GovernorPolicy
from backend.app.services.risk import pre_trade_risk_check
from backend.app.services.strategy_journal import append_strategy_tournament_history
from backend.app.services.strategy_iteration import run_strategy_tournament


DEFAULT_REFRESH_INTERVAL_SECONDS = 300


class PaperTradingLoop:
    def __init__(
        self,
        *,
        policy: GovernorPolicy,
        price_path: str | Path,
        approval_queue: ApprovalQueue | None = None,
        paper_broker: PaperBroker | None = None,
        paper_broker_adapter: PaperBrokerAdapter | None = None,
        paper_state_path: str | Path | None = None,
        market_data_gateway: MarketDataGateway | None = None,
        strategy_history_path: str | Path | None = None,
        audit_sink: MemoryAuditSink | None = None,
        refresh_interval_seconds: int = DEFAULT_REFRESH_INTERVAL_SECONDS,
    ) -> None:
        self.policy = policy
        self.price_path = Path(price_path)
        self.approval_queue = approval_queue or ApprovalQueue()
        self.paper_state_path = Path(paper_state_path) if paper_state_path else None
        self.paper_broker = paper_broker or (PaperBroker.load(self.paper_state_path) if self.paper_state_path else PaperBroker())
        self.paper_broker_adapter = paper_broker_adapter or LocalSandboxPaperBrokerAdapter(self.paper_broker)
        self.market_data_gateway = market_data_gateway
        self.strategy_history_path = Path(strategy_history_path) if strategy_history_path else None
        self.audit_sink = audit_sink or MemoryAuditSink()
        self.refresh_interval_seconds = refresh_interval_seconds

    def run_once(self) -> dict:
        run_id = f"run_{uuid4().hex[:12]}"
        market_data = self._resolve_market_data()
        tournament = run_strategy_tournament(market_data.price_path)
        strategy_journal = self._append_strategy_history(tournament, run_id=run_id, market_data=market_data.status)
        intent = self._generate_order_intent(run_id, tournament=tournament, price_path=market_data.price_path)
        risk_check = pre_trade_risk_check(intent.as_dict(), self.policy)
        ticket = BrokerReadyOrderTicket.from_intent(intent, risk_check).as_dict()
        queue_result = self.approval_queue.enqueue(ticket)

        paper_order = PaperOrder(
            idempotency_key=intent.idempotency_key,
            symbol=intent.symbol,
            side=intent.side,
            quantity=intent.quantity,
            price=intent.estimated_price,
        )
        broker_paper_receipt = self.paper_broker_adapter.skipped_receipt(
            paper_order,
            reason=risk_check["reason"],
            source_ticket=ticket,
        )
        paper_result = broker_paper_receipt["paper_result"]
        if risk_check.get("allowed"):
            broker_paper_receipt = self.paper_broker_adapter.submit_order(paper_order, source_ticket=ticket)
            paper_result = broker_paper_receipt["paper_result"]
            if self.paper_state_path:
                self.paper_broker.save(self.paper_state_path)

        mark_prices = latest_mark_prices(market_data.price_path)
        portfolio = self.paper_broker.portfolio_snapshot(mark_prices)

        self.audit_sink.write(
            trace_id=run_id,
            actor_type="agent",
            actor_id="paper_trading_loop",
            event_type="paper_cycle",
            decision=queue_result["status"],
            reason=risk_check["reason"],
            payload={
                "strategy_tournament": tournament,
                "strategy_journal": strategy_journal,
                "intent": intent.as_dict(),
                "risk_check": risk_check,
                "market_data": market_data.status,
                "broker_paper_receipt": broker_paper_receipt,
                "paper_result": paper_result,
                "paper_portfolio": portfolio,
            },
        )

        return {
            "run_id": run_id,
            "status": "completed",
            "generated_at": utc_now_iso(),
            "refresh_interval_seconds": self.refresh_interval_seconds,
            "next_refresh_in_seconds": self.refresh_interval_seconds,
            "intent": intent.as_dict(),
            "market_data": market_data.status,
            "strategy_tournament": tournament,
            "strategy_journal": strategy_journal,
            "risk_check": risk_check,
            "approval_queue": queue_result,
            "paper_broker_adapter": self.paper_broker_adapter.status(),
            "broker_paper_order": broker_paper_receipt,
            "paper_order": paper_result,
            "paper_portfolio": portfolio,
            "audit_events": self.audit_sink.as_dicts(),
        }

    def run_forever(self, *, output_json: bool = False) -> None:
        while True:
            result = self.run_once()
            if output_json:
                print(json.dumps(result, indent=2, sort_keys=True))
            else:
                print(format_paper_cycle_summary_zh(result), flush=True)
            time.sleep(self.refresh_interval_seconds)

    def _generate_order_intent(self, run_id: str, *, tournament: dict, price_path: str | Path | None = None) -> OrderIntent:
        df = load_price_fixture(price_path or self.price_path)
        latest_prices = df.sort_values("date").groupby("symbol").tail(1).copy()
        max_notional = float(self.policy.data.get("risk_limits", {}).get("max_order_value_aud", 0))
        candidates = latest_prices[latest_prices["close"] <= max_notional].sort_values("close", ascending=False)
        tradable_symbols = set(candidates["symbol"].tolist())
        winner = _select_tradable_winner(tournament, tradable_symbols)
        symbol = winner.get("symbol")
        if symbol and not candidates[candidates["symbol"] == symbol].empty:
            latest = candidates[candidates["symbol"] == symbol].iloc[0]
        else:
            latest = (candidates if not candidates.empty else latest_prices.sort_values("close")).iloc[0]
            winner = {"strategy_id": f"fixture_momentum_{latest['symbol']}", "symbol": str(latest["symbol"])}
        return OrderIntent.create(
            strategy_id=str(winner.get("strategy_id", "fixture_momentum_v0")),
            symbol=str(latest["symbol"]),
            side="buy",
            quantity=1,
            estimated_price=float(latest["close"]),
            source_run_id=run_id,
            ttl_seconds=self.refresh_interval_seconds,
        )

    def _resolve_market_data(self) -> MarketDataSnapshot:
        if self.market_data_gateway:
            return self.market_data_gateway.resolve_price_path()
        return _static_market_data_snapshot(self.price_path)

    def _append_strategy_history(self, tournament: dict, *, run_id: str, market_data: dict) -> dict:
        if not self.strategy_history_path:
            return {"status": "skipped", "status_zh": "已跳过", "reason_zh": "未配置策略迭代历史文件。"}
        return append_strategy_tournament_history(
            tournament,
            history_path=self.strategy_history_path,
            run_id=run_id,
            market_data=market_data,
        )


def build_default_loop(
    queue_path: str | Path | None = None,
    paper_state_path: str | Path | None = None,
    strategy_history_path: str | Path | None = None,
    interval_seconds: int = DEFAULT_REFRESH_INTERVAL_SECONDS,
) -> PaperTradingLoop:
    root = Path(__file__).resolve().parents[3]
    policy = GovernorPolicy.load(root / "configs" / "trading_governor_policy.yaml")
    state_path = Path(paper_state_path) if paper_state_path else root / "runtime" / "paper_portfolio.json"
    return PaperTradingLoop(
        policy=policy,
        price_path=root / "data" / "sample_prices.csv",
        approval_queue=ApprovalQueue(queue_path or root / "runtime" / "approval_queue.sqlite3"),
        paper_state_path=state_path,
        market_data_gateway=MarketDataGateway(root=root),
        strategy_history_path=strategy_history_path or root / "runtime" / "strategy_tournament_history.jsonl",
        refresh_interval_seconds=interval_seconds,
    )


def latest_mark_prices(price_path: str | Path) -> dict[str, float]:
    df = load_price_fixture(price_path)
    latest_prices = df.sort_values("date").groupby("symbol").tail(1)
    return {str(row["symbol"]): float(row["close"]) for _, row in latest_prices.iterrows()}


def _static_market_data_snapshot(price_path: str | Path) -> MarketDataSnapshot:
    path = Path(price_path)
    df = load_price_fixture(path)
    latest = df.sort_values("date").groupby("symbol").tail(1)
    latest_prices = {str(row["symbol"]): round(float(row["close"]), 4) for _, row in latest.iterrows()}
    latest_date = latest["date"].max()
    status = {
        "provider": "direct_file",
        "source_kind": "local_file",
        "data_quality": "sample",
        "real_market_data": False,
        "price_path": str(path),
        "cache_path": None,
        "fixture_path": str(path),
        "cache_exists": False,
        "cache_age_seconds": None,
        "max_cache_age_seconds": None,
        "symbols": sorted(str(symbol) for symbol in df["symbol"].unique()),
        "symbol_count": int(df["symbol"].nunique()),
        "row_count": int(len(df)),
        "latest_date": latest_date.date().isoformat() if hasattr(latest_date, "date") else str(latest_date),
        "latest_prices": latest_prices,
        "refresh_attempted": False,
        "refresh_succeeded": False,
        "refresh_error": None,
        "generated_at": market_data_utc_now_iso(),
    }
    return MarketDataSnapshot(price_path=path, status=status)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--interval-seconds", type=int, default=DEFAULT_REFRESH_INTERVAL_SECONDS)
    parser.add_argument("--queue-path", default=None)
    parser.add_argument("--paper-state-path", default=None)
    parser.add_argument("--json", action="store_true", help="输出原始机器 JSON；默认输出中文运行摘要")
    args = parser.parse_args()

    loop = build_default_loop(
        queue_path=args.queue_path,
        paper_state_path=args.paper_state_path,
        interval_seconds=args.interval_seconds,
    )
    if args.once:
        result = loop.run_once()
        if args.json:
            print(json.dumps(result, indent=2, sort_keys=True))
        else:
            print(format_paper_cycle_summary_zh(result))
        return
    loop.run_forever(output_json=args.json)


def _select_tradable_winner(tournament: dict, tradable_symbols: set[str]) -> dict:
    for candidate in tournament.get("candidates", []):
        if candidate.get("symbol") in tradable_symbols:
            return candidate
    return tournament.get("winner") or {}


if __name__ == "__main__":
    main()
