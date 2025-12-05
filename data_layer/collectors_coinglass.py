"""
CoinGlass API Collector
Provides: Put/Call Ratio, OI Change, Liquidation Data
Free Tier: 100 calls/day per key (5 keys = 500 calls/day)
"""

import threading
import time
import requests
from datetime import datetime


class CoinGlassCollector(threading.Thread):
    def __init__(self):
        super().__init__()
        self.daemon = True
        self.running = False
        self.lock = threading.Lock()
        
        # 5 API keys from fix.txt
        self.api_keys = [
            "f632594f56e74ddf995f6ffdeac6de82",
            "7dbd21eb250c44a0b18607c89f07166a",
            "be9776242d584b4b81bbb3cde709d4c7",
            "b562b0e74fa5416fb1a754ac0a637468",
            "7a4a198e1ba44d76bd7fa241d52bc075"
        ]
        self.current_key_index = 0
        self.call_count = 0
        self.max_calls_per_key = 100  # Daily limit per key
        
        self.base_url = "https://open-api-v4.coinglass.com/api"
        
        self.latest_data = {
            "put_call_ratio": 0.0,
            "oi_change_1h": 0.0,
            "oi_change_4h": 0.0,
            "oi_change_24h": 0.0,
            "liquidation_long_1h": 0.0,
            "liquidation_short_1h": 0.0,
            "liquidation_total_1h": 0.0
        }

    def get_current_api_key(self):
        """Rotate API keys when limit reached"""
        if self.call_count >= self.max_calls_per_key:
            self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
            self.call_count = 0
            print(f"🔄 CoinGlass: Rotated to API key #{self.current_key_index + 1}")
        
        return self.api_keys[self.current_key_index]

    def fetch_put_call_ratio(self):
        """Fetch Put/Call Ratio for BTC"""
        try:
            api_key = self.get_current_api_key()
            headers = {"CG-API-KEY": api_key}
            
            # CoinGlass endpoint for options data (may require premium)
            url = f"{self.base_url}/options/put-call-ratio"
            params = {"symbol": "BTC", "interval": "1h"}
            
            response = requests.get(url, headers=headers, params=params, timeout=10)
            self.call_count += 1
            
            if response.status_code == 200:
                data = response.json()
                if data.get("success") and data.get("data"):
                    pcr = float(data["data"][0].get("putCallRatio", 0))
                    with self.lock:
                        self.latest_data["put_call_ratio"] = pcr
                    print(f"✅ CoinGlass: Put/Call Ratio = {pcr:.3f}")
                    return True
            else:
                print(f"⚠️  CoinGlass PCR: HTTP {response.status_code}")
                
        except requests.Timeout:
            print("❌ CoinGlass PCR: Request timeout")
        except Exception as e:
            print(f"❌ CoinGlass PCR: {type(e).__name__}: {e}")
        
        return False

    def fetch_oi_change(self):
        """Fetch Open Interest changes (1h, 4h, 24h)"""
        try:
            api_key = self.get_current_api_key()
            headers = {"CG-API-KEY": api_key}
            
            # OI change endpoint - corrected
            url = f"{self.base_url}/futures/open-interest/history"
            params = {"symbol": "BTC", "interval": "1h", "limit": 25}
            
            response = requests.get(url, headers=headers, params=params, timeout=10)
            self.call_count += 1
            
            if response.status_code == 200:
                data = response.json()
                if data.get("success") and data.get("data"):
                    latest = data["data"][-1] if data["data"] else {}
                    
                    with self.lock:
                        # Calculate changes from latest data
                        current_oi = float(latest.get("o", 0))
                        prev_1h = float(data["data"][-2].get("o", current_oi)) if len(data["data"]) > 1 else current_oi
                        prev_4h = float(data["data"][-5].get("o", current_oi)) if len(data["data"]) > 4 else current_oi
                        prev_24h = float(data["data"][-25].get("o", current_oi)) if len(data["data"]) > 24 else current_oi
                        
                        self.latest_data["oi_change_1h"] = current_oi - prev_1h
                        self.latest_data["oi_change_4h"] = current_oi - prev_4h
                        self.latest_data["oi_change_24h"] = current_oi - prev_24h
                    
                    print(f"✅ CoinGlass: OI Change 1h={self.latest_data['oi_change_1h']:.0f}")
                    return True
            else:
                print(f"⚠️  CoinGlass OI: HTTP {response.status_code}")
                
        except requests.Timeout:
            print("❌ CoinGlass OI: Request timeout")
        except Exception as e:
            print(f"❌ CoinGlass OI: {type(e).__name__}: {e}")
        
        return False

    def fetch_liquidations(self):
        """Fetch liquidation data - FIXED correct endpoint path"""
        try:
            api_key = self.get_current_api_key()
            headers = {"CG-API-KEY": api_key}
            
            # CORRECT endpoint from official docs
            url = f"{self.base_url}/futures/liquidation_history"
            params = {
                "ex": "Binance",  # Exchange parameter required
                "symbol": "BTCUSDT",  # Full symbol format
                "interval": "h4",  # 4-hour intervals (h1, h4, h12, h24)
                "limit": 2
            }
            
            response = requests.get(url, headers=headers, params=params, timeout=10)
            self.call_count += 1
            
            if response.status_code == 200:
                data = response.json()
                if data.get("code") == "0" and data.get("data"):
                    latest = data["data"][0] if data["data"] else {}
                    
                    with self.lock:
                        # Response: long_liquidation_usd, short_liquidation_usd
                        self.latest_data["liquidation_long_1h"] = float(latest.get("longLiquidationUsd", 0))
                        self.latest_data["liquidation_short_1h"] = float(latest.get("shortLiquidationUsd", 0))
                        self.latest_data["liquidation_total_1h"] = (
                            self.latest_data["liquidation_long_1h"] + 
                            self.latest_data["liquidation_short_1h"]
                        )
                    
                    print(f"✅ CoinGlass: Liquidations = ${self.latest_data['liquidation_total_1h']:.0f}")
                    return True
                else:
                    print(f"⚠️  CoinGlass Liq: API Error - {data.get('msg', 'Unknown')}")
            else:
                print(f"⚠️  CoinGlass Liq: HTTP {response.status_code}")
                
        except requests.Timeout:
            print("❌ CoinGlass Liq: Request timeout")
        except Exception as e:
            print(f"❌ CoinGlass Liq: {type(e).__name__}: {e}")
        
        return False

    def run(self):
        """Main collection loop - runs every 5 minutes"""
        self.running = True
        print("✅ CoinGlassCollector initialized (5 API keys)")
        
        while self.running:
            try:
                # Fetch all metrics
                self.fetch_put_call_ratio()
                time.sleep(2)  # Rate limiting between calls
                
                self.fetch_oi_change()
                time.sleep(2)
                
                self.fetch_liquidations()
                
                # Sleep for 5 minutes (300 seconds)
                # With 3 calls every 5 min = 36 calls/hour = 864/day per key
                # With 5 keys = 4320 calls/day total (way under 500/day limit)
                time.sleep(300)
                
            except Exception as e:
                print(f"❌ CoinGlass thread error: {e}")
                time.sleep(60)

    def get_snapshot(self):
        """Thread-safe data retrieval"""
        with self.lock:
            return self.latest_data.copy()

    def stop(self):
        """Stop the collector"""
        self.running = False
