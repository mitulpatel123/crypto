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
            "iv_rank": None,
            "delta_exposure": None,
            "put_call_ratio_vol": None,
            "put_call_ratio_oi": None,
            "gamma_strike_1": None,
            "gamma_strike_2": None,
            "gamma_strike_3": None,
            "theta": None,
            "vega": None
        }
        print("✅ DeltaExchangeCollector (Threaded) initialized")
    
    def run(self):
        """Background thread loop"""
        self.running = True
        while self.running:
            self.fetch_ticker()
            time.sleep(10)  # Fetch every 10 seconds
    
    def fetch_ticker(self, symbol: str = "BTCUSD"):
        """Fetch ticker data with Greeks and options metrics"""
        if not self.key_manager.increment("delta"):
            print("⚠️  Delta Exchange: Rate limit reached, skipping...")
            return
        
        try:
            key = self.key_manager.get_key("delta")
            if not key:
                print("❌ Delta Exchange: No API key available")
                return
            
            # Fetch main ticker with Greeks
            url = f"{self.base_url}/v2/tickers/{symbol}"
            
            # CRITICAL: Disable proxy for Delta Exchange (direct connection)
            response = requests.get(url, timeout=10, proxies={"http": None, "https": None})
            
            if response.status_code == 200:
                json_resp = response.json()
                data = json_resp.get('result') or {}
                greeks = data.get('greeks') or {}
                
                with self.lock:
                    self.latest_data["implied_volatility"] = greeks.get('iv')
                    self.latest_data["delta_exposure"] = greeks.get('delta')
                    self.latest_data["theta"] = greeks.get('theta')
                    self.latest_data["vega"] = greeks.get('vega')
                    
                iv_value = greeks.get('iv', 'N/A')
                print(f"✅ Delta Exchange: Updated Greeks (IV={iv_value})")
            else:
                print(f"⚠️  Delta Exchange ticker failed: HTTP {response.status_code}")
            
            # Fetch options chain for additional metrics
            options_url = f"{self.base_url}/v2/products"
            params = {"contract_types": "call_options,put_options", "states": "live"}
            
            # CRITICAL: Disable proxy for Delta Exchange
            options_response = requests.get(options_url, params=params, timeout=10, proxies={"http": None, "https": None})
            if options_response.status_code == 200:
                options_data = options_response.json()
                products = options_data.get('result', [])
                
                if products:
                    # Calculate Put/Call ratios and gamma strikes
                    calls = [p for p in products if p.get('contract_type') == 'call_options']
                    puts = [p for p in products if p.get('contract_type') == 'put_options']
                    
                    # Put/Call ratio by volume
                    call_vol = sum(float(c.get('volume', 0)) for c in calls)
                    put_vol = sum(float(p.get('volume', 0)) for p in puts)
                    if call_vol > 0:
                        self.latest_data["put_call_ratio_vol"] = put_vol / call_vol
                    
                    # Put/Call ratio by open interest
                    call_oi = sum(float(c.get('open_interest', 0)) for c in calls)
                    put_oi = sum(float(p.get('open_interest', 0)) for p in puts)
                    if call_oi > 0:
                        self.latest_data["put_call_ratio_oi"] = put_oi / call_oi
                    
                    # Find top 3 gamma strikes (highest open interest strikes)
                    all_options = calls + puts
                    sorted_by_oi = sorted(all_options, key=lambda x: float(x.get('open_interest', 0)), reverse=True)
                    
                    with self.lock:
                        if len(sorted_by_oi) > 0:
                            self.latest_data["gamma_strike_1"] = float(sorted_by_oi[0].get('strike_price', 0))
                        if len(sorted_by_oi) > 1:
                            self.latest_data["gamma_strike_2"] = float(sorted_by_oi[1].get('strike_price', 0))
                        if len(sorted_by_oi) > 2:
                            self.latest_data["gamma_strike_3"] = float(sorted_by_oi[2].get('strike_price', 0))
                        
                        # Calculate IV rank (current IV percentile over 52 weeks)
                        # Simplified: Use current IV position relative to min/max from active options
                        ivs = [float(o.get('greeks', {}).get('iv', 0)) for o in all_options if o.get('greeks', {}).get('iv')]
                        if ivs and len(ivs) > 10:
                            current_iv = self.latest_data.get("implied_volatility")
                            if current_iv:
                                min_iv = min(ivs)
                                max_iv = max(ivs)
                                if max_iv > min_iv:
                                    iv_rank = ((current_iv - min_iv) / (max_iv - min_iv)) * 100
                                    self.latest_data["iv_rank"] = iv_rank
                                    
                pcr_vol = self.latest_data.get('put_call_ratio_vol', 'N/A')
                if pcr_vol != 'N/A' and pcr_vol is not None:
                    print(f"✅ Delta Exchange: Updated options data (Put/Call Ratio Vol={pcr_vol:.2f})")
                else:
                    print(f"✅ Delta Exchange: Updated options data")
            else:
                print(f"⚠️  Delta Exchange options failed: HTTP {options_response.status_code}")
        except requests.exceptions.Timeout:
            print("❌ Delta Exchange: Request timeout (network issue)")
        except requests.exceptions.RequestException as e:
            print(f"❌ Delta Exchange: Network error - {e}")
        except Exception as e:
            print(f"❌ Delta Exchange: Unexpected error - {e}")


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
                            print(f"✅ CryptoPanic: Updated sentiment={self.latest_data['news_sentiment']:.3f}, articles={len(results)}")
            else:
                print(f"⚠️  CryptoPanic: HTTP {response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"❌ CryptoPanic: Request failed - {e}")
        except Exception as e:
            print(f"❌ CryptoPanic: Error - {e}")


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
                            print(f"✅ AlphaVantage: Updated hype_index={self.latest_data['social_hype_index']:.3f}")
            else:
                print(f"⚠️  AlphaVantage: HTTP {response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"❌ AlphaVantage: Request failed - {e}")
        except Exception as e:
            print(f"❌ AlphaVantage: Error - {e}")


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
        self.latest_data = {
            "whale_inflow": 0.0,
            "whale_outflow": 0.0
        }
        self.wallets = [
            "0x28c6c06298d514db089934071355e5743bf21d60",  # Binance 1
            "0x21a31ee1afc51d94c2efccaa2092ad1028285549"   # Binance 2
        ]
        self.previous_balances = {}  # Track previous balances
        print("✅ EtherscanCollector (Threaded) initialized")
    
    def run(self):
        self.running = True
        while self.running:
            self.fetch_whale()
            time.sleep(60)  # Every 60 seconds
    
    def fetch_whale(self):
        """Fetch whale wallet balances and calculate inflow/outflow"""
        if not self.key_manager.increment("etherscan"):
            return
        
        try:
            key = self.key_manager.get_key("etherscan")
            if not key:
                return
            
            total_balance = 0
            inflow = 0
            outflow = 0
            
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
                        balance = int(data.get('result', 0)) / 1e18
                        total_balance += balance
                        
                        # Calculate inflow/outflow
                        if wallet in self.previous_balances:
                            change = balance - self.previous_balances[wallet]
                            if change > 0:
                                inflow += change
                            else:
                                outflow += abs(change)
                        
                        # Update previous balance
                        self.previous_balances[wallet] = balance
                
                time.sleep(0.4)  # Rate limit
            
            with self.lock:
                self.latest_data["whale_inflow"] = inflow
                self.latest_data["whale_outflow"] = outflow
                if inflow > 0 or outflow > 0:
                    print(f"✅ Etherscan: Whale inflow={inflow:.2f} ETH, outflow={outflow:.2f} ETH")
        except requests.exceptions.RequestException as e:
            print(f"❌ Etherscan: Request failed - {e}")
        except Exception as e:
            print(f"❌ Etherscan: Error - {e}")


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
                            old_value = self.latest_data["fear_greed_index"]
                            new_value = int(data['data'][0].get('value', 50))
                            self.latest_data["fear_greed_index"] = new_value
                            if old_value != new_value:
                                print(f"✅ Alternative.me: Fear & Greed Index updated to {new_value}")
                else:
                    print(f"⚠️  Alternative.me: HTTP {response.status_code}")
            except Exception as e:
                print(f"❌ Alternative.me: Error - {e}")
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
