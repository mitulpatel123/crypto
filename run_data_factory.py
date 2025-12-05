"""
CRYPTO DATA FACTORY - Main Orchestration Script
Runs 24x7 data collection with all collectors and database storage
"""

import time
import threading
import signal
import sys
from datetime import datetime
import numpy as np  # For volatility calculation

# Import our modules
from config.api_key_parser import APIKeyParser
from infrastructure.key_manager import KeyManager
from infrastructure.timescale_db import TimescaleDB
from data_layer.collectors_binance import BinanceWebSocketCollector, BinanceRESTCollector
from data_layer.collectors_other import (
    DeltaExchangeCollector,
    CryptoPanicCollector,
    AlphaVantageCollector,
    EtherscanCollector,
    AlternativeMeCollector
)
from data_layer.collectors_deribit import DeribitCollector  # NEW: Deribit for Greeks
from data_layer.collectors_yfinance import YahooFinanceCollector  # NEW: Yahoo for correlations
from data_layer.collectors_coinglass import CoinGlassCollector  # NEW: CoinGlass for OI changes
from data_layer.collectors_coinalyze import CoinalyzeCollector  # NEW: Coinalyze for liquidations + PCR
from data_layer.collectors_fred import FREDCollector  # NEW: FRED for macro data
from web_ui.status_server import run_server, update_status


# Global shutdown flag
shutdown_event = threading.Event()


