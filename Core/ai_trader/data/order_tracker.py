from typing import Dict, Any


class OrderTracker:
    def __init__(self) -> None:
        self._orders: Dict[str, Dict[str, Any]] = {}

    def update(self, event: Dict[str, Any]) -> None:
        ord_id = event.get("ordId") or event.get("clOrdId")
        if not ord_id:
            return
        self._orders[ord_id] = event

    def get(self, ord_id: str) -> Dict[str, Any]:
        return self._orders.get(ord_id, {})
