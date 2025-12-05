"""
FRED (Federal Reserve Economic Data) API Collector
Provides: DXY, 10Y Treasury Yields, M2 Money Supply
FREE unlimited with API key - Using fredapi library for reliability
"""

import threading
import time
from fredapi import Fred
from datetime import datetime


class FREDCollector(threading.Thread):
    def __init__(self, key_manager):
        super().__init__()
        self.daemon = True
        self.running = False
        self.lock = threading.Lock()
        self.key_manager = key_manager
        self.fred = None
        
        # FRED series IDs
        self.series_ids = {
            "dxy": "DTWEXBGS",  # Trade Weighted U.S. Dollar Index
            "treasury_10y": "DGS10",  # 10-Year Treasury Constant Maturity Rate
            "m2_money": "WM2NS"  # M2 Money Stock (Billions)
        }
        
        self.latest_data = {
            "dxy_fred": 0.0,
            "treasury_10y": 0.0,
            "m2_money_supply": 0.0
        }
        
    def initialize_fred(self):
        """Initialize FRED API client with key from manager"""
        try:
            key_info = self.key_manager.get_key("fred")
            if not key_info:
                print("❌ FRED: No API key available")
                return False
            
            api_key = key_info.get("api_key") or key_info.get("token")
            self.fred = Fred(api_key=api_key)
            return True
        except Exception as e:
            print(f"❌ FRED: Initialization failed - {e}")
            return False
    
    def fetch_series_data(self, series_id, data_key):
        """Fetch latest data point for a FRED series using fredapi library"""
        try:
            if not self.fred:
                if not self.initialize_fred():
                    return False
            
            # Get latest observation
            series = self.fred.get_series(series_id, limit=1)
            
            if series is not None and len(series) > 0:
                latest_value = series.iloc[-1]
                
                # Handle NaN values
                if latest_value != latest_value:  # NaN check
                    print(f"⚠️  FRED {data_key}: No recent data (NaN)")
                    return False
                
                value = float(latest_value)
                
                # M2 is in billions, others are already in correct format
                if data_key == "m2_money_supply":
                    value = value / 1000  # Convert to trillions for readability
                
                with self.lock:
                    self.latest_data[data_key] = value
                
                self.key_manager.increment("fred")
                return True
            else:
                print(f"⚠️  FRED {data_key}: No data returned")
                return False
                        
        except Exception as e:
            print(f"❌ FRED {data_key}: {type(e).__name__}: {e}")
            return False
    
    def run(self):
        """Main collection loop - runs every 1 hour (data updates daily)"""
        self.running = True
        print("✅ FREDCollector initialized (Using existing 4 API keys)")
        
        while self.running:
            try:
                # Fetch all series
                self.fetch_series_data(self.series_ids["dxy"], "dxy_fred")
                time.sleep(5)
                
                self.fetch_series_data(self.series_ids["treasury_10y"], "treasury_10y")
                time.sleep(5)
                
                self.fetch_series_data(self.series_ids["m2_money"], "m2_money_supply")
                
                # Print status
                dxy = self.latest_data['dxy_fred']
                treasury = self.latest_data['treasury_10y']
                m2 = self.latest_data['m2_money_supply']
                print(f"✅ FRED: DXY={dxy:.2f}, 10Y={treasury:.3f}%, M2=${m2:.2f}T")
                
                # Sleep for 1 hour (data updates once per day)
                time.sleep(3600)
                
            except Exception as e:
                print(f"❌ FRED thread error: {e}")
                time.sleep(300)  # 5 min on error
    
    def get_snapshot(self):
        """Thread-safe data retrieval"""
        with self.lock:
            return self.latest_data.copy()
    
    def stop(self):
        """Stop the collector"""
        self.running = False