def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully"""
    print("\n\n⚠️  Shutdown signal received. Stopping gracefully...")
    shutdown_event.set()


def main():
    """Main orchestration function"""
    print("=" * 80)
    print("🚀 CRYPTO DATA FACTORY - STARTING UP")
    print("=" * 80)
    
    # Register signal handler for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Step 1: Parse API keys
    print("\n📝 Step 1: Loading API Keys...")
    parser = APIKeyParser(apikey_file="apikey.txt")
    config = parser.parse()
    parser.add_proxies_from_file("iproyal-proxies.txt")
    
    # Step 2: Initialize Key Manager
    print("\n🔑 Step 2: Initializing Key Manager...")
    key_manager = KeyManager(config)
    
    # Step 3: Initialize Database
    print("\n💾 Step 3: Connecting to TimescaleDB...")
    db = TimescaleDB()
    
    # Step 4: Initialize Collectors
    print("\n📡 Step 4: Initializing Data Collectors...")
    
    # Binance collectors
    binance_ws = BinanceWebSocketCollector(symbol="btcusdt", proxy_manager=key_manager)
    binance_rest = BinanceRESTCollector(symbol="BTCUSDT", key_manager=key_manager)
    
    # Threaded collectors (will run in background)
    delta = DeltaExchangeCollector(key_manager)
    cryptopanic = CryptoPanicCollector(key_manager)
    alphavantage = AlphaVantageCollector(key_manager)
    etherscan = EtherscanCollector(key_manager)
    alternative_me = AlternativeMeCollector()
    
    # NEW COLLECTORS for 100% data coverage
    deribit = DeribitCollector()  # For Greeks (IV, Delta, Theta, Vega) + Black-Scholes + PCR
    yfinance_collector = YahooFinanceCollector()  # For SPX and DXY correlations
    coinglass = CoinGlassCollector()  # For OI changes only (4h, 24h)
    coinalyze = CoinalyzeCollector()  # For liquidations (3 keys = 300 calls/day)
    fred = FREDCollector(key_manager)  # For macro data (DXY, 10Y, M2)
    
    # Collector status tracking
    collectors_status = {
        "Binance WS": "starting",
        "Delta": "running",
        "News": "running",
        "Sentiment": "running"
    }
    
    # Step 5: Start ALL background threads
    print("\n🔌 Step 5: Starting All Collectors...")
    
    # Start Binance WebSocket
    threading.Thread(target=binance_ws.run, daemon=True).start()
    
    # Start threaded collectors
    delta.start()
    cryptopanic.start()
    alphavantage.start()
    etherscan.start()
    alternative_me.start()
    
    # Start NEW collectors for 100% data coverage
    deribit.start()
    yfinance_collector.start()
    coinglass.start()  # CoinGlass OI changes (FIXED endpoints)
    coinalyze.start()  # Coinalyze liquidations (3 API keys)
    fred.start()  # FRED macro data
    
    time.sleep(3)  # Wait for connections
    
    # Step 6: Start Web UI in separate thread
    print("\n🌐 Step 6: Starting Web UI...")
    ui_thread = threading.Thread(
        target=run_server,
        kwargs={"host": "0.0.0.0", "port": 8080},
        daemon=True
    )
    ui_thread.start()
    time.sleep(2)
    
    print("\n" + "=" * 80)
    print("✅ ALL SYSTEMS ONLINE - DATA COLLECTION STARTED")
    print("=" * 80)
    print(f"📊 Web UI: http://localhost:8080")
    print(f"💾 Database: feature_store table")
    print(f"🔄 Collection Frequency: Every 1 second")
    print(f"⏹️  Press Ctrl+C to stop gracefully")
    print("=" * 80 + "\n")
    
    # Main data collection loop
    iteration = 0
    
    # Storage for local calculations
    price_history = []  # For volatility calculation
    last_known = {  # For forward fill of slow-updating data
        "funding_rate": 0.0,
        "funding_predicted": 0.0,
        "open_interest": 0.0,
        "long_short_ratio": 0.0
    }
    
    while not shutdown_event.is_set():
        try:
            iteration += 1
            
            # Aggregate data from all collectors (INSTANT - just reading cached data)
            now = datetime.now()
            row = {
                "timestamp": now,
                "symbol": "BTCUSDT",
                # Add time-based features FIRST (before get_snapshot overwrites)
                "time_hour": now.hour,
                "time_day": now.weekday(),  # 0=Monday, 6=Sunday
                "is_weekend": now.weekday() >= 5  # Saturday=5, Sunday=6
            }
            
            # Get real-time data (non-blocking snapshots) - these should NOT overwrite time features
            row.update(binance_ws.get_snapshot())
            row.update(delta.get_snapshot())
            row.update(cryptopanic.get_snapshot())
            row.update(alphavantage.get_snapshot())
            row.update(etherscan.get_snapshot())
            row.update(alternative_me.get_snapshot())
            
            # Get NEW data sources (Deribit, Yahoo, CoinGlass OI, Coinalyze Liq, FRED)
            row.update(deribit.get_snapshot())  # Enhanced: Greeks + Black-Scholes + PCR
            row.update(yfinance_collector.get_snapshot())  # SPX/DXY correlations
            row.update(coinglass.get_snapshot())  # CoinGlass: OI 1h/4h/24h changes (FIXED)
            row.update(coinalyze.get_snapshot())  # Coinalyze: Liquidations (FREE 300 calls/day)
            row.update(fred.get_snapshot())  # FRED: DXY, 10Y, M2
            
            # Get Binance REST data (every 60 seconds)
            if iteration % 60 == 0:
                binance_rest.fetch_funding_rate()
                binance_rest.fetch_open_interest()
                binance_rest.fetch_long_short_ratio()
                row.update(binance_rest.get_snapshot())
            
            # === LOCAL CALCULATIONS FOR 100% DATA COVERAGE ===
            
            # 1. Calculate Historical Volatility (HV) from recent prices
            price = row.get('close', 0)
            if price > 0:
                price_history.append(price)
                if len(price_history) > 60:  # Keep last 60 seconds
                    price_history.pop(0)
                
                if len(price_history) >= 10:  # Need at least 10 points
                    # Calculate returns
                    returns = np.diff(price_history) / np.array(price_history[:-1])
                    # Annualized volatility (assuming 1-second intervals)
                    row['volatility_hv'] = float(np.std(returns) * np.sqrt(365 * 24 * 60 * 60))
            
            # 2. Forward Fill slow-updating data (so it's never None/NaN)
            # Update last_known values when Binance REST provides fresh data
            if row.get('funding_rate') is not None and row.get('funding_rate') != 0:
                last_known['funding_rate'] = row['funding_rate']
            if row.get('funding_predicted') is not None and row.get('funding_predicted') != 0:
                last_known['funding_predicted'] = row['funding_predicted']
            if row.get('open_interest') is not None and row.get('open_interest') != 0:
                last_known['open_interest'] = row['open_interest']
            if row.get('long_short_ratio') is not None and row.get('long_short_ratio') != 0:
                last_known['long_short_ratio'] = row['long_short_ratio']
            
            # Fill current row with last known values (prevents NaN gaps)
            row['funding_rate'] = row.get('funding_rate') or last_known['funding_rate']
            row['funding_predicted'] = row.get('funding_predicted') or last_known['funding_predicted']
            row['open_interest'] = row.get('open_interest') or last_known['open_interest']
            row['long_short_ratio'] = row.get('long_short_ratio') or last_known['long_short_ratio']
            
            # 3. Calculate order book walls (if detected)
            # Logic is already in Binance collector, but ensure it's not None
            if row.get('ob_wall_bid') is None:
                row['ob_wall_bid'] = 0.0
            if row.get('ob_wall_ask') is None:
                row['ob_wall_ask'] = 0.0
            
            # Insert into database
            if row.get("timestamp"):
                db.insert_single(row)
                
                if iteration % 10 == 0:  # Print every 10 seconds
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] "
                          f"💾 Row {iteration} | "
                          f"Price: ${row.get('close', 0):.2f} | "
                          f"OI: ${row.get('open_interest', 0):,.0f}")
            
            # Update web UI status (every 5 seconds)
            if iteration % 5 == 0:
                update_status(key_manager, db, collectors_status)
            
            # Sleep for 1 second (1Hz collection frequency)
            time.sleep(1)
            
        except KeyboardInterrupt:
            print("\n⚠️  Keyboard interrupt received...")
            break
        except Exception as e:
            print(f"❌ Error in main loop: {e}")
            time.sleep(5)  # Wait before retry
    
    # Cleanup
    print("\n🛑 Shutting down...")
    binance_ws.stop()
    db.close()
    print("✅ Shutdown complete. Goodbye!")


if __name__ == "__main__":
    main()
