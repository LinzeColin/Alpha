from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from uuid import uuid4

from backend.app.services.approval_queue import ApprovalQueue
from backend.app.services.audit import MemoryAuditSink
from backend.app.services.backtest import load_price_fixture
from backend.app.services.broker_paper_adapter import PaperBrokerAdapter, build_paper_broker_adapter
from backend.app.services.display_locale import format_paper_cycle_summary_zh
from backend.app.services.market_data_gateway import MarketDataGateway, MarketDataSnapshot, utc_now_iso as market_data_utc_now_iso
from backend.app.services.order_ticket import BrokerReadyOrderTicket, OrderIntent, utc_now_iso
from backend.app.services.paper_broker import PaperBroker, PaperOrder
from backend.app.services.paper_performance import append_paper_performance_history
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
        performance_history_path: str | Path | None = None,
        audit_sink: MemoryAuditSink | None = None,
        refresh_interval_seconds: int = DEFAULT_REFRESH_INTERVAL_SECONDS,
    ) -> None:
        self.policy = policy
        self.price_path = Path(price_path)
        self.approval_queue = approval_queue or ApprovalQueue()
        self.paper_state_path = Path(paper_state_path) if paper_state_path else None
        self.paper_broker = paper_broker or (PaperBroker.load(self.paper_state_path) if self.paper_state_path else PaperBroker())
        self.paper_broker_adapter = paper_broker_adapter or build_paper_broker_adapter(self.paper_broker)
        self.market_data_gateway = market_data_gateway
        self.strategy_history_path = Path(strategy_history_path) if strategy_history_path else None
        self.performance_history_path = Path(performance_history_path) if performance_history_path else None
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
        paper_performance = self._append_performance_history(
            portfolio,
            run_id=run_id,
            market_data=market_data.status,
            intent=intent.as_dict(),
            broker_receipt=broker_paper_receipt,
        )

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
                "paper_performance": paper_performance,
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
            "paper_performance": paper_performance,
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
        latest_price_map = {str(row["symbol"]): float(row["close"]) for _, row in latest_prices.iterrows()}
        limits = self.policy.data.get("risk_limits", {})
        max_notional = float(limits.get("max_order_value_aud", 0))
        max_position_weight_pct = float(limits.get("max_position_weight_pct", 0) or 0)
        max_total_gross_exposure_pct = float(limits.get("max_total_gross_exposure_pct", 0) or 0)
        candidates = latest_prices[latest_prices["close"] <= max_notional].sort_values("close", ascending=False)
        tradable_symbols = set(candidates["symbol"].tolist())
        winner = _select_tradable_winner(tournament, tradable_symbols)
        symbol = winner.get("symbol")
        if symbol and not candidates[candidates["symbol"] == symbol].empty:
            latest = candidates[candidates["symbol"] == symbol].iloc[0]
        else:
            latest = (candidates if not candidates.empty else latest_prices.sort_values("close")).iloc[0]
            winner = {"strategy_id": f"fixture_momentum_{latest['symbol']}", "symbol": str(latest["symbol"])}
        side = "buy"
        quantity = 1.0
        estimated_price = float(latest["close"])
        strategy_id = str(winner.get("strategy_id", "fixture_momentum_v0"))
        exposure = _portfolio_exposure(
            cash=self.paper_broker.cash,
            positions=self.paper_broker.positions,
            latest_price_map=latest_price_map,
        )
        risk_reduction_order = _select_policy_reduction_sell_order(
            latest_price_map=latest_price_map,
            positions=self.paper_broker.positions,
            max_notional=max_notional,
            equity=exposure["equity"],
            total_gross_exposure=exposure["total_gross_exposure"],
            max_position_weight_pct=max_position_weight_pct,
            max_total_gross_exposure_pct=max_total_gross_exposure_pct,
        )
        if risk_reduction_order:
            side = "sell"
            symbol, estimated_price, quantity = risk_reduction_order
            strategy_id = f"target_rebalance_{symbol}"
            return OrderIntent.create(
                strategy_id=strategy_id,
                symbol=str(symbol or latest["symbol"]),
                side=side,
                quantity=quantity,
                estimated_price=estimated_price,
                source_run_id=run_id,
                ttl_seconds=self.refresh_interval_seconds,
            )

        buy_order = _select_policy_eligible_buy_order(
            candidates=candidates.to_dict("records"),
            tournament=tournament,
            cash=self.paper_broker.cash,
            positions=self.paper_broker.positions,
            latest_price_map=latest_price_map,
            adapter_status=self.paper_broker_adapter.status(),
            max_notional=max_notional,
            equity=exposure["equity"],
            total_gross_exposure=exposure["total_gross_exposure"],
            max_position_weight_pct=max_position_weight_pct,
            max_total_gross_exposure_pct=max_total_gross_exposure_pct,
        )
        if buy_order:
            symbol, estimated_price, quantity, strategy_id = buy_order
            return OrderIntent.create(
                strategy_id=strategy_id,
                symbol=symbol,
                side="buy",
                quantity=quantity,
                estimated_price=estimated_price,
                source_run_id=run_id,
                ttl_seconds=self.refresh_interval_seconds,
            )

        rebalance_order = _select_rebalance_sell_order(
            latest_price_map=latest_price_map,
            positions=self.paper_broker.positions,
            max_notional=max_notional,
        )
        if rebalance_order:
            side = "sell"
            symbol, estimated_price, quantity = rebalance_order
            strategy_id = (
                f"cash_rebalance_{symbol}"
                if self.paper_broker.cash
                < _estimated_buy_cash_required(
                    estimated_price,
                    quantity=1.0,
                    adapter_status=self.paper_broker_adapter.status(),
                )
                else f"target_rebalance_{symbol}"
            )
            return OrderIntent.create(
                strategy_id=strategy_id,
                symbol=str(symbol or latest["symbol"]),
                side=side,
                quantity=quantity,
                estimated_price=estimated_price,
                source_run_id=run_id,
                ttl_seconds=self.refresh_interval_seconds,
            )

        buy_cash_required = _estimated_buy_cash_required(
            estimated_price,
            quantity=quantity,
            adapter_status=self.paper_broker_adapter.status(),
        )
        if self.paper_broker.cash < buy_cash_required:
            rebalance_order = _select_rebalance_sell_order(
                latest_price_map=latest_price_map,
                positions=self.paper_broker.positions,
                max_notional=max_notional,
            )
            if rebalance_order:
                side = "sell"
                symbol, estimated_price, quantity = rebalance_order
                strategy_id = _strategy_id_for_symbol(tournament, symbol) or f"cash_rebalance_{symbol}"
        return OrderIntent.create(
            strategy_id=strategy_id,
            symbol=str(symbol or latest["symbol"]),
            side=side,
            quantity=quantity,
            estimated_price=estimated_price,
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

    def _append_performance_history(
        self,
        portfolio: dict,
        *,
        run_id: str,
        market_data: dict,
        intent: dict,
        broker_receipt: dict,
    ) -> dict:
        if not self.performance_history_path:
            return {"status": "skipped", "status_zh": "已跳过", "reason_zh": "未配置模拟绩效历史文件。"}
        return append_paper_performance_history(
            portfolio,
            history_path=self.performance_history_path,
            run_id=run_id,
            market_data=market_data,
            intent=intent,
            broker_receipt=broker_receipt,
        )


def build_default_loop(
    queue_path: str | Path | None = None,
    paper_state_path: str | Path | None = None,
    strategy_history_path: str | Path | None = None,
    performance_history_path: str | Path | None = None,
    market_data_gateway: MarketDataGateway | None = None,
    interval_seconds: int = DEFAULT_REFRESH_INTERVAL_SECONDS,
) -> PaperTradingLoop:
    root = Path(__file__).resolve().parents[3]
    policy = GovernorPolicy.load(root / "configs" / "trading_governor_policy.yaml")
    state_path = Path(paper_state_path) if paper_state_path else root / "runtime" / "paper_portfolio.json"
    paper_broker = PaperBroker.load(state_path) if state_path.exists() else PaperBroker()
    return PaperTradingLoop(
        policy=policy,
        price_path=root / "data" / "sample_prices.csv",
        approval_queue=ApprovalQueue(queue_path or root / "runtime" / "approval_queue.sqlite3"),
        paper_broker=paper_broker,
        paper_broker_adapter=build_paper_broker_adapter(paper_broker, config_path=root / "configs" / "paper_broker.yaml"),
        paper_state_path=state_path,
        market_data_gateway=market_data_gateway or MarketDataGateway(root=root),
        strategy_history_path=strategy_history_path or root / "runtime" / "strategy_tournament_history.jsonl",
        performance_history_path=performance_history_path or root / "runtime" / "paper_performance_history.jsonl",
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


def _estimated_buy_cash_required(price: float, *, quantity: float, adapter_status: dict) -> float:
    slippage_bps = float(adapter_status.get("slippage_bps", 0.0) or 0.0)
    commission = float(adapter_status.get("commission_per_order", 0.0) or 0.0)
    simulated_price = float(price) * (1.0 + (slippage_bps / 10_000.0))
    return (simulated_price * float(quantity)) + commission


def _select_rebalance_sell_order(
    *,
    latest_price_map: dict[str, float],
    positions: dict[str, float],
    max_notional: float,
) -> tuple[str, float, float] | None:
    candidates: list[tuple[str, float, float, float]] = []
    for symbol, raw_quantity in positions.items():
        available_quantity = float(raw_quantity)
        estimated_price = float(latest_price_map.get(symbol, 0.0) or 0.0)
        if available_quantity <= 0 or estimated_price <= 0:
            continue
        max_quantity_by_policy = max_notional / estimated_price if max_notional > 0 else available_quantity
        order_quantity = min(available_quantity, 1.0, max_quantity_by_policy)
        if order_quantity <= 0:
            continue
        market_value = available_quantity * estimated_price
        candidates.append((str(symbol), estimated_price, round(order_quantity, 6), market_value))
    if not candidates:
        return None
    symbol, estimated_price, order_quantity, _ = sorted(candidates, key=lambda row: row[3], reverse=True)[0]
    return symbol, estimated_price, order_quantity


def _portfolio_exposure(*, cash: float, positions: dict[str, float], latest_price_map: dict[str, float]) -> dict:
    position_values = {
        str(symbol): max(float(quantity), 0.0) * float(latest_price_map.get(symbol, 0.0) or 0.0)
        for symbol, quantity in positions.items()
    }
    total_gross_exposure = sum(position_values.values())
    return {
        "position_values": position_values,
        "total_gross_exposure": total_gross_exposure,
        "equity": float(cash) + total_gross_exposure,
    }


def _select_policy_reduction_sell_order(
    *,
    latest_price_map: dict[str, float],
    positions: dict[str, float],
    max_notional: float,
    equity: float,
    total_gross_exposure: float,
    max_position_weight_pct: float,
    max_total_gross_exposure_pct: float,
) -> tuple[str, float, float] | None:
    max_position_value = equity * (max_position_weight_pct / 100.0) if max_position_weight_pct > 0 else 0.0
    max_gross_value = equity * (max_total_gross_exposure_pct / 100.0) if max_total_gross_exposure_pct > 0 else 0.0
    candidates: list[tuple[str, float, float, float]] = []
    for symbol, raw_quantity in positions.items():
        available_quantity = float(raw_quantity)
        estimated_price = float(latest_price_map.get(symbol, 0.0) or 0.0)
        if available_quantity <= 0 or estimated_price <= 0:
            continue
        position_value = available_quantity * estimated_price
        position_excess = max(position_value - max_position_value, 0.0) if max_position_value > 0 else 0.0
        gross_excess = max(total_gross_exposure - max_gross_value, 0.0) if max_gross_value > 0 else 0.0
        reduction_need = max(position_excess, gross_excess)
        if reduction_need <= 0:
            continue
        max_quantity_by_policy = max_notional / estimated_price if max_notional > 0 else available_quantity
        desired_quantity = max(1.0 if available_quantity >= 1.0 else available_quantity, reduction_need / estimated_price)
        order_quantity = min(available_quantity, max_quantity_by_policy, desired_quantity)
        if order_quantity <= 0:
            continue
        candidates.append((str(symbol), estimated_price, round(order_quantity, 6), reduction_need))
    if not candidates:
        return None
    symbol, estimated_price, order_quantity, _ = sorted(candidates, key=lambda row: row[3], reverse=True)[0]
    return symbol, estimated_price, order_quantity


def _select_policy_eligible_buy_order(
    *,
    candidates: list[dict],
    tournament: dict,
    cash: float,
    positions: dict[str, float],
    latest_price_map: dict[str, float],
    adapter_status: dict,
    max_notional: float,
    equity: float,
    total_gross_exposure: float,
    max_position_weight_pct: float,
    max_total_gross_exposure_pct: float,
) -> tuple[str, float, float, str] | None:
    ranked_symbols = _ranked_candidate_symbols(tournament, candidates)
    max_position_value = equity * (max_position_weight_pct / 100.0) if max_position_weight_pct > 0 else float("inf")
    max_gross_value = equity * (max_total_gross_exposure_pct / 100.0) if max_total_gross_exposure_pct > 0 else float("inf")
    for symbol in ranked_symbols:
        estimated_price = float(latest_price_map.get(symbol, 0.0) or 0.0)
        if estimated_price <= 0:
            continue
        current_position_value = max(float(positions.get(symbol, 0.0) or 0.0), 0.0) * estimated_price
        if current_position_value + estimated_price > max_position_value:
            continue
        if total_gross_exposure + estimated_price > max_gross_value:
            continue
        if estimated_price > max_notional:
            continue
        if cash < _estimated_buy_cash_required(estimated_price, quantity=1.0, adapter_status=adapter_status):
            continue
        strategy_id = _strategy_id_for_symbol(tournament, symbol) or f"fixture_momentum_{symbol}"
        return str(symbol), estimated_price, 1.0, strategy_id
    return None


def _ranked_candidate_symbols(tournament: dict, candidates: list[dict]) -> list[str]:
    ranked: list[str] = []
    for candidate in tournament.get("candidates", []):
        symbol = candidate.get("symbol")
        if symbol and symbol not in ranked:
            ranked.append(str(symbol))
    for candidate in candidates:
        symbol = candidate.get("symbol")
        if symbol and symbol not in ranked:
            ranked.append(str(symbol))
    return ranked


def _strategy_id_for_symbol(tournament: dict, symbol: str) -> str | None:
    for candidate in tournament.get("candidates", []):
        if candidate.get("symbol") == symbol:
            return str(candidate.get("strategy_id"))
    winner = tournament.get("winner") or {}
    if winner.get("symbol") == symbol:
        return str(winner.get("strategy_id"))
    return None


if __name__ == "__main__":
    main()
