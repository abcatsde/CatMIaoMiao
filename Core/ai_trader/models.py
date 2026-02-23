from dataclasses import dataclass
from typing import Optional, Dict, Any, List


@dataclass
class AccountInfo:
    balance: float
    equity: float
    available: float


@dataclass
class Position:
    symbol: str
    quantity: float
    entry_price: float
    side: str  # long/short
    mgn_mode: Optional[str] = None
    margin: Optional[float] = None
    mmr: Optional[float] = None


@dataclass
class MarketSnapshot:
    symbol: str
    last_price: float
    bid: float
    ask: float
    timestamp: str


@dataclass
class Instrument:
    inst_id: str
    inst_type: str
    inst_family: str
    base_ccy: str
    quote_ccy: str
    tick_sz: str
    lot_sz: str


@dataclass
class Candle:
    ts: int
    o: float
    h: float
    l: float
    c: float
    vol: float


@dataclass
class Plan:
    symbols: List[str]
    timeframes: List[str]
    notes: str
    include_account: bool = False
    include_positions: bool = False


@dataclass
class Signal:
    symbol: str
    action: str  # buy/sell/hold
    confidence: float
    reason: str
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    timeframes: Optional[List[str]] = None
    protect_intent: Optional[str] = None


@dataclass
class Order:
    symbol: str
    side: str  # buy/sell
    quantity: float
    order_type: str = "market"
    price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    meta: Optional[Dict[str, Any]] = None
