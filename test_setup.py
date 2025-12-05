"""
Test Script - Verify All Components Before Deployment
Run this to ensure everything is configured correctly
"""

import sys
import os

def test_imports():
    """Test if all modules can be imported"""
    print("\n🧪 Testing Imports...")
    try:
        from config.api_key_parser import APIKeyParser
        from infrastructure.key_manager import KeyManager
        from infrastructure.timescale_db import TimescaleDB
        from data_layer.collectors_binance import BinanceWebSocketCollector, BinanceRESTCollector
        from data_layer.collectors_other import DeltaExchangeCollector, CryptoPanicCollector
        print("✅ All imports successful")
        return True
    except Exception as e:
        print(f"❌ Import failed: {e}")
        return False

def test_api_keys():
    """Test if API keys are loaded correctly"""
    print("\n🔑 Testing API Key Loading...")
    try:
        from config.api_key_parser import APIKeyParser
        
        parser = APIKeyParser("apikey.txt")
        config = parser.parse()
        parser.add_proxies_from_file("iproyal-proxies.txt")
        
        # Verify we have keys
        assert len(config['delta_keys']) == 2, f"Expected 2 Delta keys, got {len(config['delta_keys'])}"
        assert len(config['cryptopanic_keys']) == 4, f"Expected 4 CryptoPanic keys, got {len(config['cryptopanic_keys'])}"
        assert len(config['alphavantage_keys']) == 30, f"Expected 30 Alpha Vantage keys, got {len(config['alphavantage_keys'])}"
        assert len(config['etherscan_keys']) == 3, f"Expected 3 Etherscan keys, got {len(config['etherscan_keys'])}"
        assert len(config['proxies']) == 30, f"Expected 30 proxies, got {len(config['proxies'])}"
        
        print("✅ All API keys loaded correctly")
        return True
    except Exception as e:
        print(f"❌ API key loading failed: {e}")
        return False

def test_key_manager():
    """Test KeyManager functionality"""
    print("\n🔄 Testing Key Manager...")
    try:
        from config.api_key_parser import APIKeyParser
        from infrastructure.key_manager import KeyManager
        
        parser = APIKeyParser("apikey.txt")
        config = parser.parse()
        
        km = KeyManager(config)
        
        # Test getting keys
        delta_key = km.get_key("delta")
        assert delta_key is not None, "Delta key is None"
        
        alphavantage_key = km.get_key("alphavantage")
        assert alphavantage_key is not None, "Alpha Vantage key is None"
        
        # Test increment
        result = km.increment("delta")
        assert result == True, "Increment failed"
        
        # Test proxy
        proxy = km.get_proxy()
        assert proxy is not None, "Proxy is None"
        
        print("✅ Key Manager working correctly")
        return True
    except Exception as e:
        print(f"❌ Key Manager test failed: {e}")
        return False

def test_database_connection():
    """Test database connection (Docker must be running)"""
    print("\n💾 Testing Database Connection...")
    print("⚠️  Make sure Docker is running: docker-compose up -d")
    
    try:
        from infrastructure.timescale_db import TimescaleDB
        
        db = TimescaleDB()
        
        # Test query
        result = db.query("SELECT NOW() as current_time")
        assert result is not None, "Query returned None"
        
        print(f"✅ Database connected: {result[0]['current_time']}")
        
        db.close()
        return True
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        print("   Make sure Docker is running: docker-compose up -d")
        return False

def test_collectors():
    """Test collector initialization"""
    print("\n📡 Testing Collectors...")
    try:
        from config.api_key_parser import APIKeyParser
        from infrastructure.key_manager import KeyManager
        from data_layer.collectors_binance import BinanceRESTCollector
        from data_layer.collectors_other import DeltaExchangeCollector
        
        parser = APIKeyParser("apikey.txt")
        config = parser.parse()
        km = KeyManager(config)
        
        # Test Binance REST
        binance = BinanceRESTCollector("BTCUSDT", km)
        assert binance is not None
        
        # Test Delta
        delta = DeltaExchangeCollector(km)
        assert delta is not None
        
        print("✅ All collectors initialized successfully")
        return True
    except Exception as e:
        print(f"❌ Collector test failed: {e}")
        return False

def main():
    """Run all tests"""
    print("=" * 80)
    print("🧪 CRYPTO DATA FACTORY - SYSTEM TEST")
    print("=" * 80)
    
    tests = [
        ("Module Imports", test_imports),
        ("API Key Loading", test_api_keys),
        ("Key Manager", test_key_manager),
        ("Database Connection", test_database_connection),
        ("Collectors", test_collectors)
    ]
    
    results = []
    for name, test_func in tests:
        result = test_func()
        results.append((name, result))
    
    # Summary
    print("\n" + "=" * 80)
    print("📊 TEST SUMMARY")
    print("=" * 80)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {name}")
    
    all_passed = all(r[1] for r in results)
    
    print("\n" + "=" * 80)
    if all_passed:
        print("🎉 ALL TESTS PASSED! System is ready for deployment.")
        print("\nNext steps:")
        print("1. Start the data factory: python run_data_factory.py")
        print("2. Open Web UI: http://localhost:5000")
        print("3. Monitor for a few hours to ensure stability")
        print("4. Deploy to VPS following README_SETUP.txt")
    else:
        print("⚠️  SOME TESTS FAILED! Please fix issues before deployment.")
        print("\nCommon fixes:")
        print("- Install dependencies: pip install -r requirements.txt")
        print("- Start Docker: docker-compose up -d")
        print("- Check apikey.txt and iproyal-proxies.txt exist")
    print("=" * 80)
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())
