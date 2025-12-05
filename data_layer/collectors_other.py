"""
Other Data Collectors: Delta Exchange, CryptoPanic, Alpha Vantage, Etherscan, etc.
Uses latest 2025 API endpoints
"""

import requests
import time
from typing import Dict, Any, Optional
from datetime import datetime


class DeltaExchangeCollector:
    """
    Delta Exchange India API Collector
    https://www.delta.exchange/api (2025)
    """
    
    def __init__(self, key_manager):
        self.key_manager = key_manager
        self.base_url = "https://api.delta.exchange"
        self.latest_data = {
            "implied_volatility": None,
            "delta_exposure": None,
            "theta": None,
            "vega": None,
            "open_interest": None
        }
        print("✅ DeltaExchangeCollector initialized")
    
    def fetch_ticker(self, symbol: str = "BTCUSD") -> bool:
        """Fetch ticker data with Greeks"""
        # Track usage internally to respect our rate limits
        if not self.key_manager.increment("delta"):
            print("⚠️  Delta Exchange rate limit reached")
            return False
        
        try:
            # Verify we have a key configured (even though public endpoint doesn't need auth)
            key = self.key_manager.get_key("delta")
            if not key:
                return False
            
            # ✅ SECURITY FIX: /v2/tickers is a PUBLIC endpoint
            # No authentication headers required!
            # If you need private data later, implement proper HMAC-SHA256 signature
            url = f"{self.base_url}/v2/tickers/{symbol}"
            
            proxies = self.key_manager.get_proxy_dict()
            response = requests.get(url, proxies=proxies, timeout=10)
            response.raise_for_status()
            
            data = response.json().get('result', {})
            
            # Extract Greeks (if available)
            self.latest_data["implied_volatility"] = data.get('greeks', {}).get('iv')
            self.latest_data["delta_exposure"] = data.get('greeks', {}).get('delta')
            self.latest_data["theta"] = data.get('greeks', {}).get('theta')
            self.latest_data["vega"] = data.get('greeks', {}).get('vega')
            self.latest_data["open_interest"] = data.get('oi_value_usd')
            
            return True
            
        except Exception as e:
            print(f"⚠️  Delta Exchange error: {e}")
            return False
    
    def get_snapshot(self) -> Dict[str, Any]:
        return self.latest_data.copy()


