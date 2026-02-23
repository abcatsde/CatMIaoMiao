import base64
import hashlib
import hmac
import json
import logging
import threading
import time
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

import websocket


class OKXWebSocket:
    def __init__(
        self,
        public_url: str,
        private_url: str,
        api_key: str,
        api_secret: str,
        passphrase: str,
    ) -> None:
        self.public_url = public_url
        self.private_url = private_url
        self.api_key = api_key
        self.api_secret = api_secret
        self.passphrase = passphrase

        self.logger = logging.getLogger("OKXWebSocket")
        self._public_ws: Optional[websocket.WebSocketApp] = None
        self._private_ws: Optional[websocket.WebSocketApp] = None
        self._public_thread: Optional[threading.Thread] = None
        self._private_thread: Optional[threading.Thread] = None

        self._tickers: Dict[str, Dict[str, Any]] = {}
        self._bbo: Dict[str, Dict[str, Any]] = {}
        self._account: Dict[str, Any] = {}
        self._positions: List[Dict[str, Any]] = []
        self._order_events: List[Dict[str, Any]] = []
        self._lock = threading.Lock()

        self._inst_ids: List[str] = []
        self._running = False
        self._ping_thread: Optional[threading.Thread] = None
        self._reconnect_delay = 5

    def _timestamp(self) -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")

    def _sign(self, timestamp: str, method: str, path: str, body: str) -> str:
        message = f"{timestamp}{method}{path}{body}"
        mac = hmac.new(self.api_secret.encode("utf-8"), message.encode("utf-8"), hashlib.sha256)
        return base64.b64encode(mac.digest()).decode("utf-8")

    def start(self, inst_ids: List[str]) -> None:
        if self._running:
            return
        self._running = True
        self._inst_ids = inst_ids

        self._public_thread = threading.Thread(target=self._run_public_loop, daemon=True)
        self._private_thread = threading.Thread(target=self._run_private_loop, daemon=True)
        self._public_thread.start()
        self._private_thread.start()

        self._ping_thread = threading.Thread(target=self._ping_loop, daemon=True)
        self._ping_thread.start()

    def stop(self) -> None:
        self._running = False
        if self._public_ws:
            self._public_ws.close()
        if self._private_ws:
            self._private_ws.close()

    def _run_public_loop(self) -> None:
        while self._running:
            try:
                self._public_ws = websocket.WebSocketApp(
                    self.public_url,
                    on_open=self._on_public_open,
                    on_message=self._on_public_message,
                    on_error=self._on_public_error,
                    on_close=self._on_public_close,
                )
                self._public_ws.run_forever(ping_interval=20, ping_timeout=10)
            except Exception as exc:
                self.logger.warning("Public WS loop error: %s", exc)
            if self._running:
                time.sleep(self._reconnect_delay)

    def _run_private_loop(self) -> None:
        while self._running:
            try:
                self._private_ws = websocket.WebSocketApp(
                    self.private_url,
                    on_open=self._on_private_open,
                    on_message=self._on_private_message,
                    on_error=self._on_private_error,
                    on_close=self._on_private_close,
                )
                self._private_ws.run_forever(ping_interval=20, ping_timeout=10)
            except Exception as exc:
                self.logger.warning("Private WS loop error: %s", exc)
            if self._running:
                time.sleep(self._reconnect_delay)

    def _on_public_open(self, ws):
        self.logger.info("Public WS connected")
        chunk_size = 20
        for i in range(0, len(self._inst_ids), chunk_size):
            args = [{"channel": "tickers", "instId": inst_id} for inst_id in self._inst_ids[i:i + chunk_size]]
            ws.send(json.dumps({"op": "subscribe", "args": args}))
            bbo_args = [{"channel": "bbo-tbt", "instId": inst_id} for inst_id in self._inst_ids[i:i + chunk_size]]
            ws.send(json.dumps({"op": "subscribe", "args": bbo_args}))

    def _on_public_message(self, ws, message: str):
        try:
            data = json.loads(message)
        except json.JSONDecodeError:
            return

        channel = data.get("arg", {}).get("channel")
        if "data" in data and channel == "tickers":
            for item in data.get("data", []):
                inst_id = item.get("instId")
                if inst_id:
                    with self._lock:
                        self._tickers[inst_id] = item
        elif "data" in data and channel == "bbo-tbt":
            for item in data.get("data", []):
                inst_id = item.get("instId")
                if inst_id:
                    with self._lock:
                        self._bbo[inst_id] = item

    def _on_public_error(self, ws, error):
        self.logger.warning("Public WS error: %s", error)

    def _on_public_close(self, ws, close_status_code, close_msg):
        self.logger.warning("Public WS closed: %s %s", close_status_code, close_msg)

    def _on_private_open(self, ws):
        self.logger.info("Private WS connected")
        ts = self._timestamp()
        sign = self._sign(ts, "GET", "/users/self/verify", "")
        login = {
            "op": "login",
            "args": [
                {
                    "apiKey": self.api_key,
                    "passphrase": self.passphrase,
                    "timestamp": ts,
                    "sign": sign,
                }
            ],
        }
        ws.send(json.dumps(login))

        subs = [
            {"channel": "account"},
            {"channel": "positions"},
            {"channel": "orders", "instType": "ANY"},
        ]
        ws.send(json.dumps({"op": "subscribe", "args": subs}))

    def _on_private_message(self, ws, message: str):
        try:
            data = json.loads(message)
        except json.JSONDecodeError:
            return

        channel = data.get("arg", {}).get("channel")
        if channel == "account":
            items = data.get("data", [])
            if items:
                with self._lock:
                    self._account = items[0]
        elif channel == "positions":
            with self._lock:
                self._positions = data.get("data", [])
        elif channel == "orders":
            with self._lock:
                self._order_events.extend(data.get("data", []))

    def _on_private_error(self, ws, error):
        self.logger.warning("Private WS error: %s", error)

    def _on_private_close(self, ws, close_status_code, close_msg):
        self.logger.warning("Private WS closed: %s %s", close_status_code, close_msg)

    def _ping_loop(self) -> None:
        while self._running:
            try:
                if self._public_ws:
                    self._public_ws.send("ping")
                if self._private_ws:
                    self._private_ws.send("ping")
            except Exception:
                pass
            time.sleep(20)

    def get_ticker(self, inst_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            return self._tickers.get(inst_id)

    def get_bbo(self, inst_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            return self._bbo.get(inst_id)

    def get_account(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self._account)

    def get_positions(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._positions)

    def consume_order_events(self) -> List[Dict[str, Any]]:
        with self._lock:
            events = list(self._order_events)
            self._order_events.clear()
            return events
