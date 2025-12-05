# 🚀 Crypto Data Factory

**24x7 Cryptocurrency Data Collection System** with smart API key rotation, real-time monitoring, and TimescaleDB storage.

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## 📋 Overview

This system collects **60+ cryptocurrency features** every second from multiple data sources:

- **Binance** - Real-time price, volume, orderbook (WebSocket + REST)
- **Delta Exchange** - Options Greeks, implied volatility
- **CryptoPanic** - News sentiment analysis
- **Alpha Vantage** - Social sentiment hype index
- **Etherscan** - Whale movements on-chain
- **Alternative.me** - Fear & Greed Index

**Key Features:**
- ✅ Smart API key rotation (auto-switch at 95% limit)
- ✅ IPRoyal proxy support (bypass geo-restrictions)
- ✅ Real-time web UI monitoring (http://localhost:5000)
- ✅ TimescaleDB for optimized time-series storage
- ✅ Production-ready systemd service configuration

---

## 🏗️ Architecture

```
Data Sources → API Key Manager → Collectors → TimescaleDB
                     ↓
                Web UI (Flask)
```

**Stack:**
- Python 3.8+
- TimescaleDB (PostgreSQL extension)
- Flask (Web UI)
- Docker Compose

---

## 📦 Quick Start

### 1. Clone Repository
```bash
git clone https://github.com/mitulpatel123/crypto.git
cd crypto
```

### 2. Setup API Keys
```bash
# Copy template and fill with your API keys
cp apikey.txt.template apikey.txt
nano apikey.txt  # Add your real keys
```

**Required API Keys:**
- [Delta Exchange](https://www.delta.exchange/) - Options data
- [CryptoPanic](https://cryptopanic.com/developers/api/) - News sentiment
- [Etherscan](https://docs.etherscan.io/) - Blockchain data
- [Alpha Vantage](https://www.alphavantage.co/support/#api-key) - Market sentiment
- [FRED](https://fred.stlouisfed.org/docs/api/api_key.html) - Economic data
- [CoinGecko](https://www.coingecko.com/en/api) - Market data

### 3. Install Dependencies
```bash
# Python packages
pip install -r requirements.txt

# Docker (for TimescaleDB)
docker-compose up -d
```

### 4. Test Setup
```bash
python test_setup.py
```

### 5. Start Data Collection
```bash
python run_data_factory.py
```

**Access Web UI:** http://localhost:5000

---

## 📁 Project Structure

```
crypto/
├── config/
│   └── api_key_parser.py      # Parse apikey.txt format
├── infrastructure/
│   ├── key_manager.py         # Smart key rotation
│   └── timescale_db.py        # Database handler
├── data_layer/
│   ├── collectors_binance.py  # Binance WebSocket + REST
│   └── collectors_other.py    # Delta, CryptoPanic, etc.
├── web_ui/
│   └── status_server.py       # Flask monitoring dashboard
├── apikey.txt                 # Your API keys (gitignored)
├── apikey.txt.template        # API key format reference
├── docker-compose.yml         # TimescaleDB setup
├── requirements.txt           # Python dependencies
└── run_data_factory.py        # Main entry point
```

---

## 🔑 API Key Management

The system uses a custom format in `apikey.txt`:

```ini
[DELTA_EXCHANGE]
api_key:api_secret:50

[CRYPTOPANIC]
token:100

[ETHERSCAN]
api_key:100000
```

**Smart Rotation:**
- Automatically switches to next key at 95% usage
- Tracks per-minute, daily, and monthly limits
- Prevents rate limit violations

---

## 💾 Database Schema

TimescaleDB hypertable with **60 columns**:

| Category | Columns | Examples |
|----------|---------|----------|
| Price & Volume | 10 | open, high, low, close, volume, vwap |
| Order Book | 15 | bid_ask_spread, ob_imbalance_5 |
| Derivatives | 15 | funding_rate, open_interest, implied_volatility |
| Sentiment | 10 | news_sentiment, fear_greed_index, whale_inflow |

**Chunk Interval:** 1 day for optimal query performance

---

## 🌐 Web UI

Access real-time monitoring at **http://localhost:5000**

**Features:**
- Live API key usage with progress bars
- Color-coded status (green/yellow/red)
- Database row count
- Collector status indicators
- Auto-refresh every 5 seconds

---

## 🔒 Security

**Protected Files (NOT in Git):**
- `apikey.txt` - Your real API keys
- `iproyal-proxies.txt` - Proxy credentials

**Safe to Commit:**
- `apikey.txt.template` - Format reference
- All code files

**Security Measures:**
- No raw API secrets in HTTP headers
- Public endpoints used when possible
- HTTPS for all external API calls
- Proxy support for anonymity

---

## 📊 Data Collection Frequencies

| Source | Frequency | Rate Limit |
|--------|-----------|------------|
| Binance WebSocket | Real-time (100ms) | No auth required |
| Binance REST | 60 seconds | Public endpoints |
| Delta Exchange | 10 seconds | 50 req/min |
| CryptoPanic | 10 minutes | 100 req/MONTH ⚠️ |
| Alpha Vantage | 30 minutes | 25 req/day per key |
| Etherscan | 60 seconds | 100k req/day |
| Fear & Greed | 30 minutes | No limit |

**Note:** CryptoPanic has the tightest limit (monthly reset)

---

## 🚀 VPS Deployment

### 1. Install System Dependencies
```bash
sudo apt update
sudo apt install docker.io docker-compose python3-pip -y
```

### 2. Clone and Setup
```bash
git clone https://github.com/mitulpatel123/crypto.git
cd crypto
pip3 install -r requirements.txt
```

### 3. Copy API Keys (from local machine)
```bash
scp apikey.txt user@vps-ip:~/crypto/
scp iproyal-proxies.txt user@vps-ip:~/crypto/
```

### 4. Start Services
```bash
docker-compose up -d
python3 run_data_factory.py
```

### 5. Setup Systemd Service (Optional)
See `README_SETUP.txt` for full systemd configuration.

---

## 📈 Expected Data Volume

- **Rows per day:** ~86,400 (1 row/second)
- **Storage growth:** ~1 GB/month
- **Database size (1 year):** ~12 GB

**TimescaleDB compression** can reduce this by 90%+

---

## 🛠️ Troubleshooting

### Database Connection Failed
```bash
docker-compose ps  # Check if TimescaleDB is running
docker-compose logs  # View container logs
```

### API Rate Limit Errors
```bash
# Check web UI at http://localhost:5000
# Look for red/yellow status indicators
```

### WebSocket Disconnected
```bash
# System auto-reconnects every 5 seconds
# Check Binance status: https://www.binance.com/en/support/announcement
```

---

## 📝 Configuration Files

- **`docker-compose.yml`** - TimescaleDB configuration
- **`apikey.txt`** - Your API keys (create from template)
- **`iproyal-proxies.txt`** - Germany proxy list (optional)
- **`requirements.txt`** - Python dependencies

---

## 🤝 Contributing

This is a private data collection system. For production use:

1. Add proper error handling
2. Implement data validation
3. Add unit tests
4. Setup monitoring alerts
5. Configure database backups

---

## 📄 License

MIT License - See LICENSE file for details

---

## 🙏 Credits

**Data Sources:**
- [Binance](https://www.binance.com/) - Cryptocurrency exchange
- [Delta Exchange](https://www.delta.exchange/) - Options & futures
- [CryptoPanic](https://cryptopanic.com/) - News aggregator
- [Alpha Vantage](https://www.alphavantage.co/) - Market intelligence
- [Etherscan](https://etherscan.io/) - Ethereum blockchain explorer
- [Alternative.me](https://alternative.me/) - Fear & Greed Index

**Built with:**
- Python 3.8+
- TimescaleDB
- Flask
- Docker

---

## 📞 Support

For issues or questions:
1. Check `README_SETUP.txt` for detailed setup instructions
2. Review `SECURITY_FIXES_APPLIED.md` for security best practices
3. View `NEXT_STEPS.txt` for quick start guide

---

**Happy Data Collecting! 🚀📊**
