"""
CRYPTO DATA FACTORY - Main Orchestration Script
Runs 24x7 data collection with all collectors and database storage
"""

import time
import threading
import signal
import sys
from datetime import datetime

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
    
    # Other collectors
    delta = DeltaExchangeCollector(key_manager)
    cryptopanic = CryptoPanicCollector(key_manager)
    alphavantage = AlphaVantageCollector(key_manager)
    etherscan = EtherscanCollector(key_manager)
    alternative_me = AlternativeMeCollector()
    
    # Collector status tracking
    collectors_status = {
        "Binance WebSocket": "starting",
        "Binance REST": "ok",
        "Delta Exchange": "ok",
        "CryptoPanic": "ok",
        "Alpha Vantage": "ok",
        "Etherscan": "ok",
        "Alternative.me": "ok"
    }
    
    # Step 5: Start Binance WebSocket in separate thread
    print("\n🔌 Step 5: Starting WebSocket Collectors...")
    def run_binance_ws():
        try:
            collectors_status["Binance WebSocket"] = "running"
            binance_ws.run()  # Blocking call
        except Exception as e:
            print(f"❌ Binance WebSocket error: {e}")
            collectors_status["Binance WebSocket"] = "error"
    
    ws_thread = threading.Thread(target=run_binance_ws, daemon=True)
    ws_thread.start()
    time.sleep(3)  # Wait for WebSocket to connect
    
    # Step 6: Start Web UI in separate thread
    print("\n🌐 Step 6: Starting Web UI...")
    ui_thread = threading.Thread(
        target=run_server,
        kwargs={"host": "0.0.0.0", "port": 5000},
        daemon=True
    )
    ui_thread.start()
    time.sleep(2)
    
    print("\n" + "=" * 80)
    print("✅ ALL SYSTEMS ONLINE - DATA COLLECTION STARTED")
    print("=" * 80)
    print(f"📊 Web UI: http://localhost:5000")
    print(f"💾 Database: feature_store table")
    print(f"🔄 Collection Frequency: Every 1 second")
    print(f"⏹️  Press Ctrl+C to stop gracefully")
    print("=" * 80 + "\n")
    
    # Main data collection loop
    iteration = 0
    last_delta_fetch = 0
    last_cryptopanic_fetch = 0
    last_alphavantage_fetch = 0
    last_etherscan_fetch = 0
    last_fear_greed_fetch = 0
    
    while not shutdown_event.is_set():
        try:
            iteration += 1
            current_time = time.time()
            
            # Aggregate data from all collectors
            row = {
                "timestamp": datetime.now(),
                "symbol": "BTCUSDT"
            }
            
            # Get Binance WebSocket data (real-time)
            ws_data = binance_ws.get_snapshot()
            row.update(ws_data)
            
            # Get Binance REST data (every 60 seconds)
            if iteration % 60 == 0:
                binance_rest.fetch_funding_rate()
                binance_rest.fetch_open_interest()
                binance_rest.fetch_long_short_ratio()
                rest_data = binance_rest.get_snapshot()
                row.update(rest_data)
            
            # Delta Exchange (every 10 seconds)
            if current_time - last_delta_fetch >= 10:
                if delta.fetch_ticker():
                    row.update(delta.get_snapshot())
                    last_delta_fetch = current_time
            
            # CryptoPanic (every 5 minutes = 300 seconds)
            # With 4 keys × 100 req/month = 400 req/month = ~13 req/day
            # Every 5 min = 288 req/day, so we need to be careful!
            if current_time - last_cryptopanic_fetch >= 600:  # Every 10 minutes instead
                if cryptopanic.fetch_news():
                    row.update(cryptopanic.get_snapshot())
                    last_cryptopanic_fetch = current_time
            
            # Alpha Vantage (every 30 minutes)
            # With 30 keys × 25 req/day = 750 req/day
            # Every 30 min = 48 req/day (well within limits!)
            if current_time - last_alphavantage_fetch >= 1800:
                if alphavantage.fetch_crypto_sentiment():
                    row.update(alphavantage.get_snapshot())
                    last_alphavantage_fetch = current_time
            
            # Etherscan (every 60 seconds)
            if current_time - last_etherscan_fetch >= 60:
                if etherscan.fetch_whale_movements():
                    row.update(etherscan.get_snapshot())
                    last_etherscan_fetch = current_time
            
            # Fear & Greed (every 30 minutes, data updates every 8 hours anyway)
            if current_time - last_fear_greed_fetch >= 1800:
                if alternative_me.fetch_fear_greed():
                    row.update(alternative_me.get_snapshot())
                    last_fear_greed_fetch = current_time
            
            # Insert into database
            if row.get("timestamp"):
                db.insert_single(row)
                
                if iteration % 10 == 0:  # Print every 10 seconds
                    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] "
                          f"💾 Row {iteration} saved | "
                          f"Price: ${row.get('close', 0):.2f} | "
                          f"Funding: {row.get('funding_rate', 0):.6f} | "
                          f"OI: ${row.get('open_interest', 0):,.0f} | "
                          f"Fear/Greed: {row.get('fear_greed_index', 50)}")
            
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
