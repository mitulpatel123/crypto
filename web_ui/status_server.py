"""
Simple Web UI for Monitoring API Status
Runs on http://localhost:5000
Shows real-time status of all API keys and data collection
"""

from flask import Flask, jsonify, render_template_string, request
from flask_cors import CORS
from typing import Dict, Any
import threading
import time
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from infrastructure.monitoring import MONITOR


app = Flask(__name__)
CORS(app)

# Global status storage (updated by main script)
API_STATUS = {
    "last_updated": None,
    "services": {},
    "database": {"status": "unknown", "rows": 0, "coverage": 0},
    "collectors": {},
    "field_stats": {}  # NEW: Per-field population stats
}


HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Crypto Data Factory - Production Dashboard</title>
    <meta http-equiv="refresh" content="10">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #0d1117; color: #c9d1d9; }
        .container { max-width: 1400px; margin: 0 auto; padding: 20px; }
        h1 { color: #58a6ff; margin-bottom: 10px; font-size: 2.2em; }
        .header { background: linear-gradient(135deg, #1f2937 0%, #111827 100%); padding: 25px; border-radius: 10px; margin-bottom: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.3); }
        .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 15px; margin-bottom: 20px; }
        .stat-card { background: #161b22; padding: 20px; border-radius: 8px; border-left: 4px solid; }
        .stat-card.green { border-color: #2ea043; }
        .stat-card.yellow { border-color: #d29922; }
        .stat-card.red { border-color: #da3633; }
        .stat-card.blue { border-color: #58a6ff; }
        .stat-value { font-size: 2.5em; font-weight: bold; margin: 10px 0; }
        .stat-label { color: #8b949e; font-size: 0.9em; }
        .service { background: #161b22; margin: 15px 0; padding: 20px; border-radius: 8px; border: 1px solid #30363d; }
        .service h2 { color: #58a6ff; margin-bottom: 15px; font-size: 1.3em; }
        .status-ok { color: #2ea043; }
        .status-warning { color: #d29922; }
        .status-critical, .status-error { color: #da3633; }
        .status-unknown { color: #6e7681; }
        table { width: 100%; border-collapse: collapse; margin-top: 10px; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #21262d; }
        th { background: #0d1117; color: #8b949e; font-weight: 600; }
        tr:hover { background: #0d1117; }
        .progress-bar { background: #21262d; height: 24px; border-radius: 4px; overflow: hidden; position: relative; }
        .progress-fill { height: 100%; transition: width 0.3s ease; }
        .progress-fill.green { background: linear-gradient(90deg, #2ea043, #3fb950); }
        .progress-fill.yellow { background: linear-gradient(90deg, #d29922, #e3b341); }
        .progress-fill.red { background: linear-gradient(90deg, #da3633, #f85149); }
        .progress-text { position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); font-weight: 600; font-size: 0.85em; }
        .collector-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 10px; }
        .collector-badge { background: #21262d; padding: 12px; border-radius: 6px; border-left: 3px solid #58a6ff; }
        .timestamp { color: #6e7681; font-size: 0.9em; }
        .metric { display: inline-block; margin-right: 20px; }
        .badge { display: inline-block; padding: 4px 10px; border-radius: 12px; font-size: 0.85em; font-weight: 600; }
        .badge.success { background: #2ea04320; color: #2ea043; }
        .badge.warning { background: #d2992220; color: #d29922; }
        .badge.danger { background: #da363320; color: #da3633; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚀 Crypto Data Factory - Production Monitor</h1>
            <p class="timestamp">⏱ Last Updated: {{ last_updated }}</p>
        </div>
        
        <div class="stats-grid">
            <div class="stat-card green">
                <div class="stat-label">DATABASE ROWS</div>
                <div class="stat-value">{{ "{:,}".format(db_rows) }}</div>
                <div class="stat-label">Status: <span class="status-{{ db_status }}">{{ db_status.upper() }}</span></div>
            </div>
            <div class="stat-card {% if db_coverage >= 95 %}green{% elif db_coverage >= 80 %}yellow{% else %}red{% endif %}">
                <div class="stat-label">DATA COVERAGE</div>
                <div class="stat-value">{{ "%.1f"|format(db_coverage) }}%</div>
                <div class="stat-label">Target: 100%</div>
            </div>
            <div class="stat-card blue">
                <div class="stat-label">ACTIVE COLLECTORS</div>
                <div class="stat-value">{{ collectors|length }}</div>
                <div class="stat-label">{{ active_collectors }} Running</div>
            </div>
            <div class="stat-card blue">
                <div class="stat-label">API SERVICES</div>
                <div class="stat-value">{{ services|length }}</div>
                <div class="stat-label">{{ total_api_keys }} Total Keys</div>
            </div>
        </div>
        
        <div class="service">
            <h2>📊 Field Population Stats (Last 100 Rows)</h2>
            <table>
                <tr>
                    <th>Field Name</th>
                    <th>Category</th>
                    <th>Population</th>
                    <th>Status</th>
                </tr>
                {% for field_name, field_data in field_stats.items() %}
                <tr>
                    <td><strong>{{ field_name }}</strong></td>
                    <td>{{ field_data.category }}</td>
                    <td>
                        <div class="progress-bar">
                            <div class="progress-fill {% if field_data.percentage >= 90 %}green{% elif field_data.percentage >= 50 %}yellow{% else %}red{% endif %}" 
                                 style="width: {{ field_data.percentage }}%"></div>
                            <div class="progress-text">{{ "%.1f"|format(field_data.percentage) }}%</div>
                        </div>
                    </td>
                    <td>
                        {% if field_data.percentage >= 90 %}
                        <span class="badge success">EXCELLENT</span>
                        {% elif field_data.percentage >= 50 %}
                        <span class="badge warning">PARTIAL</span>
                        {% else %}
                        <span class="badge danger">LOW</span>
                        {% endif %}
                    </td>
                </tr>
                {% endfor %}
            </table>
        </div>
        
        {% for service_name, service_data in services.items() %}
        <div class="service">
            <h2>🔑 {{ service_name.upper() }} API Keys</h2>
            <div class="metric">
                <strong>Total Keys:</strong> {{ service_data.total_keys }}
            </div>
            <div class="metric">
                <strong>Active Key:</strong> #{{ service_data.current_key_index + 1 }}
            </div>
            <div class="metric">
                <strong>Total Requests:</strong> {{ "{:,}".format(service_data.total_requests) }}
            </div>
            
            <table>
                <tr>
                    <th>Key #</th>
                    <th>Status</th>
                    <th>Usage</th>
                    <th>Rate Limit Progress</th>
                </tr>
                {% for key in service_data.key_list %}
                <tr>
                    <td>{{ key.index + 1 }} {% if key.active %}⭐{% endif %}</td>
                    <td class="status-{{ key.status.lower() }}">{{ key.status }}</td>
                    <td>{{ "{:,}".format(key.used) }} / {{ "{:,}".format(key.limit) }}</td>
                    <td>
                        <div class="progress-bar">
                            <div class="progress-fill {% if key.percentage < 70 %}green{% elif key.percentage < 90 %}yellow{% else %}red{% endif %}" 
                                 style="width: {{ key.percentage }}%"></div>
                            <div class="progress-text">{{ "%.1f"|format(key.percentage) }}%</div>
                        </div>
                    </td>
                </tr>
                {% endfor %}
            </table>
        </div>
        {% endfor %}
        
        <div class="service">
            <h2>📡 Data Collectors Status</h2>
            <div class="collector-grid">
                {% for collector, status in collectors.items() %}
                <div class="collector-badge">
                    <strong>{{ collector }}</strong><br>
                    <span class="status-{{ status }}">● {{ status.upper() }}</span>
                </div>
                {% endfor %}
            </div>
        </div>
    </div>
</body>
</html>
"""


@app.route('/')
def dashboard():
    """Render enhanced status dashboard with coverage stats"""
    # Calculate additional metrics
    total_api_keys = sum(s.get('total_keys', 0) for s in API_STATUS['services'].values())
    active_collectors = sum(1 for status in API_STATUS['collectors'].values() if status == 'ok')
    
    return render_template_string(
        HTML_TEMPLATE,
        last_updated=API_STATUS.get('last_updated', 'Never'),
        db_status=API_STATUS['database']['status'],
        db_rows=API_STATUS['database']['rows'],
        db_coverage=API_STATUS['database'].get('coverage', 0),
        services=API_STATUS['services'],
        collectors=API_STATUS['collectors'],
        field_stats=API_STATUS.get('field_stats', {}),
        total_api_keys=total_api_keys,
        active_collectors=active_collectors
    )


@app.route('/advanced')
def advanced_dashboard():
    """Render advanced monitoring dashboard"""
    import os
    template_path = os.path.join(os.path.dirname(__file__), 'enhanced_dashboard.html')
    with open(template_path, 'r') as f:
        return f.read()


@app.route('/api/status')
def api_status():
    """JSON API endpoint for status"""
    return jsonify(API_STATUS)


@app.route('/api/monitoring')
def api_monitoring():
    """Real-time monitoring data"""
    return jsonify(MONITOR.get_dashboard_data())


@app.route('/api/errors')
def api_errors():
    """Get recent error logs"""
    service = request.args.get('service')
    limit = int(request.args.get('limit', 50))
    return jsonify(MONITOR.get_error_details(service, limit))


@app.route('/api/field_errors/<field_name>')
def api_field_errors(field_name):
    """Get errors for specific field"""
    limit = int(request.args.get('limit', 10))
    errors = MONITOR.db_monitor.get_field_errors(field_name, limit)
    # Convert datetime objects to strings
    for error in errors:
        error['timestamp'] = error['timestamp'].isoformat()
    return jsonify(errors)


def update_status(key_manager, db, collectors_status):
    """Update global status with field-level coverage stats"""
    global API_STATUS
    
    # Get key manager status
    km_status = key_manager.get_status() if key_manager else {}
    
    # Get database stats with field coverage
    db_status = "ok"
    db_rows = 0
    field_stats = {}
    coverage_pct = 0
    
    if db:
        try:
            # Total row count
            result = db.query("SELECT COUNT(*) as count FROM feature_store")
            db_rows = result[0]['count'] if result else 0
            
            # Field-level coverage (last 100 rows)
            if db_rows > 0:
                coverage_query = """
                SELECT 
                    'open' as field, 'Price' as category, COUNT(open) as populated, COUNT(*) as total,
                    ROUND(COUNT(open)::numeric / COUNT(*) * 100, 1) as pct
                FROM (SELECT * FROM feature_store ORDER BY timestamp DESC LIMIT 100) t
                UNION ALL
                SELECT 'implied_volatility', 'Greeks', COUNT(implied_volatility), COUNT(*),
                    ROUND(COUNT(implied_volatility)::numeric / COUNT(*) * 100, 1)
                FROM (SELECT * FROM feature_store ORDER BY timestamp DESC LIMIT 100) t
                UNION ALL
                SELECT 'delta_bs', 'Black-Scholes', COUNT(delta_bs), COUNT(*),
                    ROUND(COUNT(delta_bs)::numeric / COUNT(*) * 100, 1)
                FROM (SELECT * FROM feature_store ORDER BY timestamp DESC LIMIT 100) t
                UNION ALL
                SELECT 'put_call_ratio_oi', 'Deribit PCR', COUNT(put_call_ratio_oi), COUNT(*),
                    ROUND(COUNT(put_call_ratio_oi)::numeric / COUNT(*) * 100, 1)
                FROM (SELECT * FROM feature_store ORDER BY timestamp DESC LIMIT 100) t
                UNION ALL
                SELECT 'liquidation_total_1h', 'CoinGlass', COUNT(liquidation_total_1h), COUNT(*),
                    ROUND(COUNT(liquidation_total_1h)::numeric / COUNT(*) * 100, 1)
                FROM (SELECT * FROM feature_store ORDER BY timestamp DESC LIMIT 100) t
                UNION ALL
                SELECT 'dxy_fred', 'FRED', COUNT(dxy_fred), COUNT(*),
                    ROUND(COUNT(dxy_fred)::numeric / COUNT(*) * 100, 1)
                FROM (SELECT * FROM feature_store ORDER BY timestamp DESC LIMIT 100) t
                UNION ALL
                SELECT 'fear_greed_index', 'Sentiment', COUNT(fear_greed_index), COUNT(*),
                    ROUND(COUNT(fear_greed_index)::numeric / COUNT(*) * 100, 1)
                FROM (SELECT * FROM feature_store ORDER BY timestamp DESC LIMIT 100) t
                UNION ALL
                SELECT 'funding_rate', 'Derivatives', COUNT(funding_rate), COUNT(*),
                    ROUND(COUNT(funding_rate)::numeric / COUNT(*) * 100, 1)
                FROM (SELECT * FROM feature_store ORDER BY timestamp DESC LIMIT 100) t
                """
                
                coverage_results = db.query(coverage_query)
                
                for row in coverage_results:
                    field_stats[row['field']] = {
                        'category': row['category'],
                        'populated': row['populated'],
                        'total': row['total'],
                        'percentage': float(row['pct'])
                    }
                
                # Calculate overall coverage
                if coverage_results:
                    coverage_pct = sum(r['pct'] for r in coverage_results) / len(coverage_results)
            
            db_status = "ok"
        except Exception as e:
            print(f"⚠️  Status update error: {e}")
            db_status = "error"
    
    API_STATUS = {
        "last_updated": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
        "services": km_status,
        "database": {
            "status": db_status, 
            "rows": db_rows,
            "coverage": coverage_pct
        },
        "collectors": collectors_status,
        "field_stats": field_stats
    }


def run_server(host='0.0.0.0', port=8080):
    """Run Flask server on port 8080"""
    print(f"🌐 Starting web UI on http://{host}:{port}")
    app.run(host=host, port=port, debug=False, use_reloader=False)


if __name__ == '__main__':
    run_server()
