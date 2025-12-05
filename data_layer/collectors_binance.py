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
            "open": None,
            "high": None,
            "low": None,
            "close": None,
            "volume": None,
            "volume_buy": None,
            "volume_sell": None,
            "trade_count": 0,
            "vwap": None,
            "bid_ask_spread": None,
            "ob_imbalance_5": None,
            "ob_wall_bid": None,
            "ob_wall_ask": None,
            "flow_delta_1m": None,
            "flow_delta_5m": None,
            "large_trade_count": 0,
            "bid_price_1": None,
            "ask_price_1": None,
            "bid_qty_1": None,
            "bid_qty_2": None,
            "bid_qty_3": None,
            "ask_qty_1": None,
            "ask_qty_2": None,
            "ask_qty_3": None
        }
        
        # Flow tracking
        self.trade_history = []  # Track last 5 minutes of trades
        self.last_cleanup = time.time()
        
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
        
        # --- CRITICAL PROXY INJECTION ---
        proxy_kwargs = {}
        if self.proxy_manager:
            proxy = self.proxy_manager.get_proxy()
            if proxy:
                print(f"🔒 Using Proxy: {proxy['host']}:{proxy['port']}")
                proxy_kwargs = {
                    "http_proxy_host": proxy['host'],
                    "http_proxy_port": int(proxy['port']),
                    "http_proxy_auth": (proxy['username'], proxy['password']),
                    "proxy_type": "http"  # CRITICAL FIX: Explicit proxy type required
                }
        
        # Run forever (blocking call) with proxy support
        self.ws.run_forever(**proxy_kwargs)
    
    def _handle_trade(self, data: Dict):
        """Handle aggregate trade data"""
        with self.lock:
            price = float(data.get('p', 0))
            qty = float(data.get('q', 0))
            is_buyer = data.get('m', False)  # True = buyer is market maker (sell), False = buy
            timestamp = data.get('T', 0) / 1000
            
            self.latest_data["close"] = price
            self.latest_data["timestamp"] = datetime.fromtimestamp(timestamp)
            self.latest_data["trade_count"] += 1
            
            # Track buy/sell volume split
            if not is_buyer:  # Buyer is taker = buy volume
                self.latest_data["volume_buy"] = (self.latest_data.get("volume_buy") or 0) + qty
            else:  # Seller is taker = sell volume
                self.latest_data["volume_sell"] = (self.latest_data.get("volume_sell") or 0) + qty
            
            # Track for flow calculations
            now = time.time()
            self.trade_history.append({
                'time': now,
                'price': price,
                'qty': qty,
                'is_buy': not is_buyer
            })
            
            # Cleanup old trades (> 5 minutes)
            if now - self.last_cleanup > 60:  # Cleanup every minute
                cutoff = now - 300  # 5 minutes
                self.trade_history = [t for t in self.trade_history if t['time'] > cutoff]
                self.last_cleanup = now
            
            # Calculate flow deltas
            self._calculate_flow_delta()
            
            # Track large trades (> $100k)
            if price * qty > 100000:
                self.latest_data["large_trade_count"] += 1
    
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
                
                # Detect order book walls (large orders at single price)
                # Wall = order > 10x average of top 3 levels
                avg_bid_qty = bid_volume / min(5, len(bids)) if bids else 0
                avg_ask_qty = ask_volume / min(5, len(asks)) if asks else 0
                
                # Find largest bid wall
                max_bid_wall = 0
                for bid in bids[:5]:
                    qty = float(bid[1])
                    if qty > avg_bid_qty * 10:
                        max_bid_wall = max(max_bid_wall, qty)
                
                # Find largest ask wall
                max_ask_wall = 0
                for ask in asks[:5]:
                    qty = float(ask[1])
                    if qty > avg_ask_qty * 10:
                        max_ask_wall = max(max_ask_wall, qty)
                
                self.latest_data["ob_wall_bid"] = max_bid_wall if max_bid_wall > 0 else None
                self.latest_data["ob_wall_ask"] = max_ask_wall if max_ask_wall > 0 else None
    
    def _handle_ticker(self, data: Dict):
        """Handle 24hr ticker data"""
        with self.lock:
            # CRITICAL FIX: Preserve OHLC data from ticker
            self.latest_data["open"] = float(data.get('o', 0))
            self.latest_data["high"] = float(data.get('h', 0))
            self.latest_data["low"] = float(data.get('l', 0))
            self.latest_data["close"] = float(data.get('c', 0))
            self.latest_data["volume"] = float(data.get('v', 0))  # 24hr volume
            self.latest_data["vwap"] = float(data.get('w', 0))  # VWAP
            self.latest_data["trade_count"] = int(data.get('n', 0))
    
    def _calculate_flow_delta(self):
        """Calculate buy/sell flow delta over 1m and 5m windows"""
        now = time.time()
        
        # 1 minute flow
        cutoff_1m = now - 60
        trades_1m = [t for t in self.trade_history if t['time'] > cutoff_1m]
        if trades_1m:
            buy_vol_1m = sum(t['qty'] for t in trades_1m if t['is_buy'])
            sell_vol_1m = sum(t['qty'] for t in trades_1m if not t['is_buy'])
            total_1m = buy_vol_1m + sell_vol_1m
            self.latest_data["flow_delta_1m"] = (buy_vol_1m - sell_vol_1m) / total_1m if total_1m > 0 else 0
        
        # 5 minute flow
        cutoff_5m = now - 300
        trades_5m = [t for t in self.trade_history if t['time'] > cutoff_5m]
        if trades_5m:
            buy_vol_5m = sum(t['qty'] for t in trades_5m if t['is_buy'])
            sell_vol_5m = sum(t['qty'] for t in trades_5m if not t['is_buy'])
            total_5m = buy_vol_5m + sell_vol_5m
            self.latest_data["flow_delta_5m"] = (buy_vol_5m - sell_vol_5m) / total_5m if total_5m > 0 else 0
    
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
            "funding_predicted": None,
            "open_interest": None,
            "oi_change_1h": None,
            "long_short_ratio": None
        }
        
        # Track previous OI for change calculation
        self.oi_history = []  # List of (timestamp, oi) tuples
        
        print(f"✅ BinanceRESTCollector initialized for {symbol}")
    
    def fetch_funding_rate(self) -> Optional[float]:
        """
        Fetch current and predicted funding rate
        Endpoint: GET /fapi/v1/fundingRate (public, no auth needed)
        Endpoint: GET /fapi/v1/premiumIndex (for predicted funding)
        """
        try:
            # Get current funding rate
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
            
            # Get predicted funding rate (next funding)
            url_premium = f"{self.base_url_futures}/fapi/v1/premiumIndex"
            params_premium = {"symbol": self.symbol}
            
            response_premium = requests.get(url_premium, params=params_premium, proxies=proxies, timeout=10)
            response_premium.raise_for_status()
            
            premium_data = response_premium.json()
            if premium_data:
                # lastFundingRate is the predicted rate
                predicted = float(premium_data.get('lastFundingRate', 0))
                self.latest_data["funding_predicted"] = predicted
                return funding_rate
                
        except Exception as e:
            print(f"⚠️  Failed to fetch funding rate: {e}")
        return None
    
    def fetch_open_interest(self) -> Optional[float]:
        """
        Fetch open interest and calculate 1h change
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
            
            # Track OI history for change calculation
            now = time.time()
            self.oi_history.append((now, open_interest))
            
            # Keep only last 2 hours of data
            cutoff = now - 7200  # 2 hours
            self.oi_history = [(t, oi) for t, oi in self.oi_history if t > cutoff]
            
            # Calculate 1h change
            one_hour_ago = now - 3600
            historical_oi = [oi for t, oi in self.oi_history if t <= one_hour_ago]
            if historical_oi:
                old_oi = historical_oi[-1]  # Get closest to 1h ago
                oi_change = ((open_interest - old_oi) / old_oi * 100) if old_oi > 0 else 0
                self.latest_data["oi_change_1h"] = oi_change
            
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
