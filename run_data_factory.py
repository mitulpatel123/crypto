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
    
    # Threaded collectors (will run in background)
    delta = DeltaExchangeCollector(key_manager)
    cryptopanic = CryptoPanicCollector(key_manager)
    alphavantage = AlphaVantageCollector(key_manager)
    etherscan = EtherscanCollector(key_manager)
    alternative_me = AlternativeMeCollector()
    
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
    
    time.sleep(3)  # Wait for connections
    
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
    
    while not shutdown_event.is_set():
        try:
            iteration += 1
            
            # Aggregate data from all collectors (INSTANT - just reading cached data)
            row = {
                "timestamp": datetime.now(),
                "symbol": "BTCUSDT"
            }
            
            # Get real-time data (non-blocking snapshots)
            row.update(binance_ws.get_snapshot())
            row.update(delta.get_snapshot())
            row.update(cryptopanic.get_snapshot())
            row.update(alphavantage.get_snapshot())
            row.update(etherscan.get_snapshot())
            row.update(alternative_me.get_snapshot())
            
            # Get Binance REST data (every 60 seconds)
            if iteration % 60 == 0:
                binance_rest.fetch_funding_rate()
                binance_rest.fetch_open_interest()
                binance_rest.fetch_long_short_ratio()
                row.update(binance_rest.get_snapshot())
            
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
