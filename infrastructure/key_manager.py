"""
Smart API Key Manager with Rotation Logic
Handles rate limiting, key rotation, and usage tracking for all APIs
"""

import time
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from collections import defaultdict
import json


class KeyManager:
    """Manages API keys, rotation, and rate limiting"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.lock = threading.Lock()
        
        # Track usage for each service
        self.usage = {
            "binance": {"index": 0, "count": 0, "reset_time": time.time()},
            "delta": {"index": 0, "count": 0, "reset_time": time.time()},
            "cryptopanic": {"index": 0, "count": 0, "reset_time": self._get_month_start()},
            "etherscan": {"index": 0, "count": 0, "reset_time": self._get_day_start()},
            "alphavantage": {"index": 0, "count": 0, "reset_time": self._get_day_start()},
            "fred": {"index": 0, "count": 0, "reset_time": time.time()},
            "coingecko": {"index": 0, "count": 0, "reset_time": self._get_month_start()}
        }
        
        # Track per-key usage (important for daily/monthly limits)
        self.key_usage = defaultdict(lambda: {"count": 0, "last_reset": time.time()})
        
        # Proxy rotation index
        self.proxy_index = 0
        
        print("✅ KeyManager initialized")
        self._print_key_summary()
    
    def _print_key_summary(self):
        """Print summary of available keys"""
        print(f"📊 API Key Summary:")
        print(f"   - Delta Exchange: {len(self.config.get('delta_keys', []))} keys")
        print(f"   - CryptoPanic: {len(self.config.get('cryptopanic_keys', []))} keys (100 req/month each)")
        print(f"   - Etherscan: {len(self.config.get('etherscan_keys', []))} keys (100k req/day each)")
        print(f"   - Alpha Vantage: {len(self.config.get('alphavantage_keys', []))} keys (25 req/day each)")
        print(f"   - FRED: {len(self.config.get('fred_keys', []))} keys")
        print(f"   - CoinGecko: {len(self.config.get('coingecko_keys', []))} keys (10k req/month each)")
        print(f"   - Proxies: {len(self.config.get('proxies', []))} available")
    
    def _get_day_start(self) -> float:
        """Get timestamp of today's midnight UTC"""
        now = datetime.utcnow()
        today_start = datetime(now.year, now.month, now.day)
        return today_start.timestamp()
    
    def _get_month_start(self) -> float:
        """Get timestamp of current month's start"""
        now = datetime.utcnow()
        month_start = datetime(now.year, now.month, 1)
        return month_start.timestamp()
    
    def get_key(self, service: str) -> Optional[Dict[str, Any]]:
        """Get next available API key for a service"""
        with self.lock:
            keys_config_name = f"{service}_keys"
            keys = self.config.get(keys_config_name, [])
            
            if not keys:
                print(f"⚠️  No keys available for {service}")
                return None
            
            # Check if we need to reset counters
            self._check_and_reset(service)
            
            # Get current key index
            idx = self.usage[service]["index"]
            key = keys[idx]
            
            return key
    
    def increment(self, service: str) -> bool:
        """
        Increment usage counter and rotate if needed
        Returns True if request can proceed, False if rate limit exceeded
        """
        with self.lock:
            keys_config_name = f"{service}_keys"
            keys = self.config.get(keys_config_name, [])
            
            if not keys:
                return False
            
            meta = self.usage[service]
            idx = meta["index"]
            key = keys[idx]
            
            # Get limit for this key
            limit = self._get_limit(service, key)
            
            # Reset if time window passed
            self._check_and_reset(service)
            
            # Check if we can make request
            if meta["count"] >= limit * 0.95:  # 95% threshold
                # Try to rotate to next key
                if self._rotate_key(service):
                    print(f"🔄 Rotated {service} key ({meta['count']}/{limit} used)")
                else:
                    print(f"⚠️  {service} rate limit reached! All keys exhausted.")
                    return False
            
            # Increment counter
            meta["count"] += 1
            
            # Track per-key usage
            key_id = self._get_key_id(service, key)
            self.key_usage[key_id]["count"] += 1
            
            return True
    
    def _get_limit(self, service: str, key: Dict) -> int:
        """Get rate limit for a service/key"""
        if service == "binance":
            return key.get("limit", 1200)
        elif service == "delta":
            return key.get("limit", 50)
        elif service == "cryptopanic":
            return key.get("monthly_limit", 100)
        elif service == "etherscan":
            return key.get("daily_limit", 100000)
        elif service == "alphavantage":
            return key.get("daily_limit", 25)
        elif service == "fred":
            return key.get("limit", 120)
        elif service == "coingecko":
            return key.get("monthly_limit", 10000)
        return 0
    
    def _get_key_id(self, service: str, key: Dict) -> str:
        """Generate unique ID for a key"""
        if service in ["binance", "delta"]:
            return f"{service}_{key.get('api_key', '')[:8]}"
        elif service in ["cryptopanic", "etherscan", "alphavantage", "fred", "coingecko"]:
            token = key.get('token') or key.get('api_key', '')
            return f"{service}_{token[:8]}"
        return f"{service}_unknown"
    
    def _check_and_reset(self, service: str):
        """Check if we need to reset counters based on time window"""
        meta = self.usage[service]
        now = time.time()
        
        if service in ["binance", "delta", "fred"]:
            # Per-minute limits (60 second window)
            if now - meta["reset_time"] > 60:
                meta["count"] = 0
                meta["reset_time"] = now
        
        elif service in ["etherscan", "alphavantage"]:
            # Daily limits (reset at midnight UTC)
            if now >= self._get_day_start() + 86400:  # Next day
                meta["count"] = 0
                meta["reset_time"] = self._get_day_start()
                # Reset all key usages
                for key_id in list(self.key_usage.keys()):
                    if key_id.startswith(service):
                        self.key_usage[key_id]["count"] = 0
        
        elif service in ["cryptopanic", "coingecko"]:
            # Monthly limits (reset on 1st of month)
            current_month_start = self._get_month_start()
            if meta["reset_time"] < current_month_start:
                meta["count"] = 0
                meta["reset_time"] = current_month_start
                # Reset all key usages
                for key_id in list(self.key_usage.keys()):
                    if key_id.startswith(service):
                        self.key_usage[key_id]["count"] = 0
    
    def _rotate_key(self, service: str) -> bool:
        """Rotate to next available key. Returns True if rotation successful"""
        keys_config_name = f"{service}_keys"
        keys = self.config.get(keys_config_name, [])
        
        if len(keys) <= 1:
            return False  # Can't rotate, only one key
        
        meta = self.usage[service]
        original_idx = meta["index"]
        
        # Try all keys
        for _ in range(len(keys)):
            meta["index"] = (meta["index"] + 1) % len(keys)
            new_key = keys[meta["index"]]
            key_id = self._get_key_id(service, new_key)
            
            # Check if this key has capacity
            key_usage = self.key_usage[key_id]["count"]
            limit = self._get_limit(service, new_key)
            
            if key_usage < limit * 0.95:
                meta["count"] = key_usage  # Set to current usage of this key
                return True
        
        # No keys available, revert to original
        meta["index"] = original_idx
        return False
    
    def get_proxy(self) -> Optional[Dict[str, Any]]:
        """Get next proxy in rotation"""
        with self.lock:
            proxies = self.config.get("proxies", [])
            if not proxies:
                return None
            
            proxy = proxies[self.proxy_index]
            self.proxy_index = (self.proxy_index + 1) % len(proxies)
            return proxy
    
    def get_proxy_dict(self) -> Optional[Dict[str, str]]:
        """Get proxy formatted for requests library"""
        proxy = self.get_proxy()
        if not proxy:
            return None
        
        # Format: http://username:password@host:port
        proxy_url = f"http://{proxy['username']}:{proxy['password']}@{proxy['host']}:{proxy['port']}"
        return {
            "http": proxy_url,
            "https": proxy_url
        }
    
    def get_status(self) -> Dict[str, Any]:
        """Get current status of all keys and usage"""
        with self.lock:
            status = {}
            
            for service in ["delta", "cryptopanic", "etherscan", "alphavantage", "fred", "coingecko"]:
                keys_config_name = f"{service}_keys"
                keys = self.config.get(keys_config_name, [])
                
                if not keys:
                    continue
                
                service_status = {
                    "total_keys": len(keys),
                    "current_key_index": self.usage[service]["index"],
                    "total_requests": self.usage[service]["count"],
                    "keys": []
                }
                
                for i, key in enumerate(keys):
                    key_id = self._get_key_id(service, key)
                    limit = self._get_limit(service, key)
                    used = self.key_usage[key_id]["count"]
                    
                    service_status["keys"].append({
                        "index": i,
                        "active": i == self.usage[service]["index"],
                        "used": used,
                        "limit": limit,
                        "percentage": round((used / limit * 100) if limit > 0 else 0, 2),
                        "status": "OK" if used < limit * 0.8 else "WARNING" if used < limit * 0.95 else "CRITICAL"
                    })
                
                status[service] = service_status
            
            return status
