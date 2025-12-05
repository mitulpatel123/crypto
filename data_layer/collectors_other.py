"""
Other Data Collectors - THREADED VERSION
Uses latest 2025 API endpoints with background threading
"""

import requests
import time
import threading
from typing import Dict, Any, Optional
from datetime import datetime


class ThreadedCollector(threading.Thread):
    """Base class for threaded collectors"""
    def __init__(self):
        super().__init__()
        self.daemon = True
        self.running = False
        self.lock = threading.Lock()
        self.latest_data = {}
    
    def get_snapshot(self) -> Dict[str, Any]:
        with self.lock:
            return self.latest_data.copy()
    
    def stop(self):
        self.running = False


class DeltaExchangeCollector(ThreadedCollector):
    """
    Delta Exchange India API Collector
    https://www.delta.exchange/api (2025)
    """
    
    def __init__(self, key_manager):
        super().__init__()
        self.key_manager = key_manager
        self.base_url = "https://api.delta.exchange"
        self.latest_data = {
            "implied_volatility": None,
            "delta_exposure": None,
            "theta": None,
            "vega": None,
            "open_interest": None
        }
        print("✅ DeltaExchangeCollector (Threaded) initialized")
    
    def run(self):
        """Background thread loop"""
        self.running = True
        while self.running:
            self.fetch_ticker()
            time.sleep(10)  # Fetch every 10 seconds
    
    def fetch_ticker(self, symbol: str = "BTCUSD"):
        """Fetch ticker data with Greeks"""
        if not self.key_manager.increment("delta"):
            return
        
        try:
            key = self.key_manager.get_key("delta")
            if not key:
                return
            
            url = f"{self.base_url}/v2/tickers/{symbol}"
            proxies = self.key_manager.get_proxy_dict()
            
            response = requests.get(url, proxies=proxies, timeout=5)
            if response.status_code == 200:
                json_resp = response.json()
                data = json_resp.get('result') or {}
                greeks = data.get('greeks') or {}
                
                with self.lock:
                    self.latest_data["implied_volatility"] = greeks.get('iv')
                    self.latest_data["delta_exposure"] = greeks.get('delta')
                    self.latest_data["theta"] = greeks.get('theta')
                    self.latest_data["vega"] = greeks.get('vega')
                    self.latest_data["open_interest"] = data.get('oi_value_usd')
        except Exception:
            pass


class CryptoPanicCollector(ThreadedCollector):
    """
    CryptoPanic API (Developer v2 - 2025)
    https://cryptopanic.com/developers/api/
    Rate limit: 100 requests/month, 2 req/sec
    """
    
    def __init__(self, key_manager):
        super().__init__()
        self.key_manager = key_manager
        self.base_url = "https://cryptopanic.com/api/developer/v2"
        self.latest_data = {
            "news_sentiment": 0.0,
            "news_count": 0
        }
        print("✅ CryptoPanicCollector (Threaded) initialized")
    
    def run(self):
        self.running = True
        while self.running:
            self.fetch_news()
            time.sleep(600)  # Every 10 minutes
    
    def fetch_news(self, currencies: str = "BTC"):
        if not self.key_manager.increment("cryptopanic"):
            return
        
        try:
            key = self.key_manager.get_key("cryptopanic")
            if not key:
                return
            
            url = f"{self.base_url}/posts/"
            params = {
                "auth_token": key["token"],
                "currencies": currencies,
                "kind": "news",
                "filter": "rising"
            }
            
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                results = data.get('results', [])
                
                if results:
                    scores = []
                    for item in results[:20]:
                        votes = item.get('votes', {})
                        pos = votes.get('positive', 0)
                        neg = votes.get('negative', 0)
                        if pos + neg > 0:
                            scores.append((pos - neg) / (pos + neg))
                    
                    with self.lock:
                        if scores:
                            self.latest_data["news_sentiment"] = sum(scores) / len(scores)
                            self.latest_data["news_count"] = len(results)
        except Exception:
            pass


