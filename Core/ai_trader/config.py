import os
from dotenv import load_dotenv
from dataclasses import dataclass
from typing import List


def _get_bool(value: str, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y"}


@dataclass
class Settings:
    okx_base_url: str
    okx_api_key: str
    okx_api_secret: str
    okx_api_passphrase: str
    okx_inst_types: List[str]
    okx_inst_limit: int
    okx_use_proxy: bool
    okx_proxy_url: str
    use_websocket: bool
    okx_ws_public: str
    okx_ws_private: str

    llm_provider: str
    llm_model: str
    llm_api_key: str
    llm_base_url: str
    llm_use_proxy: bool
    llm_proxy_url: str

    trading_symbols: List[str]
    max_risk_pct: float
    max_position_pct: float
    paper_trading: bool

    trailing_stop_pct: float
    take_profit_pct: float
    state_store_path: str
    min_profit_to_trail_pct: float
    stop_by_llm: bool
    vol_window: int
    vol_threshold: float
    use_bbo: bool
    max_spread_pct: float
    analysis_log_path: str
    kline_timeframes: List[str]
    kline_limit: int
    fail_on_llm_error: bool
    llm_retries: int
    llm_retry_backoff: float
    llm_timeout_sec: int
    memory_path: str
    action_guard_enabled: bool
    action_guard_path: str
    action_cooldown_sec: int
    action_override_confidence: float

    poll_interval_sec: int = 15
    journal_path: str = "data/trades.jsonl"


def load_settings() -> Settings:
    load_dotenv()
    symbols = os.getenv("TRADING_SYMBOLS", "").split(",")
    symbols = [s.strip() for s in symbols if s.strip()]

    return Settings(
        okx_base_url=os.getenv("OKX_BASE_URL", ""),
        okx_api_key=os.getenv("OKX_API_KEY", ""),
        okx_api_secret=os.getenv("OKX_API_SECRET", ""),
        okx_api_passphrase=os.getenv("OKX_API_PASSPHRASE", ""),
        okx_inst_types=[s.strip() for s in os.getenv("OKX_INST_TYPES", "SPOT,SWAP").split(",") if s.strip()],
        okx_inst_limit=int(os.getenv("OKX_INST_LIMIT", "50")),
        okx_use_proxy=_get_bool(os.getenv("OKX_USE_PROXY", "false"), False),
        okx_proxy_url=os.getenv("OKX_PROXY_URL", ""),
        use_websocket=_get_bool(os.getenv("USE_WEBSOCKET", "false"), False),
        okx_ws_public=os.getenv("OKX_WS_PUBLIC", "wss://ws.okx.com:8443/ws/v5/public"),
        okx_ws_private=os.getenv("OKX_WS_PRIVATE", "wss://ws.okx.com:8443/ws/v5/private"),
        llm_provider=os.getenv("LLM_PROVIDER", "openai").strip().lower(),
        llm_model=os.getenv("LLM_MODEL", "gpt-4.1"),
        llm_api_key=os.getenv("LLM_API_KEY", ""),
        llm_base_url=os.getenv("LLM_BASE_URL", ""),
        llm_use_proxy=_get_bool(os.getenv("LLM_USE_PROXY", "true"), True),
        llm_proxy_url=os.getenv("LLM_PROXY_URL", ""),
        trading_symbols=symbols,
        max_risk_pct=float(os.getenv("MAX_RISK_PCT", "0.01")),
        max_position_pct=float(os.getenv("MAX_POSITION_PCT", "0.2")),
        paper_trading=_get_bool(os.getenv("PAPER_TRADING", "true"), True),
        trailing_stop_pct=float(os.getenv("TRAILING_STOP_PCT", "0.02")),
        take_profit_pct=float(os.getenv("TAKE_PROFIT_PCT", "0.04")),
        state_store_path=os.getenv("STATE_STORE_PATH", "data/position_state.json"),
        min_profit_to_trail_pct=float(os.getenv("MIN_PROFIT_TO_TRAIL_PCT", "0.01")),
        stop_by_llm=_get_bool(os.getenv("STOP_BY_LLM", "false"), False),
        vol_window=int(os.getenv("VOL_WINDOW", "20")),
        vol_threshold=float(os.getenv("VOL_THRESHOLD", "0.05")),
        use_bbo=_get_bool(os.getenv("USE_BBO", "true"), True),
        max_spread_pct=float(os.getenv("MAX_SPREAD_PCT", "0.002")),
        analysis_log_path=os.getenv("ANALYSIS_LOG_PATH", "data/analysis.log"),
        kline_timeframes=[s.strip() for s in os.getenv("KLINE_TIMEFRAMES", "1m,5m,15m,1h,4h").split(",") if s.strip()],
        kline_limit=int(os.getenv("KLINE_LIMIT", "50")),
        fail_on_llm_error=_get_bool(os.getenv("FAIL_ON_LLM_ERROR", "true"), True),
        llm_retries=int(os.getenv("LLM_RETRIES", "2")),
        llm_retry_backoff=float(os.getenv("LLM_RETRY_BACKOFF", "1.5")),
        llm_timeout_sec=int(os.getenv("LLM_TIMEOUT_SEC", "60")),
        memory_path=os.getenv("MEMORY_PATH", "data/llm_memory.txt"),
        action_guard_enabled=_get_bool(os.getenv("ACTION_GUARD_ENABLED", "true"), True),
        action_guard_path=os.getenv("ACTION_GUARD_PATH", "data/action_state.json"),
        action_cooldown_sec=int(os.getenv("ACTION_COOLDOWN_SEC", "120")),
        action_override_confidence=float(os.getenv("ACTION_OVERRIDE_CONFIDENCE", "0.8")),
    )