class CryptoPanicCollector:
    """
    CryptoPanic API (Developer v2 - 2025)
    https://cryptopanic.com/developers/api/
    Rate limit: 100 requests/month, 2 req/sec
    """
    
    def __init__(self, key_manager):
        self.key_manager = key_manager
        self.base_url = "https://cryptopanic.com/api/developer/v2"
        self.latest_data = {
            "news_sentiment": 0.0,  # -1 to +1
            "news_count": 0
        }
        print("✅ CryptoPanicCollector initialized")
    
    def fetch_news(self, currencies: str = "BTC") -> bool:
        """Fetch latest news and calculate sentiment"""
        if not self.key_manager.increment("cryptopanic"):
            print("⚠️  CryptoPanic monthly limit reached")
            return False
        
        try:
            key = self.key_manager.get_key("cryptopanic")
            if not key:
                return False
            
            url = f"{self.base_url}/posts/"
            params = {
                "auth_token": key["token"],
                "currencies": currencies,
                "kind": "news",
                "filter": "rising"
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            results = data.get('results', [])
            
            if results:
                # Calculate sentiment from votes
                sentiment_scores = []
                for item in results[:20]:  # Latest 20 news
                    votes = item.get('votes', {})
                    positive = votes.get('positive', 0)
                    negative = votes.get('negative', 0)
                    
                    if positive + negative > 0:
                        score = (positive - negative) / (positive + negative)
                        sentiment_scores.append(score)
                
                if sentiment_scores:
                    self.latest_data["news_sentiment"] = sum(sentiment_scores) / len(sentiment_scores)
                    self.latest_data["news_count"] = len(results)
            
            return True
            
        except Exception as e:
            print(f"⚠️  CryptoPanic error: {e}")
            return False
    
    def get_snapshot(self) -> Dict[str, Any]:
        return self.latest_data.copy()


class AlphaVantageCollector:
    """
    Alpha Vantage API (2025)
    https://www.alphavantage.co/documentation/
    Rate limit: 25 requests/day per key (you have 30 keys!)
    """
    
    def __init__(self, key_manager):
        self.key_manager = key_manager
        self.base_url = "https://www.alphavantage.co/query"
        self.latest_data = {
            "social_hype_index": 0.0
        }
        print("✅ AlphaVantageCollector initialized with 30 keys")
    
    def fetch_crypto_sentiment(self, symbol: str = "BTC") -> bool:
        """Fetch cryptocurrency news sentiment"""
        if not self.key_manager.increment("alphavantage"):
            print("⚠️  Alpha Vantage daily limit reached (rotating to next key)")
            return False
        
        try:
            key = self.key_manager.get_key("alphavantage")
            if not key:
                return False
            
            params = {
                "function": "NEWS_SENTIMENT",
                "tickers": f"CRYPTO:{symbol}",
                "apikey": key["api_key"],
                "limit": 50
            }
            
            response = requests.get(self.base_url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            feed = data.get('feed', [])
            
            if feed:
                # Calculate average sentiment
                sentiments = []
                for article in feed:
                    ticker_sentiment = article.get('ticker_sentiment', [])
                    for ts in ticker_sentiment:
                        if ts.get('ticker') == f"CRYPTO:{symbol}":
                            score = float(ts.get('ticker_sentiment_score', 0))
                            sentiments.append(score)
                
                if sentiments:
                    self.latest_data["social_hype_index"] = sum(sentiments) / len(sentiments)
            
            return True
            
        except Exception as e:
            print(f"⚠️  Alpha Vantage error: {e}")
            return False
    
    def get_snapshot(self) -> Dict[str, Any]:
        return self.latest_data.copy()


class EtherscanCollector:
    """
    Etherscan API (2025)
    https://docs.etherscan.io/api-endpoints
    Rate limit: 3 calls/sec, 100k/day
    """
    
    def __init__(self, key_manager):
        self.key_manager = key_manager
        self.base_url = "https://api.etherscan.io/api"
        self.latest_data = {
            "whale_inflow": 0.0,
            "whale_outflow": 0.0
        }
        
        # Major exchange wallets to track
        self.exchange_wallets = [
            "0x28c6c06298d514db089934071355e5743bf21d60",  # Binance 1
            "0x21a31ee1afc51d94c2efccaa2092ad1028285549",  # Binance 2
            "0x3f5ce5fbfe3e9af3971dd833d26ba9b5c936f0be",  # Binance 3
            "0x564286362092d8e7936f0549571a803b203aaced",  # Binance 4
            "0x0681d8db095565fe8a346fa0277bffde9c0edbbf",  # Binance 5
        ]
        
        print("✅ EtherscanCollector initialized")
    
    def fetch_whale_movements(self) -> bool:
        """Track ETH movements to/from exchanges"""
        if not self.key_manager.increment("etherscan"):
            return False
        
        try:
            key = self.key_manager.get_key("etherscan")
            if not key:
                return False
            
            # Sample: Check balance changes (simplified)
            # In production, you'd track transactions
            
            total_balance = 0
            for wallet in self.exchange_wallets[:2]:  # Check first 2 to save API calls
                params = {
                    "module": "account",
                    "action": "balance",
                    "address": wallet,
                    "tag": "latest",
                    "apikey": key["api_key"]
                }
                
                response = requests.get(self.base_url, params=params, timeout=10)
                response.raise_for_status()
                
                data = response.json()
                if data.get('status') == '1':
                    balance_wei = int(data.get('result', 0))
                    balance_eth = balance_wei / 1e18
                    total_balance += balance_eth
                
                time.sleep(0.4)  # Rate limit: 3 calls/sec
            
            # Store as whale inflow (simplified logic)
            self.latest_data["whale_inflow"] = total_balance
            
            return True
            
        except Exception as e:
            print(f"⚠️  Etherscan error: {e}")
            return False
    
    def get_snapshot(self) -> Dict[str, Any]:
        return self.latest_data.copy()


class AlternativeMeCollector:
    """
    Alternative.me Fear & Greed Index (Free, no API key)
    https://api.alternative.me/fng/
    """
    
    def __init__(self):
        self.base_url = "https://api.alternative.me"
        self.latest_data = {
            "fear_greed_index": 50  # Default neutral
        }
        print("✅ AlternativeMeCollector initialized")
    
    def fetch_fear_greed(self) -> bool:
        """Fetch Fear & Greed Index"""
        try:
            url = f"{self.base_url}/fng/"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            if 'data' in data and len(data['data']) > 0:
                value = int(data['data'][0].get('value', 50))
                self.latest_data["fear_greed_index"] = value
                return True
                
        except Exception as e:
            print(f"⚠️  Alternative.me error: {e}")
        return False
    
    def get_snapshot(self) -> Dict[str, Any]:
        return self.latest_data.copy()


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