class AlphaVantageCollector(ThreadedCollector):
    """
    Alpha Vantage API (2025)
    https://www.alphavantage.co/documentation/
    Rate limit: 25 requests/day per key (you have 30 keys!)
    """
    
    def __init__(self, key_manager):
        super().__init__()
        self.key_manager = key_manager
        self.base_url = "https://www.alphavantage.co/query"
        self.latest_data = {"social_hype_index": 0.0}
        print("✅ AlphaVantageCollector (Threaded) initialized")
    
    def run(self):
        self.running = True
        while self.running:
            self.fetch_sentiment()
            time.sleep(1800)  # Every 30 minutes
    
    def fetch_sentiment(self, symbol: str = "BTC"):
        if not self.key_manager.increment("alphavantage"):
            return
        
        try:
            key = self.key_manager.get_key("alphavantage")
            if not key:
                return
            
            params = {
                "function": "NEWS_SENTIMENT",
                "tickers": f"CRYPTO:{symbol}",
                "apikey": key["api_key"],
                "limit": 50
            }
            
            response = requests.get(self.base_url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                feed = data.get('feed', [])
                
                if feed:
                    scores = []
                    for article in feed:
                        for ts in article.get('ticker_sentiment', []):
                            if ts.get('ticker') == f"CRYPTO:{symbol}":
                                scores.append(float(ts.get('ticker_sentiment_score', 0)))
                    
                    with self.lock:
                        if scores:
                            self.latest_data["social_hype_index"] = sum(scores) / len(scores)
        except Exception:
            pass


class EtherscanCollector(ThreadedCollector):
    """
    Etherscan API (2025)
    https://docs.etherscan.io/api-endpoints
    Rate limit: 3 calls/sec, 100k/day
    """
    
    def __init__(self, key_manager):
        super().__init__()
        self.key_manager = key_manager
        self.base_url = "https://api.etherscan.io/api"
        self.latest_data = {"whale_inflow": 0.0}
        self.wallets = [
            "0x28c6c06298d514db089934071355e5743bf21d60",
            "0x21a31ee1afc51d94c2efccaa2092ad1028285549"
        ]
        print("✅ EtherscanCollector (Threaded) initialized")
    
    def run(self):
        self.running = True
        while self.running:
            self.fetch_whale()
            time.sleep(60)  # Every 60 seconds
    
    def fetch_whale(self):
        if not self.key_manager.increment("etherscan"):
            return
        
        try:
            key = self.key_manager.get_key("etherscan")
            if not key:
                return
            
            total = 0
            for wallet in self.wallets:
                params = {
                    "module": "account",
                    "action": "balance",
                    "address": wallet,
                    "tag": "latest",
                    "apikey": key["api_key"]
                }
                
                response = requests.get(self.base_url, params=params, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    if data.get('status') == '1':
                        total += int(data.get('result', 0)) / 1e18
                time.sleep(0.4)  # Rate limit
            
            with self.lock:
                self.latest_data["whale_inflow"] = total
        except Exception:
            pass


class AlternativeMeCollector(ThreadedCollector):
    """
    Alternative.me Fear & Greed Index (Free, no API key)
    https://api.alternative.me/fng/
    """
    
    def __init__(self):
        super().__init__()
        self.latest_data = {"fear_greed_index": 50}
        print("✅ AlternativeMeCollector (Threaded) initialized")
    
    def run(self):
        self.running = True
        while self.running:
            try:
                response = requests.get("https://api.alternative.me/fng/", timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    if data.get('data'):
                        with self.lock:
                            self.latest_data["fear_greed_index"] = int(data['data'][0].get('value', 50))
            except Exception:
                pass
            time.sleep(1800)  # Every 30 minutes


class BlockchainInfoCollector:
    """
    Blockchain.info WebSocket (Free, no auth)
    wss://ws.blockchain.info/inv
    """
    
    def __init__(self):
        self.latest_data = {
            "whale_inflow": 0.0,
            "whale_outflow": 0.0,
            "large_tx_count": 0
        }
        print("✅ BlockchainInfoCollector initialized")
    
    def get_snapshot(self) -> Dict[str, Any]:
        return self.latest_data.copy()
