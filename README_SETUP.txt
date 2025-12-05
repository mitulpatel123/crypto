================================================================================
    CRYPTO DATA FACTORY - COMPLETE SETUP GUIDE
    24x7 Data Collection System with Web UI Monitoring
================================================================================

📋 WHAT YOU HAVE NOW:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ 2 Delta Exchange API keys
✅ 4 CryptoPanic API keys (100 req/month each)
✅ 3 Etherscan API keys (100k req/day each)
✅ 30 Alpha Vantage API keys (25 req/day each = 750 req/day total!)
✅ 4 FRED API keys
✅ 13 CoinGecko API keys
✅ 30 IPRoyal proxies (Germany location for Binance access)
✅ Complete project structure with all collectors
✅ Web UI for monitoring at http://localhost:5000


📁 PROJECT STRUCTURE:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Crypto/
├── apikey.txt                          # ✅ ALL YOUR API KEYS (FILLED)
├── iproyal-proxies.txt                 # ✅ 30 PROXIES
├── docker-compose.yml                  # TimescaleDB setup
├── requirements.txt                    # Python dependencies
├── .gitignore                          # Security (excludes apikey.txt)
│
├── config/
│   ├── __init__.py
│   └── api_key_parser.py              # Parses apikey.txt
│
├── infrastructure/
│   ├── __init__.py
│   ├── key_manager.py                 # Smart key rotation & rate limiting
│   └── timescale_db.py                # Database handler (60 columns)
│
├── data_layer/
│   ├── __init__.py
│   ├── collectors_binance.py          # Binance WS + REST (2025 endpoints)
│   └── collectors_other.py            # Delta, CryptoPanic, etc.
│
├── web_ui/
│   ├── __init__.py
│   └── status_server.py               # Flask web UI
│
└── run_data_factory.py                # 🚀 MAIN SCRIPT


🚀 QUICK START (LOCAL TESTING):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. Start Database:
   cd /Users/mitulpatel/StudioProjects/Mitul/Crypto
   docker-compose up -d

2. Install Python Dependencies:
   pip install -r requirements.txt

3. Run the Data Factory:
   python run_data_factory.py

4. Open Web UI:
   http://localhost:5000

5. Monitor:
   - See all API key usage in real-time
   - Track which keys are active
   - Monitor rate limits (green/yellow/red)
   - View database row count


🔧 VPS DEPLOYMENT (24x7 PRODUCTION):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

STEP 1: Prepare for GitHub
────────────────────────────────────────────────────────────────────────────
# Initialize git (if not already done)
cd /Users/mitulpatel/StudioProjects/Mitul/Crypto
git init
git add .
git commit -m "Initial Crypto Data Factory setup"

# Create GitHub repo (on github.com)
# Then push:
git remote add origin https://github.com/YOUR_USERNAME/Crypto_Data_Factory.git
git branch -M main
git push -u origin main

⚠️  IMPORTANT: apikey.txt is in .gitignore and will NOT be pushed!


STEP 2: Setup VPS
────────────────────────────────────────────────────────────────────────────
# SSH into your VPS
ssh root@YOUR_VPS_IP

# Update system
apt update && apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh

# Install Docker Compose
apt install docker-compose -y

# Install Python 3.11+
apt install python3 python3-pip python3-venv -y

# Install Git
apt install git -y


STEP 3: Clone & Setup
────────────────────────────────────────────────────────────────────────────
# Clone your repo
git clone https://github.com/YOUR_USERNAME/Crypto_Data_Factory.git
cd Crypto_Data_Factory

# Copy apikey.txt from your local machine to VPS
# On your LOCAL machine:
scp /Users/mitulpatel/StudioProjects/Mitul/Crypto/apikey.txt root@YOUR_VPS_IP:~/Crypto_Data_Factory/

# On VPS: Verify apikey.txt is there
cat apikey.txt  # Should show all your keys

# Install Python dependencies
pip3 install -r requirements.txt


STEP 4: Start Services
────────────────────────────────────────────────────────────────────────────
# Start TimescaleDB
docker-compose up -d

# Wait 10 seconds for database to initialize
sleep 10

# Test run (Ctrl+C to stop)
python3 run_data_factory.py

# If everything works, proceed to Step 5


STEP 5: Run 24x7 with systemd
────────────────────────────────────────────────────────────────────────────
# Create systemd service
cat > /etc/systemd/system/crypto-factory.service << 'EOF'
[Unit]
Description=Crypto Data Factory
After=network.target docker.service
Requires=docker.service

[Service]
Type=simple
User=root
WorkingDirectory=/root/Crypto_Data_Factory
ExecStart=/usr/bin/python3 /root/Crypto_Data_Factory/run_data_factory.py
Restart=always
RestartSec=10
StandardOutput=append:/root/Crypto_Data_Factory/logs/factory.log
StandardError=append:/root/Crypto_Data_Factory/logs/error.log

