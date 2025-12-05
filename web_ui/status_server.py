"""
Simple Web UI for Monitoring API Status
Runs on http://localhost:5000
Shows real-time status of all API keys and data collection
"""

from flask import Flask, jsonify, render_template_string
from flask_cors import CORS
from typing import Dict, Any
import threading
import time


app = Flask(__name__)
CORS(app)

# Global status storage (updated by main script)
API_STATUS = {
    "last_updated": None,
    "services": {},
    "database": {"status": "unknown", "rows": 0},
    "collectors": {}
}


HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Crypto Data Factory - Status Dashboard</title>
    <meta http-equiv="refresh" content="5">
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #1a1a1a; color: #fff; }
        h1 { color: #00ff00; }
        .service { border: 1px solid #444; margin: 10px 0; padding: 15px; border-radius: 5px; background: #2a2a2a; }
        .status-ok { color: #00ff00; }
        .status-warning { color: #ffaa00; }
        .status-critical { color: #ff0000; }
        .status-unknown { color: #888; }
        .key-row { padding: 5px; margin: 3px 0; background: #333; border-radius: 3px; }
        table { border-collapse: collapse; width: 100%; }
        th, td { padding: 8px; text-align: left; border-bottom: 1px solid #444; }
        th { background: #333; }
        .progress-bar { background: #444; height: 20px; border-radius: 3px; overflow: hidden; }
        .progress-fill { height: 100%; background: linear-gradient(90deg, #00ff00, #ffaa00, #ff0000); }
    </style>
</head>
<body>
    <h1>🚀 Crypto Data Factory - Live Status</h1>
    <p>Last Updated: <span id="last-update">{{ last_updated }}</span></p>
    
    <div class="service">
        <h2>📊 Database Status</h2>
        <p>Status: <span class="status-{{ db_status }}">{{ db_status }}</span></p>
        <p>Total Rows: {{ db_rows }}</p>
    </div>
    
    {% for service_name, service_data in services.items() %}
    <div class="service">
        <h2>{{ service_name.upper() }}</h2>
        <p>Total Keys: {{ service_data.total_keys }}</p>
        <p>Active Key: #{{ service_data.current_key_index + 1 }}</p>
        <p>Total Requests: {{ service_data.total_requests }}</p>
        
        <table>
            <tr>
                <th>Key #</th>
                <th>Status</th>
                <th>Usage</th>
                <th>Progress</th>
            </tr>
            {% for key in service_data.keys %}
            <tr>
                <td>{{ key.index + 1 }} {% if key.active %}⭐{% endif %}</td>
                <td class="status-{{ key.status.lower() }}">{{ key.status }}</td>
                <td>{{ key.used }} / {{ key.limit }}</td>
                <td>
                    <div class="progress-bar">
                        <div class="progress-fill" style="width: {{ key.percentage }}%"></div>
                    </div>
                    {{ key.percentage }}%
                </td>
            </tr>
            {% endfor %}
        </table>
    </div>
    {% endfor %}
    
    <div class="service">
        <h2>📡 Data Collectors</h2>
        {% for collector, status in collectors.items() %}
        <div class="key-row">
            <strong>{{ collector }}:</strong> 
            <span class="status-{{ status }}">{{ status }}</span>
        </div>
        {% endfor %}
    </div>
</body>
</html>
"""


@app.route('/')
def dashboard():
    """Render status dashboard"""
    return render_template_string(
        HTML_TEMPLATE,
        last_updated=API_STATUS.get('last_updated', 'Never'),
        db_status=API_STATUS['database']['status'],
        db_rows=API_STATUS['database']['rows'],
        services=API_STATUS['services'],
        collectors=API_STATUS['collectors']
    )


@app.route('/api/status')
def api_status():
    """JSON API endpoint for status"""
    return jsonify(API_STATUS)


def update_status(key_manager, db, collectors_status):
    """Update global status (called from main script)"""
    global API_STATUS
    
    # Get key manager status
    km_status = key_manager.get_status() if key_manager else {}
    
    # Get database stats
    db_status = "ok"
    db_rows = 0
    if db:
        try:
            result = db.query("SELECT COUNT(*) as count FROM feature_store")
            db_rows = result[0]['count'] if result else 0
            db_status = "ok"
        except:
            db_status = "error"
    
    API_STATUS = {
        "last_updated": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        "services": km_status,
        "database": {"status": db_status, "rows": db_rows},
        "collectors": collectors_status
    }


def run_server(host='0.0.0.0', port=5000):
    """Run Flask server"""
    print(f"🌐 Starting web UI on http://{host}:{port}")
    app.run(host=host, port=port, debug=False, use_reloader=False)


if __name__ == '__main__':
    run_server()
