# 🚀 Quick Reference Card

## System Access

### Web Dashboards
```
Basic:    http://localhost:8080/
Advanced: http://localhost:8080/advanced  ⭐ RECOMMENDED
```

### API Endpoints
```
Status:     http://localhost:8080/api/status
Monitoring: http://localhost:8080/api/monitoring  ⭐ NEW
Errors:     http://localhost:8080/api/errors
```

## Quick Commands

### Check Status
```bash
# One-liner health check
curl -s http://localhost:8080/api/monitoring | python3 -c "import json,sys; d=json.load(sys.stdin); print(f\"DB: {d['db_metrics']['success_rate']:.1f}% | Alerts: {len(d['alerts'])}\")"
```

### View Logs
```bash
tail -50 factory.log  # Last 50 lines
tail -f factory.log   # Follow real-time
```

### Restart System
```bash
pkill -9 -f run_data_factory.py
nohup python3 run_data_factory.py > factory.log 2>&1 &
```

### Check Database
```bash
psql -U postgres -d crypto_data -c "SELECT COUNT(*) FROM feature_store;"
```

## Current Status
✅ Running: PID 35277
✅ Coverage: 100% (65/65 fields)
✅ DB Writes: 100% success
✅ Alerts: 0 active

## Files to Review
- `/DEPLOYMENT_READY.md` - Full deployment guide
- `/MONITORING_IMPLEMENTATION_SUMMARY.md` - Complete documentation  
- `/MONITORING_DEPLOYMENT.md` - Technical deployment steps
- `/web_ui/enhanced_dashboard.html` - Advanced UI
- `/infrastructure/monitoring.py` - Monitoring engine

## Support
Run health check: `~/check_crypto_factory.sh`
View advanced dashboard: `open http://localhost:8080/advanced`
