"""
Binance Data Collectors (WebSocket + REST)
Uses latest 2025 API endpoints from https://developers.binance.com
"""

import json
import time
import threading
import websocket
import requests
from datetime import datetime
from typing import Dict, Any, Optional


class BinanceWebSocketCollector:
    """
    Binance WebSocket collector for real-time data
    No API key needed for public market data streams
    """
    
    def __init__(self, symbol: str = "btcusdt", proxy_manager=None):
        self.symbol = symbol.lower()
        self.proxy_manager = proxy_manager
        self.ws = None
        self.running = False
        self.lock = threading.Lock()
        
        # Latest data storage
        self.latest_data = {
            "symbol": symbol.upper(),
            "timestamp": None,
            "close": None,
            "volume": None,
            "trade_count": 0,
            "bid_ask_spread": None,
            "ob_imbalance_5": None,
            "bid_price_1": None,
            "ask_price_1": None,
            "bid_qty_1": None,
            "bid_qty_2": None,
            "bid_qty_3": None,
            "ask_qty_1": None,
            "ask_qty_2": None,
            "ask_qty_3": None
        }
        
        print(f"✅ BinanceWebSocketCollector initialized for {symbol.upper()}")
    
    def run(self):
        """Start WebSocket connections"""
        self.running = True
        
        # Combine multiple streams into one connection
        # Latest 2025 format: wss://stream.binance.com:9443/ws/<stream1>/<stream2>/...
        streams = [
            f"{self.symbol}@aggTrade",  # Aggregate trades
            f"{self.symbol}@depth5@100ms",  # Order book depth (top 5, 100ms updates)
            f"{self.symbol}@ticker"  # 24hr ticker
        ]
        
        # URL-encoded format (supported as of Nov 2025)
        url = f"wss://stream.binance.com:9443/stream?streams={'/'.join(streams)}"
        
        print(f"🔌 Connecting to Binance WebSocket: {url}")
        
        def on_message(ws, message):
            try:
                data = json.loads(message)
                stream_name = data.get('stream', '')
                stream_data = data.get('data', {})
                
                # Handle different stream types
                if '@aggTrade' in stream_name:
                    self._handle_trade(stream_data)
                elif '@depth' in stream_name:
                    self._handle_depth(stream_data)
                elif '@ticker' in stream_name:
                    self._handle_ticker(stream_data)
                    
            except Exception as e:
                print(f"❌ WebSocket message error: {e}")
        
        def on_error(ws, error):
            print(f"❌ WebSocket error: {error}")
        
        def on_close(ws, close_status_code, close_msg):
            print(f"⚠️  WebSocket closed: {close_status_code} - {close_msg}")
            if self.running:
                print("🔄 Reconnecting in 5 seconds...")
                time.sleep(5)
                self.run()  # Reconnect
        
        def on_open(ws):
            print(f"✅ Binance WebSocket connected for {self.symbol.upper()}")
        
        # Create WebSocket connection
        self.ws = websocket.WebSocketApp(
            url,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close,
            on_open=on_open
        )
        
        # Run forever (blocking call)
        self.ws.run_forever()
    
    def _handle_trade(self, data: Dict):
        """Handle aggregate trade data"""
        with self.lock:
            self.latest_data["close"] = float(data.get('p', 0))  # Price
            self.latest_data["volume"] = float(data.get('q', 0))  # Quantity
            self.latest_data["timestamp"] = datetime.fromtimestamp(data.get('T', 0) / 1000)
            self.latest_data["trade_count"] += 1
    
    def _handle_depth(self, data: Dict):
        """Handle order book depth data"""
        with self.lock:
            bids = data.get('bids', [])
            asks = data.get('asks', [])
            
            if bids and asks:
                # Calculate bid-ask spread
                best_bid = float(bids[0][0]) if bids else 0
                best_ask = float(asks[0][0]) if asks else 0
                self.latest_data["bid_ask_spread"] = best_ask - best_bid
                self.latest_data["bid_price_1"] = best_bid
                self.latest_data["ask_price_1"] = best_ask
                
                # Order book imbalance (top 5 levels)
                bid_volume = sum([float(b[1]) for b in bids[:5]])
                ask_volume = sum([float(a[1]) for a in asks[:5]])
                total = bid_volume + ask_volume
                if total > 0:
                    self.latest_data["ob_imbalance_5"] = (bid_volume - ask_volume) / total
                
                # Store quantities
                self.latest_data["bid_qty_1"] = float(bids[0][1]) if len(bids) > 0 else None
                self.latest_data["bid_qty_2"] = float(bids[1][1]) if len(bids) > 1 else None
                self.latest_data["bid_qty_3"] = float(bids[2][1]) if len(bids) > 2 else None
                self.latest_data["ask_qty_1"] = float(asks[0][1]) if len(asks) > 0 else None
                self.latest_data["ask_qty_2"] = float(asks[1][1]) if len(asks) > 1 else None
                self.latest_data["ask_qty_3"] = float(asks[2][1]) if len(asks) > 2 else None
    
    def _handle_ticker(self, data: Dict):
        """Handle 24hr ticker data"""
        with self.lock:
            self.latest_data["volume"] = float(data.get('v', 0))  # 24hr volume
            self.latest_data["vwap"] = float(data.get('w', 0))  # VWAP
            self.latest_data["open"] = float(data.get('o', 0))
            self.latest_data["high"] = float(data.get('h', 0))
            self.latest_data["low"] = float(data.get('l', 0))
            self.latest_data["close"] = float(data.get('c', 0))
            self.latest_data["trade_count"] = int(data.get('n', 0))
    
    def get_snapshot(self) -> Dict[str, Any]:
        """Get current data snapshot"""
        with self.lock:
            return self.latest_data.copy()
    
    def stop(self):
        """Stop WebSocket connection"""
        self.running = False
        if self.ws:
            self.ws.close()
            print(f"✅ Binance WebSocket stopped for {self.symbol.upper()}")