[Install]
WantedBy=multi-user.target
EOF

# Create logs directory
mkdir -p logs

# Reload systemd
systemctl daemon-reload

# Enable auto-start on boot
systemctl enable crypto-factory

# Start the service
systemctl start crypto-factory

# Check status
systemctl status crypto-factory

# View logs (live)
tail -f logs/factory.log


STEP 6: Access Web UI
────────────────────────────────────────────────────────────────────────────
# Open in browser:
http://YOUR_VPS_IP:5000

# If firewall is blocking:
ufw allow 5000/tcp
ufw reload


📊 MONITORING & MAINTENANCE:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

View Logs:
  tail -f logs/factory.log
  tail -f logs/error.log

Check Service Status:
  systemctl status crypto-factory

Restart Service:
  systemctl restart crypto-factory

Stop Service:
  systemctl stop crypto-factory

Check Database:
  docker exec -it crypto_timescaledb psql -U postgres -d crypto_data
  SELECT COUNT(*) FROM feature_store;
  SELECT * FROM feature_store ORDER BY timestamp DESC LIMIT 10;
  \q

Backup Database:
  docker exec crypto_timescaledb pg_dump -U postgres crypto_data > backup_$(date +%Y%m%d).sql


📈 EXPECTED DATA COLLECTION RATES:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Binance WebSocket:        Real-time (100ms updates)
Binance REST:             Every 60 seconds
Delta Exchange:           Every 10 seconds
CryptoPanic:              Every 10 minutes (to stay within monthly limit)
Alpha Vantage:            Every 30 minutes (30 keys = plenty of capacity!)
Etherscan:                Every 60 seconds
Alternative.me:           Every 30 minutes

DATABASE GROWTH:
  - 1 row per second = 86,400 rows/day
  - ~2.6 million rows/month
  - ~1GB/month (with all 60 columns)


🔑 API KEY USAGE (WITH YOUR KEYS):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Delta Exchange:
  - 2 keys × 50 req/min = 100 req/min total
  - Current usage: ~6 req/min (every 10 sec)
  - Status: ✅ EXCELLENT (only 6% capacity)

CryptoPanic:
  - 4 keys × 100 req/month = 400 req/month total
  - Current usage: ~300 req/month (every 10 min)
  - Status: ✅ GOOD (75% capacity, safe margin)

Etherscan:
  - 3 keys × 100k/day = 300k requests/day total
  - Current usage: ~13k req/day
  - Status: ✅ EXCELLENT (only 4% capacity)

Alpha Vantage:
  - 30 keys × 25 req/day = 750 requests/day total
  - Current usage: 48 req/day (every 30 min)
  - Status: ✅ EXCELLENT (only 6% capacity!)

FRED:
  - 4 keys × 120 req/min = 480 req/min
  - Current usage: <1 req/hour
  - Status: ✅ EXCELLENT (massive headroom)

CoinGecko:
  - 13 keys × 10k/month = 130k req/month
  - Current usage: BACKUP ONLY (used when needed)
  - Status: ✅ EXCELLENT


🔥 TROUBLESHOOTING:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Problem: "Database connection failed"
Solution: docker-compose up -d
          Wait 10 seconds and retry

Problem: "API rate limit reached"
Solution: Web UI will show which keys are exhausted
          System auto-rotates to next key

Problem: "WebSocket disconnected"
Solution: Auto-reconnects in 5 seconds
          Check logs for errors

Problem: "Can't access Web UI"
Solution: Check firewall: ufw allow 5000/tcp
          Or use SSH tunnel: ssh -L 5000:localhost:5000 root@YOUR_VPS_IP

Problem: "Service crashes"
Solution: systemctl restart crypto-factory
          Check logs: tail -f logs/error.log


🎯 NEXT STEPS:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. ✅ Test locally (already done)
2. ✅ Push to GitHub
3. ✅ Deploy to VPS
4. ✅ Monitor for 24 hours
5. ⭐ Scale up: Add more symbols (ETHUSDT, SOLUSDT)
6. ⭐ Add alerting (Telegram/Email when errors occur)
7. ⭐ Add data analysis scripts


📞 SUPPORT:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

If you encounter issues:
1. Check logs: tail -f logs/factory.log
2. Check Web UI: http://YOUR_VPS_IP:5000
3. Check database: docker exec -it crypto_timescaledb psql -U postgres -d crypto_data
4. Review API_KEYS_REQUIREMENTS_2025.txt for rate limit details


🎉 YOU'RE ALL SET!
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Your Crypto Data Factory is ready to run 24x7!

With your API keys:
✅ 30 Alpha Vantage keys = 750 requests/day capacity
✅ Smart rotation prevents any rate limit issues
✅ Germany proxies ensure Binance access
✅ Web UI shows live status of all keys
✅ TimescaleDB stores 60 columns of data
✅ Auto-reconnects on any failures

Happy Data Collecting! 🚀📊💰
