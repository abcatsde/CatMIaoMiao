from typing import List, Dict, Any

from ..models import Position, MarketSnapshot, Order, Signal


class StopManager:
    def __init__(self, trailing_stop_pct: float, take_profit_pct: float, min_profit_to_trail_pct: float, state_store) -> None:
        self.trailing_stop_pct = trailing_stop_pct
        self.take_profit_pct = take_profit_pct
        self.min_profit_to_trail_pct = min_profit_to_trail_pct
        self.state_store = state_store

    def update_stops(
        self,
        positions: List[Position],
        market: List[MarketSnapshot],
        signals: List[Signal] | None = None,
        manage_by_llm: bool = False,
    ) -> List[Dict[str, Any]]:
        state = self.state_store.load()
        updates: List[Dict[str, Any]] = []
        price_map = {m.symbol: m.last_price for m in market}

        if manage_by_llm and signals:
            signal_map = {s.symbol: s for s in signals}
        else:
            signal_map = {}

        for pos in positions:
            if pos.quantity == 0:
                continue

            price = price_map.get(pos.symbol)
            if price is None or price <= 0:
                continue

            if manage_by_llm:
                sig = signal_map.get(pos.symbol)
                intent = (sig.protect_intent or "").lower() if sig else ""
                if intent != "strong":
                    continue
                if not sig or (sig.stop_loss is None and sig.take_profit is None):
                    continue
                new_stop = sig.stop_loss
                new_take = sig.take_profit
                profit_pct = None
            else:
                if pos.entry_price and pos.entry_price > 0:
                    if pos.side == "short":
                        profit_pct = (pos.entry_price - price) / pos.entry_price
                    else:
                        profit_pct = (price - pos.entry_price) / pos.entry_price
                else:
                    profit_pct = 0.0

                if profit_pct < self.min_profit_to_trail_pct:
                    continue

            key = pos.symbol
            entry = state.get(key, {})
            stop = entry.get("stop_loss")
            take = entry.get("take_profit")

            if not manage_by_llm:
                if pos.side == "short":
                    new_stop = min(stop, price * (1 + self.trailing_stop_pct)) if stop else price * (1 + self.trailing_stop_pct)
                    new_take = min(take, price * (1 - self.take_profit_pct)) if take else price * (1 - self.take_profit_pct)
                else:
                    new_stop = max(stop, price * (1 - self.trailing_stop_pct)) if stop else price * (1 - self.trailing_stop_pct)
                    new_take = max(take, price * (1 + self.take_profit_pct)) if take else price * (1 + self.take_profit_pct)

            if stop != new_stop or take != new_take:
                state[key] = {
                    "stop_loss": new_stop,
                    "take_profit": new_take,
                    "side": pos.side,
                    "profit_pct": profit_pct,
                }
                updates.append({"symbol": key, "stop_loss": new_stop, "take_profit": new_take})

        self.state_store.save(state)
        return updates

    def check_exits(self, positions: List[Position], market: List[MarketSnapshot]) -> List[Order]:
        state = self.state_store.load()
        price_map = {m.symbol: m.last_price for m in market}
        exit_orders: List[Order] = []

        for pos in positions:
            if pos.quantity == 0:
                continue

            price = price_map.get(pos.symbol)
            if price is None or price <= 0:
                continue

            entry = state.get(pos.symbol, {})
            stop = entry.get("stop_loss")
            take = entry.get("take_profit")

            if pos.side == "short":
                hit_stop = stop is not None and price >= stop
                hit_take = take is not None and price <= take
                side = "buy"
            else:
                hit_stop = stop is not None and price <= stop
                hit_take = take is not None and price >= take
                side = "sell"

            if hit_stop or hit_take:
                exit_orders.append(
                    Order(
                        symbol=pos.symbol,
                        side=side,
                        quantity=abs(pos.quantity),
                        order_type="market",
                        meta={"reduceOnly": True},
                    )
                )

        return exit_orders
