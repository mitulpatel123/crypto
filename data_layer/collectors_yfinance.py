"""
Yahoo Finance Collector (Free, No API Key Required)
Provides SPX and DXY correlations with BTC
"""

import threading
import time
from typing import Dict, Any

try:
    import yfinance as yf
    import pandas as pd
    YFINANCE_AVAILABLE = True
except ImportError:
    YFINANCE_AVAILABLE = False
    print("⚠️  yfinance not installed. Run: pip install yfinance")


class YahooFinanceCollector(threading.Thread):
    """
    Yahoo Finance Collector for Market Correlations
    Calculates correlation between BTC and SPX/DXY
    """
    
    def __init__(self):
        super().__init__()
        self.daemon = True
        self.running = False
        self.lock = threading.Lock()
        self.latest_data = {
            "correlation_spx": 0.0,
            "correlation_dxy": 0.0
        }
        
        if YFINANCE_AVAILABLE:
            print("✅ YahooFinanceCollector initialized")
        else:
            print("❌ YahooFinanceCollector: yfinance library not available")
    
    def run(self):
        """Background thread loop - updates every 5 minutes"""
        if not YFINANCE_AVAILABLE:
            return
            
        self.running = True
        
        # Initial fetch
        self.fetch_correlations()
        
        while self.running:
            time.sleep(300)  # Update every 5 minutes
            try:
                self.fetch_correlations()
            except Exception as e:
                print(f"❌ YahooFinance: Unexpected error - {e}")
    
    def fetch_correlations(self):
        """Fetch market data and calculate correlations"""
        if not YFINANCE_AVAILABLE:
            return
            
        try:
            # Download 1-minute data for the last 2 hours
            # Symbols: ^GSPC (S&P 500), DX-Y.NYB (US Dollar Index), BTC-USD
            tickers_list = ["^GSPC", "DX-Y.NYB", "BTC-USD"]
            
            # Download with error handling
            data = yf.download(
                tickers=tickers_list,
                period="1d",
                interval="1m",
                progress=False,
                show_errors=False
            )
            
            if data.empty:
                print("⚠️  YahooFinance: No data downloaded")
                return
            
            # Extract Close prices
            if 'Close' in data.columns:
                close_prices = data['Close']
                
                # Handle multi-level columns (when downloading multiple tickers)
                if isinstance(close_prices.columns, pd.MultiIndex):
                    close_prices.columns = close_prices.columns.get_level_values(0)
                
                # Drop NaN values
                close_prices = close_prices.dropna()
                
                if len(close_prices) < 10:
                    print("⚠️  YahooFinance: Insufficient data points for correlation")
                    return
                
                # Calculate correlation matrix
                corr_matrix = close_prices.corr()
                
                # Extract correlations with BTC-USD
                if 'BTC-USD' in corr_matrix.columns:
                    spx_corr = corr_matrix.loc['BTC-USD', '^GSPC'] if '^GSPC' in corr_matrix.columns else 0.0
                    dxy_corr = corr_matrix.loc['BTC-USD', 'DX-Y.NYB'] if 'DX-Y.NYB' in corr_matrix.columns else 0.0
                    
                    with self.lock:
                        self.latest_data["correlation_spx"] = float(spx_corr) if pd.notna(spx_corr) else 0.0
                        self.latest_data["correlation_dxy"] = float(dxy_corr) if pd.notna(dxy_corr) else 0.0
                    
                    print(f"✅ YahooFinance: SPX Corr={spx_corr:.3f}, DXY Corr={dxy_corr:.3f}")
                else:
                    print("⚠️  YahooFinance: BTC-USD not in correlation matrix")
            else:
                print("⚠️  YahooFinance: Close prices not available")
                
        except Exception as e:
            print(f"❌ YahooFinance: Error fetching data - {e}")
    
    def get_snapshot(self) -> Dict[str, Any]:
        """Get current correlation snapshot"""
        with self.lock:
            return self.latest_data.copy()
    
    def stop(self):
        """Stop the collector"""
        self.running = False
        if YFINANCE_AVAILABLE:
            print("✅ YahooFinanceCollector stopped")
