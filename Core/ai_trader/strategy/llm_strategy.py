import json
from typing import List

from .base import Strategy
from ..models import Signal, MarketSnapshot, AccountInfo, Position, Instrument, Candle


class LLMStrategy(Strategy):
    def __init__(self, llm_client) -> None:
        self.llm = llm_client

    def generate_signals(
        self,
        market: List[MarketSnapshot],
        account: AccountInfo,
        positions: List[Position],
        instruments: List[Instrument],
        candles: dict,
        last_thoughts: str,
    ) -> List[Signal]:
        # 这里调用 LLM，当前为占位实现
        return self.llm.generate(market, account, positions, instruments, candles, last_thoughts)
