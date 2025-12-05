"""
Coinalyze API Collector - Liquidations & PCR
FREE: 100 calls/day per key (using 3 keys = 300 calls/day)
Docs: https://api.coinalyze.net/v1/doc/
"""

import threading
import time
import requests
from datetime import datetime, timedelta


class CoinalyzeCollector(threading.Thread):
    def __init__(self):
        super().__init__()
        self.daemon = True
        self.running = False
        self.lock = threading.Lock()
        
        # 3 API keys from user (100 calls/day each = 300 total)
        self.api_keys = [
            "16160041-8b64-458f-870b-19282765196b",
            "5bc5b5d6-883a-40ce-91ab-33af2f3473e5",
            "c9213e9a-1e01-4d82-a39c-2f7e0baca02e"
        ]
        self.current_key_index = 0
        self.call_count = 0
        self.max_calls_per_key = 100  # Daily limit
        
        self.base_url = "https://api.coinalyze.net/v1"
        
        self.latest_data = {
            "liquidation_long_1h": 0.0,
            "liquidation_short_1h": 0.0,
            "liquidation_total_1h": 0.0,
            "put_call_ratio": 0.0
        }
    
    def get_current_api_key(self):
        """Rotate API keys when limit reached"""
        if self.call_count >= self.max_calls_per_key:
            self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
            self.call_count = 0
            print(f"🔄 Coinalyze: Rotated to API key #{self.current_key_index + 1}")
        
        return self.api_keys[self.current_key_index]
    
    def fetch_liquidations(self):
        """Fetch liquidation history (last 1 hour)"""
        try:
            api_key = self.get_current_api_key()
            
            # Get last 1 hour of liquidations
            end_time = int(datetime.now().timestamp())
            start_time = int((datetime.now() - timedelta(hours=1)).timestamp())
            
            url = f"{self.base_url}/liquidation-history"
            params = {
                "symbols": "BTCUSDT.6",  # Binance perpetual
                "from": start_time,
                "to": end_time
            }
            headers = {"api_key": api_key}
            
            response = requests.get(url, params=params, headers=headers, timeout=10)
            self.call_count += 1
            
            if response.status_code == 200:
                data = response.json()
                
                # Aggregate liquidations by side
                long_liq = 0
                short_liq = 0
                
                for event in data:
                    side = event.get("side", "").lower()
                    quantity_usd = float(event.get("value", 0))
                    
                    if side == "buy":  # Buy liquidation = long position liquidated
                        long_liq += quantity_usd
                    elif side == "sell":  # Sell liquidation = short position liquidated
                        short_liq += quantity_usd
                
                with self.lock:
                    self.latest_data["liquidation_long_1h"] = long_liq
                    self.latest_data["liquidation_short_1h"] = short_liq
                    self.latest_data["liquidation_total_1h"] = long_liq + short_liq
                
                print(f"✅ Coinalyze: Liquidations = ${long_liq + short_liq:,.0f} (L:${long_liq:,.0f}, S:${short_liq:,.0f})")
                return True
            else:
                print(f"⚠️  Coinalyze Liq: HTTP {response.status_code}")
                if response.status_code == 429:
                    print(f"    Rate limit hit, rotating to next key...")
                    self.call_count = self.max_calls_per_key  # Force rotation
        
        except requests.Timeout:
            print("❌ Coinalyze: Request timeout")
        except Exception as e:
            print(f"❌ Coinalyze: {type(e).__name__}: {e}")
        
        return False
    
    def fetch_put_call_ratio(self):
        """Calculate PCR from options open interest"""
        try:
            api_key = self.get_current_api_key()
            
            url = f"{self.base_url}/open-interest-chart"
            params = {
                "symbols": "BTCUSDT.6",
                "from": int((datetime.now() - timedelta(hours=24)).timestamp()),
                "to": int(datetime.now().timestamp()),
                "interval": "1h"
            }
            headers = {"api_key": api_key}
            
            response = requests.get(url, params=params, headers=headers, timeout=10)
            self.call_count += 1
            
            if response.status_code == 200:
                data = response.json()
                
                if data and len(data) > 0:
                    # Get latest OI data
                    latest = data[-1]
                    put_oi = float(latest.get("put_oi", 0))
                    call_oi = float(latest.get("call_oi", 0))
                    
                    pcr = put_oi / call_oi if call_oi > 0 else 0
                    
                    with self.lock:
                        self.latest_data["put_call_ratio"] = pcr
                    
                    print(f"✅ Coinalyze: PCR = {pcr:.3f}")
                    return True
            else:
                print(f"⚠️  Coinalyze PCR: HTTP {response.status_code}")
        
        except Exception as e:
            print(f"❌ Coinalyze PCR: {type(e).__name__}: {e}")
        
        return False
    
    def run(self):
        """Main collection loop - runs every 10 minutes"""
        self.running = True
        print("✅ CoinalyzeCollector initialized (3 API keys = 300 calls/day)")
        
        # Initial fetch
        time.sleep(5)  # Wait for other collectors
        
        while self.running:
            try:
                # Fetch liquidations (primary use case)
                self.fetch_liquidations()
                time.sleep(3)
                
                # Fetch PCR (optional - uncomment if needed)
                # self.fetch_put_call_ratio()
                
                # Sleep 10 minutes = 144 calls/day per key (well under 100 limit)
                # With 3 keys we can fetch every 3 minutes if needed
                time.sleep(600)
                
            except Exception as e:
                print(f"❌ Coinalyze thread error: {e}")
                time.sleep(60)
    
    def get_snapshot(self):
        """Thread-safe data retrieval"""
        with self.lock:
            return self.latest_data.copy()
    
    def stop(self):
        """Stop the collector"""
        self.running = False
        print("✅ CoinalyzeCollector stopped")
