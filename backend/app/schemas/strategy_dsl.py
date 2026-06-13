from __future__ import annotations

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field, model_validator


class AssetClass(str, Enum):
    stock = "stock"
    etf = "etf"
    cash = "cash"
    crypto_spot_paper = "crypto_spot_paper"


class RebalanceFrequency(str, Enum):
    daily = "daily"
    weekly = "weekly"
    monthly = "monthly"
    quarterly = "quarterly"


class Signal(BaseModel):
    type: str
    lookback_days: Optional[int] = Field(default=None, ge=2, le=756)


class PortfolioRules(BaseModel):
    max_positions: int = Field(default=2, ge=1, le=50)
    max_weight_per_asset: float = Field(default=0.5, gt=0, le=1)
    cash_if_no_signal: bool = True


class RiskRules(BaseModel):
    max_drawdown_pct: float = Field(default=10, ge=1, le=100)
    no_leverage: bool = True
    no_short: bool = True
    no_options: bool = True
    no_crypto_withdrawal: bool = True

    @model_validator(mode="after")
    def enforce_mvp_safety(self) -> "RiskRules":
        if not self.no_leverage:
            raise ValueError("MVP 禁止使用杠杆")
        if not self.no_short:
            raise ValueError("MVP 禁止卖空")
        if not self.no_options:
            raise ValueError("MVP 禁止期权")
        if not self.no_crypto_withdrawal:
            raise ValueError("MVP 禁止加密货币提现")
        return self


class StrategyDSL(BaseModel):
    name: str = Field(min_length=3)
    asset_class: AssetClass
    universe: List[str] = Field(min_length=1)
    timeframe: str = "1d"
    rebalance_frequency: RebalanceFrequency
    signals: List[Signal] = Field(min_length=1)
    portfolio: PortfolioRules = Field(default_factory=PortfolioRules)
    risk: RiskRules = Field(default_factory=RiskRules)

    @model_validator(mode="after")
    def validate_universe(self) -> "StrategyDSL":
        clean = [s.strip().upper() for s in self.universe if s.strip()]
        if len(clean) != len(set(clean)):
            raise ValueError("标的列表不能重复")
        if self.asset_class == AssetClass.crypto_spot_paper and not self.risk.no_crypto_withdrawal:
            raise ValueError("MVP 禁止加密货币提现")
        self.universe = clean
        return self


def validate_strategy(payload: dict) -> StrategyDSL:
    return StrategyDSL.model_validate(payload)
