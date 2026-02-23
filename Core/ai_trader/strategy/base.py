from abc import ABC, abstractmethod
from typing import List

from ..models import Signal, MarketSnapshot, AccountInfo, Position, Instrument, Candle


class Strategy(ABC):
    @abstractmethod
    def generate_signals(
        self,
        market: List[MarketSnapshot],
        account: AccountInfo,
        positions: List[Position],
        instruments: List[Instrument],
        candles: dict,
        last_thoughts: str,
    ) -> List[Signal]:
        raise NotImplementedError