class BinanceRESTCollector:
    """
    Binance REST API collector for futures data
    Uses latest 2025 endpoints
    """
    
    def __init__(self, symbol: str = "BTCUSDT", key_manager=None):
        self.symbol = symbol.upper()
        self.key_manager = key_manager
        self.base_url_futures = "https://fapi.binance.com"
        
        self.latest_data = {
            "symbol": symbol.upper(),
            "funding_rate": None,
            "open_interest": None,
            "long_short_ratio": None
        }
        
        print(f"✅ BinanceRESTCollector initialized for {symbol}")
    
    def fetch_funding_rate(self) -> Optional[float]:
        """
        Fetch current funding rate
        Endpoint: GET /fapi/v1/fundingRate (public, no auth needed)
        """
        try:
            url = f"{self.base_url_futures}/fapi/v1/fundingRate"
            params = {"symbol": self.symbol, "limit": 1}
            
            # Use proxy if available
            proxies = self.key_manager.get_proxy_dict() if self.key_manager else None
            
            response = requests.get(url, params=params, proxies=proxies, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            if data and len(data) > 0:
                funding_rate = float(data[0].get('fundingRate', 0))
                self.latest_data["funding_rate"] = funding_rate
                return funding_rate
                
        except Exception as e:
            print(f"⚠️  Failed to fetch funding rate: {e}")
        return None
    
    def fetch_open_interest(self) -> Optional[float]:
        """
        Fetch open interest
        Endpoint: GET /fapi/v1/openInterest (public, no auth needed)
        """
        try:
            url = f"{self.base_url_futures}/fapi/v1/openInterest"
            params = {"symbol": self.symbol}
            
            proxies = self.key_manager.get_proxy_dict() if self.key_manager else None
            
            response = requests.get(url, params=params, proxies=proxies, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            open_interest = float(data.get('openInterest', 0))
            self.latest_data["open_interest"] = open_interest
            return open_interest
                
        except Exception as e:
            print(f"⚠️  Failed to fetch open interest: {e}")
        return None
    
    def fetch_long_short_ratio(self) -> Optional[float]:
        """
        Fetch top trader long/short ratio
        Endpoint: GET /futures/data/topLongShortAccountRatio (public)
        """
        try:
            url = f"{self.base_url_futures}/futures/data/topLongShortAccountRatio"
            params = {"symbol": self.symbol, "period": "5m", "limit": 1}
            
            proxies = self.key_manager.get_proxy_dict() if self.key_manager else None
            
            response = requests.get(url, params=params, proxies=proxies, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            if data and len(data) > 0:
                ratio = float(data[0].get('longShortRatio', 0))
                self.latest_data["long_short_ratio"] = ratio
                return ratio
                
        except Exception as e:
            print(f"⚠️  Failed to fetch long/short ratio: {e}")
        return None
    
    def get_snapshot(self) -> Dict[str, Any]:
        """Get all futures data"""
        return self.latest_data.copy()
