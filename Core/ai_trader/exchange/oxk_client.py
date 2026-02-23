import base64
import hashlib
import hmac
import json
import logging
import time
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

import requests

from ..models import AccountInfo, Position, MarketSnapshot, Order, Instrument, Candle


class OKXClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        api_secret: str,
        passphrase: str,
        use_proxy: bool = False,
        proxy_url: str = "",
        ws_client=None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.api_secret = api_secret
        self.passphrase = passphrase
        self.use_proxy = use_proxy
        self.proxy_url = proxy_url
        self.ws_client = ws_client
        self.logger = logging.getLogger("OKXClient")

    def _timestamp(self) -> str:
        return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")

    def _sign(self, timestamp: str, method: str, path: str, body: str) -> str:
        message = f"{timestamp}{method}{path}{body}"
        mac = hmac.new(self.api_secret.encode("utf-8"), message.encode("utf-8"), hashlib.sha256)
        return base64.b64encode(mac.digest()).decode("utf-8")

    def _headers(self, signature: str, timestamp: str) -> dict:
        return {
            "OK-ACCESS-KEY": self.api_key,
            "OK-ACCESS-SIGN": signature,
            "OK-ACCESS-TIMESTAMP": timestamp,
            "OK-ACCESS-PASSPHRASE": self.passphrase,
            "Content-Type": "application/json",
        }

    def _request(self, method: str, path: str, params: Optional[Dict[str, Any]] = None, body: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        method = method.upper()
        params = params or {}
        body = body or {}

        query = ""
        if params:
            query = "?" + "&".join(f"{k}={v}" for k, v in params.items())

        body_str = json.dumps(body) if method in {"POST", "PUT"} else ""
        request_path = f"{path}{query}"
        timestamp = self._timestamp()
        sign = self._sign(timestamp, method, request_path, body_str)
        headers = self._headers(sign, timestamp)
        proxies = self._get_proxies()

        url = f"{self.base_url}{request_path}"
        last_exc: Exception | None = None
        for attempt in range(3):
            try:
                resp = requests.request(
                    method,
                    url,
                    headers=headers,
                    data=body_str if body_str else None,
                    timeout=30,
                    proxies=proxies,
                )
                resp.raise_for_status()
                return resp.json()
            except Exception as exc:
                last_exc = exc
                self.logger.warning("OKX request failed (attempt %s): %s", attempt + 1, exc)
                time.sleep(1 + attempt)
        raise last_exc

    def _get_proxies(self) -> dict | None:
        if not self.use_proxy:
            return {"http": None, "https": None}
        if self.proxy_url:
            return {"http": self.proxy_url, "https": self.proxy_url}
        return None

    def get_instruments(self, inst_types: List[str], limit: int) -> List[Instrument]:
        instruments: List[Instrument] = []
        for inst_type in inst_types:
            data = self._request("GET", "/api/v5/public/instruments", params={"instType": inst_type})
            for item in data.get("data", [])[:limit]:
                instruments.append(
                    Instrument(
                        inst_id=item.get("instId", ""),
                        inst_type=item.get("instType", ""),
                        inst_family=item.get("instFamily", ""),
                        base_ccy=item.get("baseCcy", ""),
                        quote_ccy=item.get("quoteCcy", ""),
                        tick_sz=item.get("tickSz", ""),
                        lot_sz=item.get("lotSz", ""),
                    )
                )
        return instruments

    def get_account_info(self) -> AccountInfo:
        if self.ws_client:
            ws_account = self.ws_client.get_account()
            if ws_account:
                total_eq = ws_account.get("totalEq", "0")
                avail_eq = ws_account.get("availEq", "0")
                return AccountInfo(
                    balance=float(total_eq or 0),
                    equity=float(total_eq or 0),
                    available=float(avail_eq or 0),
                )

        data = self._request("GET", "/api/v5/account/balance")
        details = data.get("data", [{}])[0].get("details", [])
        total_eq = data.get("data", [{}])[0].get("totalEq", "0")
        avail_eq = data.get("data", [{}])[0].get("availEq", "0")
        balance = float(total_eq or 0)
        equity = float(total_eq or 0)
        available = float(avail_eq or 0)
        if details and available == 0:
            available = float(details[0].get("availEq") or details[0].get("availBal") or 0)
        return AccountInfo(balance=balance, equity=equity, available=available)

    def get_positions(self) -> List[Position]:
        if self.ws_client:
            ws_positions = self.ws_client.get_positions()
            if ws_positions:
                return [
                    Position(
                        symbol=item.get("instId", ""),
                        quantity=float(item.get("pos", 0) or 0),
                        entry_price=float(item.get("avgPx", 0) or 0),
                        side=item.get("posSide", "long") or "long",
                        mgn_mode=item.get("mgnMode"),
                        margin=float(item.get("margin", 0) or 0),
                        mmr=float(item.get("mmr", 0) or 0),
                    )
                    for item in ws_positions
                ]

        data = self._request("GET", "/api/v5/account/positions")
        positions: List[Position] = []
        for item in data.get("data", []):
            positions.append(
                Position(
                    symbol=item.get("instId", ""),
                    quantity=float(item.get("pos", 0) or 0),
                    entry_price=float(item.get("avgPx", 0) or 0),
                    side=item.get("posSide", "long") or "long",
                    mgn_mode=item.get("mgnMode"),
                    margin=float(item.get("margin", 0) or 0),
                    mmr=float(item.get("mmr", 0) or 0),
                )
            )
        return positions

    def get_market_snapshot(self, symbol: str) -> MarketSnapshot:
        if self.ws_client:
            ticker = self.ws_client.get_ticker(symbol)
            if ticker:
                return MarketSnapshot(
                    symbol=symbol,
                    last_price=float(ticker.get("last", 0) or 0),
                    bid=float(ticker.get("bidPx", 0) or 0),
                    ask=float(ticker.get("askPx", 0) or 0),
                    timestamp=ticker.get("ts", ""),
                )

        data = self._request("GET", "/api/v5/market/ticker", params={"instId": symbol})
        item = data.get("data", [{}])[0]
        return MarketSnapshot(
            symbol=symbol,
            last_price=float(item.get("last", 0) or 0),
            bid=float(item.get("bidPx", 0) or 0),
            ask=float(item.get("askPx", 0) or 0),
            timestamp=item.get("ts", ""),
        )

    def get_best_bid_ask(self, symbol: str) -> Optional[Dict[str, float]]:
        if not self.ws_client:
            return None
        bbo = self.ws_client.get_bbo(symbol)
        if not bbo:
            return None
        return {
            "bid": float(bbo.get("bidPx", 0) or 0),
            "ask": float(bbo.get("askPx", 0) or 0),
        }

    def get_candles(self, symbol: str, bar: str, limit: int) -> List[Candle]:
        data = self._request(
            "GET",
            "/api/v5/market/candles",
            params={"instId": symbol, "bar": bar, "limit": str(limit)},
        )
        candles: List[Candle] = []
        for item in data.get("data", []):
            candles.append(
                Candle(
                    ts=int(item[0]),
                    o=float(item[1]),
                    h=float(item[2]),
                    l=float(item[3]),
                    c=float(item[4]),
                    vol=float(item[5]),
                )
            )
        return candles

    def place_order(self, order: Order) -> dict:
        td_mode = "cross"
        if order.meta and order.meta.get("tdMode"):
            td_mode = order.meta["tdMode"]
        else:
            td_mode = "cash" if order.symbol.count("-") == 1 else "cross"

        body = {
            "instId": order.symbol,
            "tdMode": td_mode,
            "side": order.side,
            "ordType": order.order_type,
            "sz": str(order.quantity),
        }
        if order.price is not None:
            body["px"] = str(order.price)
        if order.meta and order.meta.get("reduceOnly"):
            body["reduceOnly"] = True

        self.logger.info("Placing order: %s", body)
        return self._request("POST", "/api/v5/trade/order", body=body)

    def cancel_order(self, order_id: str) -> dict:
        body = {"ordId": order_id}
        return self._request("POST", "/api/v5/trade/cancel-order", body=body)

    def get_open_orders(self) -> List[dict]:
        data = self._request("GET", "/api/v5/trade/orders-pending")
        return data.get("data", [])
