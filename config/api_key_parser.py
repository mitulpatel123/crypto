"""
API Key Parser - Reads apikey.txt and converts to structured format
Supports the custom format with sections like [BINANCE], [DELTA_EXCHANGE], etc.
"""

import os
from typing import Dict, List, Any


class APIKeyParser:
    """Parse apikey.txt file into structured configuration"""
    
    def __init__(self, apikey_file: str = "apikey.txt"):
        self.apikey_file = apikey_file
        self.config = {
            "binance_keys": [],
            "delta_keys": [],
            "cryptopanic_keys": [],
            "etherscan_keys": [],
            "alphavantage_keys": [],
            "fred_keys": [],
            "coingecko_keys": [],
            "proxies": []
        }
    
    def parse(self) -> Dict[str, Any]:
        """Parse the apikey.txt file"""
        if not os.path.exists(self.apikey_file):
            print(f"⚠️  API key file not found: {self.apikey_file}")
            return self.config
        
        current_section = None
        
        with open(self.apikey_file, 'r') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                
                # Skip empty lines and comments
                if not line or line.startswith('#'):
                    continue
                
                # Detect section headers
                if line.startswith('[') and line.endswith(']'):
                    current_section = line[1:-1].upper()
                    continue
                
                # Parse keys based on current section
                try:
                    if current_section == 'BINANCE':
                        self._parse_binance(line)
                    elif current_section == 'DELTA_EXCHANGE':
                        self._parse_delta(line)
                    elif current_section == 'CRYPTOPANIC':
                        self._parse_cryptopanic(line)
                    elif current_section == 'ETHERSCAN':
                        self._parse_etherscan(line)
                    elif current_section == 'ALPHAVANTAGE':
                        self._parse_alphavantage(line)
                    elif current_section == 'FRED':
                        self._parse_fred(line)
                    elif current_section == 'COINGECKO':
                        self._parse_coingecko(line)
                except Exception as e:
                    print(f"⚠️  Error parsing line {line_num} in [{current_section}]: {e}")
        
        print(f"✅ Parsed API keys:")
        print(f"   - Binance: {len(self.config['binance_keys'])} keys")
        print(f"   - Delta Exchange: {len(self.config['delta_keys'])} keys")
        print(f"   - CryptoPanic: {len(self.config['cryptopanic_keys'])} keys")
        print(f"   - Etherscan: {len(self.config['etherscan_keys'])} keys")
        print(f"   - Alpha Vantage: {len(self.config['alphavantage_keys'])} keys")
        print(f"   - FRED: {len(self.config['fred_keys'])} keys")
        print(f"   - CoinGecko: {len(self.config['coingecko_keys'])} keys")
        
        return self.config
    
    def _parse_binance(self, line: str):
        """Parse: API_KEY:API_SECRET:LIMIT:TYPE"""
        parts = line.split(':')
        if len(parts) >= 4:
            self.config['binance_keys'].append({
                "api_key": parts[0],
                "api_secret": parts[1],
                "limit": int(parts[2]),
                "type": parts[3]
            })
    
    def _parse_delta(self, line: str):
        """Parse: API_KEY:API_SECRET:LIMIT"""
        parts = line.split(':')
        if len(parts) >= 3:
            self.config['delta_keys'].append({
                "api_key": parts[0],
                "api_secret": parts[1],
                "limit": int(parts[2])
            })
    
    def _parse_cryptopanic(self, line: str):
        """Parse: TOKEN:MONTHLY_LIMIT"""
        parts = line.split(':')
        if len(parts) >= 2:
            self.config['cryptopanic_keys'].append({
                "token": parts[0],
                "monthly_limit": int(parts[1]),
                "usage": 0  # Track monthly usage
            })
    
    def _parse_etherscan(self, line: str):
        """Parse: API_KEY:DAILY_LIMIT"""
        parts = line.split(':')
        if len(parts) >= 2:
            self.config['etherscan_keys'].append({
                "api_key": parts[0],
                "daily_limit": int(parts[1]),
                "usage": 0  # Track daily usage
            })
    
    def _parse_alphavantage(self, line: str):
        """Parse: API_KEY:DAILY_LIMIT"""
        parts = line.split(':')
        if len(parts) >= 2:
            self.config['alphavantage_keys'].append({
                "api_key": parts[0],
                "daily_limit": int(parts[1]),
                "usage": 0  # Track daily usage
            })
    
    def _parse_fred(self, line: str):
        """Parse: API_KEY:LIMIT_PER_MINUTE"""
        parts = line.split(':')
        if len(parts) >= 2:
            self.config['fred_keys'].append({
                "api_key": parts[0],
                "limit": int(parts[1])
            })
    
    def _parse_coingecko(self, line: str):
        """Parse: API_KEY:MONTHLY_LIMIT"""
        parts = line.split(':')
        if len(parts) >= 2:
            self.config['coingecko_keys'].append({
                "api_key": parts[0],
                "monthly_limit": int(parts[1]),
                "usage": 0  # Track monthly usage
            })
    
    def add_proxies_from_file(self, proxy_file: str = "iproyal-proxies.txt"):
        """Load proxies from iproyal-proxies.txt"""
        if not os.path.exists(proxy_file):
            print(f"⚠️  Proxy file not found: {proxy_file}")
            return
        
        with open(proxy_file, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                # Format: IP:PORT:USERNAME:PASSWORD
                parts = line.split(':')
                if len(parts) >= 4:
                    self.config['proxies'].append({
                        "host": parts[0],
                        "port": int(parts[1]),
                        "username": parts[2],
                        "password": parts[3]
                    })
        
        print(f"✅ Loaded {len(self.config['proxies'])} proxies from {proxy_file}")
