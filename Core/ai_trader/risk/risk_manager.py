from typing import List

from ..models import Signal, AccountInfo, Position, MarketSnapshot, Order, Instrument


class RiskManager:
    def __init__(self, max_risk_pct: float, max_position_pct: float) -> None:
        self.max_risk_pct = max_risk_pct
        self.max_position_pct = max_position_pct

    def apply(
        self,
        signals: List[Signal],
        account: AccountInfo,
        positions: List[Position],
        market: List[MarketSnapshot],
        instruments: List[Instrument],
    ) -> List[Order]:
        orders: List[Order] = []
        if account.equity <= 0:
            return orders

        inst_type_map = {i.inst_id: i.inst_type for i in instruments}

        for s in signals:
            if s.action == "hold":
                continue

            price = next((m.last_price for m in market if m.symbol == s.symbol), None)
            if price is None:
                continue

            max_position_value = account.equity * self.max_position_pct
            quantity = max_position_value / price

            orders.append(
                Order(
                    symbol=s.symbol,
                    side="buy" if s.action == "buy" else "sell",
                    quantity=quantity,
                    stop_loss=s.stop_loss,
                    take_profit=s.take_profit,
                    meta={
                        "tdMode": "cash" if inst_type_map.get(s.symbol) == "SPOT" else "cross",
                    },
                )
            )

        return orders
